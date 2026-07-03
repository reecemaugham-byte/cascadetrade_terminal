"""
core/payments.py
CascadeTrade Terminal — Subscription & Payment Handling
Handles Stripe Checkout Sessions, payment verification,
and database updates for subscription lifecycle.

PAYMENT FLOW:
1. User clicks "Upgrade to Pro" → get_payment_link() creates a Stripe Checkout Session
2. Stripe handles payment on their hosted page
3. After payment, Stripe redirects to: APP_URL/?session_id={CHECKOUT_SESSION_ID}
4. Streamlit app detects session_id, calls verify_and_process_payment()
5. Stripe API confirms payment → user is upgraded in the database

Alternative: User clicks "✅ Verify My Payment" button after login
6. verify_recent_payment_by_username() searches Stripe for recent payments
7. If found, user is upgraded automatically

NO SEPARATE WEBHOOK SERVER NEEDED.
"""

import os
import hmac
import hashlib
import datetime
import json
import logging
from core.database import (
    SessionLocal, User,
    update_subscription, deactivate_subscription,
    get_user_by_subscription_id,
)

logger = logging.getLogger(__name__)

# ==========================================
# STRIPE CONFIGURATION
# ==========================================

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Your app's public URL — used for Stripe payment redirects
APP_URL = os.environ.get("APP_URL", "https://walrus-app-xg6w8.ondigitalocean.app")

# Static Payment Links — used as fallback if Checkout Session creation fails
STRIPE_PAYMENT_LINKS = {
    "pro": os.environ.get("STRIPE_PRO_LINK", "https://buy.stripe.com/test_6oU9AMd581WtfmAbepcbC00"),
    "fund": os.environ.get("STRIPE_FUND_LINK", "https://buy.stripe.com/test_dRm6oA1mqbx3b6k96hcbC01"),
}

# Plan definitions for Checkout Session creation
STRIPE_PLANS = {
    "pro": {
        "name": "CascadeTrade Pro",
        "amount": 2900,
        "currency": "gbp",
        "interval": "month",
        "description": "Advanced signals, AI sentiment, live trading, DRIP calculator, profit skimming",
    },
    "fund": {
        "name": "CascadeTrade Fund",
        "amount": 9900,
        "currency": "gbp",
        "interval": "month",
        "description": "Everything in Pro plus multiple accounts, auto-rebalancing, weekly reports, priority support",
    },
}


# ==========================================
# SUBSCRIPTION MANAGEMENT
# ==========================================

def upgrade_user(db, username: str, plan: str,
                 subscription_id: str = "",
                 start_date: datetime.datetime = None,
                 end_date: datetime.datetime = None) -> bool:
    """
    Upgrade a user to a paid plan (pro, fund, or admin).
    Delegates to database.update_subscription for consistency.
    """
    valid_plans = ["pro", "fund", "admin"]
    if plan not in valid_plans:
        logger.warning(f"upgrade_user: invalid plan '{plan}' for user '{username}'")
        return False

    result = update_subscription(
        db=db,
        username=username,
        plan=plan,
        subscription_id=subscription_id,
        status="active",
        start_date=start_date,
        end_date=end_date,
    )

    if result:
        logger.info(f"User '{username}' upgraded to '{plan}' (sub: {subscription_id})")
    else:
        logger.error(f"Failed to upgrade user '{username}' to '{plan}'")

    return result


def downgrade_user(db, username: str) -> bool:
    """
    Downgrade a user back to starter.
    Delegates to database.deactivate_subscription for consistency.
    """
    result = deactivate_subscription(db, username)

    if result:
        logger.info(f"User '{username}' downgraded to starter")
    else:
        logger.error(f"Failed to downgrade user '{username}'")

    return result


def update_payment_failed(db, username: str) -> bool:
    """
    Mark a user's subscription as past_due when payment fails.
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        logger.warning(f"update_payment_failed: user '{username}' not found")
        return False

    user.subscription_status = "past_due"
    db.commit()
    logger.warning(f"User '{username}' subscription marked as past_due")
    return True


def check_subscription(db, username: str) -> dict:
    """
    Check a user's current subscription status and effective tier.
    Handles automatic downgrade if the subscription has expired.
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return {
            "plan": "starter",
            "status": "inactive",
            "tier": "starter",
            "start_date": None,
            "end_date": None,
        }

    now = datetime.datetime.utcnow()

    if user.subscription_status == "active" and user.subscription_end:
        if user.subscription_end < now:
            logger.info(f"Subscription expired for '{username}', downgrading")
            downgrade_user(db, username)
            db.refresh(user)
            return {
                "plan": "starter",
                "status": "expired",
                "tier": "starter",
                "start_date": None,
                "end_date": None,
            }

    if user.subscription_status == "past_due":
        pass

    return {
        "plan": getattr(user, 'subscription_plan', 'starter') or 'starter',
        "status": getattr(user, 'subscription_status', 'inactive') or 'inactive',
        "tier": getattr(user, 'tier', 'starter') or 'starter',
        "start_date": str(user.subscription_start) if user.subscription_start else None,
        "end_date": str(user.subscription_end) if user.subscription_end else None,
    }


def get_payment_link(plan: str, username: str = "") -> str:
    """
    Create a Stripe Checkout Session and return the URL.

    After payment, Stripe redirects to:
      APP_URL/?session_id={CHECKOUT_SESSION_ID}&plan={plan}

    Falls back to static Payment Links if the Stripe API call fails.
    """
    plan_lower = plan.lower()

    if not STRIPE_SECRET_KEY:
        logger.warning("STRIPE_SECRET_KEY not set — falling back to static payment links")
        fallback_url = STRIPE_PAYMENT_LINKS.get(plan_lower, "")
        if fallback_url and username:
            separator = "&" if "?" in fallback_url else "?"
            return f"{fallback_url}{separator}client_reference_id={username}&metadata[plan]={plan_lower}"
        return fallback_url

    if plan_lower not in STRIPE_PLANS:
        logger.warning(f"Unknown plan: {plan_lower}")
        return STRIPE_PAYMENT_LINKS.get(plan_lower, "")

    plan_info = STRIPE_PLANS[plan_lower]

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY

        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": plan_info["currency"],
                    "product_data": {
                        "name": plan_info["name"],
                        "description": plan_info.get("description", ""),
                    },
                    "unit_amount": plan_info["amount"],
                    "recurring": {
                        "interval": plan_info["interval"],
                    },
                },
                "quantity": 1,
            }],
            client_reference_id=username or "",
            metadata={
                "plan": plan_lower,
                "username": username or "",
            },
            success_url=f"{APP_URL}/?session_id={{CHECKOUT_SESSION_ID}}&plan={plan_lower}",
            cancel_url=f"{APP_URL}/?payment=cancelled",
        )

        logger.info(f"Created Stripe Checkout Session for '{username}' ({plan_lower}): {session.id}")
        return session.url

    except Exception as e:
        logger.error(f"Stripe Checkout Session creation failed: {e}")
        fallback_url = STRIPE_PAYMENT_LINKS.get(plan_lower, "")
        if fallback_url:
            logger.warning(f"Falling back to static payment link for {plan_lower}")
            if username:
                separator = "&" if "?" in fallback_url else "?"
                return f"{fallback_url}{separator}client_reference_id={username}&metadata[plan]={plan_lower}"
        return fallback_url


# ==========================================
# STRIPE PAYMENT VERIFICATION
# ==========================================

def verify_and_process_payment(session_id: str, username: str) -> dict:
    """
    Verify a Stripe Checkout Session and upgrade the user if paid.
    Called when the user returns from Stripe with a session_id parameter.
    Uses getattr() for Stripe objects (not .get() which causes AttributeError).
    """
    if not STRIPE_SECRET_KEY:
        return {
            "success": False,
            "message": "Stripe API key not configured. Please set STRIPE_SECRET_KEY environment variable.",
            "plan": "",
        }

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY

        session = stripe.checkout.Session.retrieve(session_id)

        # Use getattr() for Stripe objects — they are NOT dicts
        payment_status = getattr(session, 'payment_status', '') or ''

        if payment_status != "paid":
            return {
                "success": False,
                "message": f"Payment status is '{payment_status}', not 'paid'. Please try again or contact support.",
                "plan": "",
            }

        # Get username from client_reference_id or metadata
        client_ref = getattr(session, 'client_reference_id', '') or ''
        metadata_obj = getattr(session, 'metadata', None)
        metadata = dict(metadata_obj) if metadata_obj else {}


        # Priority: client_reference_id > metadata.username > passed-in username
        if client_ref:
            username = client_ref
            logger.info(f"Using client_reference_id from Stripe: {username}")
        elif metadata and metadata.get("username"):
            username = metadata["username"]
            logger.info(f"Using metadata username from Stripe: {username}")
        elif not username:
            return {
                "success": False,
                "message": "Could not identify your account. Please log in and try the 'Verify My Payment' button.",
                "plan": "",
            }

        # Determine the plan
        plan = ""

        if metadata and metadata.get("plan"):
            plan = metadata["plan"].lower()
        else:
            amount_total = getattr(session, 'amount_total', 0) or 0
            if amount_total:
                for plan_key, plan_info in STRIPE_PLANS.items():
                    if abs(amount_total - plan_info["amount"]) < 100:
                        plan = plan_key
                        break

        if plan not in ["pro", "fund", "admin"]:
            return {
                "success": False,
                "message": "Could not determine plan from payment. Please contact support.",
                "plan": "",
            }

        # Get subscription details
        subscription_id = str(getattr(session, 'subscription', '') or '')
        start_date = datetime.datetime.utcnow()
        end_date = start_date + datetime.timedelta(days=30)

        db = SessionLocal()
        try:
            success = upgrade_user(
                db=db,
                username=username,
                plan=plan,
                subscription_id=subscription_id,
                start_date=start_date,
                end_date=end_date,
            )

            if success:
                logger.info(f"✅ Payment verified and user '{username}' upgraded to '{plan}'")
                return {
                    "success": True,
                    "message": f"Welcome to {plan.title()}! Your subscription is now active.",
                    "plan": plan,
                }
            else:
                logger.error(f"❌ Payment verified but upgrade failed for '{username}' to '{plan}'")
                return {
                    "success": False,
                    "message": "Payment received but upgrade failed. Please contact support.",
                    "plan": plan,
                }
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Payment verification error: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Could not verify payment. Error: {str(e)}",
            "plan": "",
        }


def verify_recent_payment_by_username(username: str) -> dict:
    """
    Check Stripe for recent checkout sessions for this username.
    Used as a fallback when the session_id redirect doesn't work.
    User clicks "✅ Verify My Payment" button after logging in.
    Uses getattr() for Stripe objects.
    """
    if not STRIPE_SECRET_KEY:
        return {
            "success": False,
            "message": "Stripe API key not configured. Please set STRIPE_SECRET_KEY environment variable.",
            "plan": "",
        }

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY

        sessions = stripe.checkout.Session.list(limit=25)

        for session in sessions.data:
            client_ref = getattr(session, 'client_reference_id', '') or ''
            metadata_obj = getattr(session, 'metadata', None)
            metadata = dict(metadata_obj) if metadata_obj else {}

            payment_status = getattr(session, 'payment_status', '') or ''

            if (client_ref == username or (metadata and metadata.get("username") == username)) and payment_status == "paid":
                plan = ""

                if metadata and metadata.get("plan"):
                    plan = metadata["plan"].lower()
                else:
                    amount_total = getattr(session, 'amount_total', 0) or 0
                    for plan_key, plan_info in STRIPE_PLANS.items():
                        if abs(amount_total - plan_info["amount"]) < 100:
                            plan = plan_key
                            break

                if plan not in ["pro", "fund", "admin"]:
                    amount_total = getattr(session, 'amount_total', 0) or 0
                    if amount_total >= 9900:
                        plan = "fund"
                    elif amount_total >= 2900:
                        plan = "pro"

                if plan in ["pro", "fund", "admin"]:
                    subscription_id = str(getattr(session, 'subscription', '') or '')
                    start_date = datetime.datetime.utcnow()
                    end_date = start_date + datetime.timedelta(days=30)

                    db = SessionLocal()
                    try:
                        success = upgrade_user(
                            db=db,
                            username=username,
                            plan=plan,
                            subscription_id=subscription_id,
                            start_date=start_date,
                            end_date=end_date,
                        )
                        if success:
                            logger.info(f"✅ Manual payment verification: {username} upgraded to {plan}")
                            return {
                                "success": True,
                                "message": f"Welcome to {plan.title()}! Your subscription is now active.",
                                "plan": plan,
                            }
                        else:
                            return {
                                "success": False,
                                "message": "Payment found but upgrade failed. Please contact support.",
                                "plan": plan,
                            }
                    finally:
                        db.close()

        return {
            "success": False,
            "message": "No recent paid checkout found for your account. If you just paid, please wait 1-2 minutes and try again.",
            "plan": "",
        }

    except Exception as e:
        logger.error(f"Recent payment verification error: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error checking payments: {str(e)}",
            "plan": "",
        }


# ==========================================
# STRIPE WEBHOOK HANDLER (Optional)
# ==========================================

def verify_webhook_signature(payload: bytes, sig_header: str) -> bool:
    """
    Verify that a webhook payload was genuinely sent by Stripe.
    Only needed if you set up a webhook server later.
    """
    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET not set — skipping verification (dev mode)")
        return True

    try:
        elements = sig_header.split(",")
        timestamp = None
        signature = None

        for element in elements:
            key, value = element.split("=", 1)
            if key == "t":
                timestamp = value
            elif key == "v1":
                signature = value

        if not timestamp or not signature:
            logger.error("Invalid Stripe-Signature header format")
            return False

        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected_sig = hmac.new(
            STRIPE_WEBHOOK_SECRET.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected_sig, signature)

    except Exception as e:
        logger.error(f"Webhook signature verification failed: {e}")
        return False


def find_user_for_subscription(db, event_data: dict):
    """
    Find the CascadeTrade user from a Stripe event's data object.
    """
    client_ref = event_data.get("client_reference_id", "")
    if client_ref:
        user = db.query(User).filter(User.username == client_ref).first()
        if user:
            logger.info(f"Found user by client_reference_id: {client_ref}")
            return user

    metadata = event_data.get("metadata", {})
    if metadata and metadata.get("username"):
        username = metadata["username"]
        user = db.query(User).filter(User.username == username).first()
        if user:
            logger.info(f"Found user by metadata username: {username}")
            return user

    sub_id = event_data.get("subscription", "")
    if sub_id and isinstance(sub_id, str):
        user = get_user_by_subscription_id(db, sub_id)
        if user:
            logger.info(f"Found user by subscription_id: {sub_id}")
            return user

    customer_email = ""
    customer_details = event_data.get("customer_details", {})
    if customer_details:
        customer_email = customer_details.get("email", "")
    if not customer_email:
        customer_email = event_data.get("customer_email", "")

    if customer_email:
        user = db.query(User).filter(User.email == customer_email).first()
        if user:
            logger.info(f"Found user by email: {customer_email}")
            return user

    logger.error(f"Could not find user for event: client_ref={client_ref}, metadata={metadata}, sub_id={sub_id}, email={customer_email}")
    return None


def determine_plan_from_event(event_data: dict) -> str:
    """
    Determine the plan (pro/fund) from a Stripe event.
    """
    metadata = event_data.get("metadata", {})
    if metadata and metadata.get("plan"):
        plan = metadata["plan"].lower()
        if plan in ("pro", "fund", "admin"):
            return plan

    amount_total = event_data.get("amount_total", 0)
    if amount_total:
        for plan_key, plan_info in STRIPE_PLANS.items():
            if abs(amount_total - plan_info["amount"]) < 100:
                return plan_key

    return ""


def handle_stripe_webhook_event(event: dict) -> dict:
    """
    Process a single Stripe webhook event.
    Only needed if you set up a webhook server later.
    """
    event_type = event.get("type", "")
    event_data = event.get("data", {}).get("object", {})

    logger.info(f"Processing Stripe webhook: {event_type}")

    db = SessionLocal()

    try:
        if event_type == "checkout.session.completed":
            user = find_user_for_subscription(db, event_data)
            if not user:
                logger.error(f"Could not find user for checkout event: {event_data.get('id')}")
                return {"success": False, "message": "User not found for checkout"}

            plan = determine_plan_from_event(event_data)
            if not plan:
                logger.error(f"Could not determine plan for checkout: {event_data.get('id')}")
                return {"success": False, "message": "Could not determine plan"}

            subscription_id = event_data.get("subscription", "") or ""
            start_date = datetime.datetime.utcnow()
            end_date = start_date + datetime.timedelta(days=30)

            success = upgrade_user(
                db=db,
                username=user.username,
                plan=plan,
                subscription_id=subscription_id,
                start_date=start_date,
                end_date=end_date,
            )

            if success:
                logger.info(f"✅ Checkout complete: {user.username} → {plan}")
                return {"success": True, "message": f"User {user.username} upgraded to {plan}"}
            else:
                return {"success": False, "message": "Upgrade failed"}

        elif event_type == "customer.subscription.updated":
            subscription_id = event_data.get("id", "")
            stripe_status = event_data.get("status", "")

            user = get_user_by_subscription_id(db, subscription_id)
            if not user:
                logger.warning(f"User not found for subscription update: {subscription_id}")
                return {"success": False, "message": "User not found for subscription update"}

            if stripe_status == "active":
                plan = determine_plan_from_event(event_data) or getattr(user, 'subscription_plan', 'starter') or "starter"
                current_period_end = event_data.get("current_period_end")

                end_date = None
                if current_period_end:
                    end_date = datetime.datetime.utcfromtimestamp(current_period_end)

                update_subscription(
                    db=db,
                    username=user.username,
                    plan=plan,
                    subscription_id=subscription_id,
                    status="active",
                    end_date=end_date,
                )
                logger.info(f"✅ Subscription updated: {user.username} → {plan}")
                return {"success": True, "message": f"Subscription updated for {user.username}"}

            elif stripe_status in ("canceled", "incomplete_expired"):
                downgrade_user(db, user.username)
                logger.info(f"Subscription cancelled: {user.username}")
                return {"success": True, "message": f"Subscription cancelled for {user.username}"}

            elif stripe_status == "past_due":
                update_payment_failed(db, user.username)
                return {"success": True, "message": f"Payment failed for {user.username}"}

            else:
                logger.info(f"Unhandled subscription status: {stripe_status}")
                return {"success": True, "message": f"Subscription status: {stripe_status}"}

        elif event_type == "customer.subscription.deleted":
            subscription_id = event_data.get("id", "")
            user = get_user_by_subscription_id(db, subscription_id)

            if not user:
                logger.warning(f"User not found for subscription deletion: {subscription_id}")
                return {"success": False, "message": "User not found for subscription deletion"}

            downgrade_user(db, user.username)
            logger.info(f"Subscription deleted: {user.username} → starter")
            return {"success": True, "message": f"Subscription deleted for {user.username}"}

        elif event_type == "invoice.payment_failed":
            subscription_id = event_data.get("subscription", "")
            user = get_user_by_subscription_id(db, subscription_id)

            if not user:
                client_ref = event_data.get("client_reference_id", "")
                if client_ref:
                    user = db.query(User).filter(User.username == client_ref).first()

            if not user:
                logger.warning(f"User not found for payment failure: {subscription_id}")
                return {"success": False, "message": "User not found for payment failure"}

            update_payment_failed(db, user.username)
            return {"success": True, "message": f"Payment failure recorded for {user.username}"}

        else:
            logger.info(f"Unhandled Stripe event type: {event_type}")
            return {"success": True, "message": f"Event type '{event_type}' not handled"}

    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {e}", exc_info=True)
        return {"success": False, "message": f"Internal error: {str(e)}"}

    finally:
        db.close()


# ==========================================
# MANUAL TIER OVERRIDE (Admin)
# ==========================================

def admin_set_tier(db, username: str, tier: str,
                   expires: datetime.datetime = None) -> bool:
    """
    Admin override: manually set a user's tier and optionally set expiry.
    """
    from core.database import set_user_tier
    return set_user_tier(db, username, tier, expires=expires)
