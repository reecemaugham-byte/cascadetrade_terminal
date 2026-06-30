"""
core/payments.py
CascadeTrade Terminal — Subscription & Payment Handling
Handles Stripe payment links, webhook event processing,
and database updates for subscription lifecycle.
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

# Stripe Payment Links — create these in your Stripe Dashboard
# (Product → Payment Links → Copy link)
# Once created, paste the URLs below.
STRIPE_PAYMENT_LINKS = {
    "pro": os.environ.get("STRIPE_PRO_LINK", "https://buy.stripe.com/test_6oU9AMd581WtfmAbepcbC00"),
    "fund": os.environ.get("STRIPE_FUND_LINK", "https://buy.stripe.com/test_dRm6oA1mqbx3b6k96hcbC01"),
}


# ==========================================
# SUBSCRIPTION MANAGEMENT
# ==========================================

def upgrade_user(db: SessionLocal, username: str, plan: str,
                 subscription_id: str = "",
                 start_date: datetime.datetime = None,
                 end_date: datetime.datetime = None) -> bool:
    """
    Upgrade a user to a paid plan (pro, fund, or admin).
    Called when a Stripe checkout.session.completed webhook is received.
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


def downgrade_user(db: SessionLocal, username: str) -> bool:
    """
    Downgrade a user back to starter.
    Called when a Stripe customer.subscription.deleted event is received,
    or when a subscription expires after the grace period.
    Delegates to database.deactivate_subscription for consistency.
    """
    result = deactivate_subscription(db, username)

    if result:
        logger.info(f"User '{username}' downgraded to starter")
    else:
        logger.error(f"Failed to downgrade user '{username}'")

    return result


def update_payment_failed(db: SessionLocal, username: str) -> bool:
    """
    Mark a user's subscription as past_due when payment fails.
    Called when a Stripe invoice.payment_failed event is received.
    The user keeps their tier for now but sees a warning in the app.
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        logger.warning(f"update_payment_failed: user '{username}' not found")
        return False

    user.subscription_status = "past_due"
    db.commit()
    logger.warning(f"User '{username}' subscription marked as past_due")
    return True


def check_subscription(db: SessionLocal, username: str) -> dict:
    """
    Check a user's current subscription status and effective tier.
    Returns a dictionary with plan details.

    This also handles automatic downgrade if the subscription has expired.
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

    # --- Check for subscription expiry ---
    if user.subscription_status == "active" and user.subscription_end:
        if user.subscription_end < now:
            # Subscription period ended — downgrade
            logger.info(f"Subscription expired for '{username}', downgrading")
            downgrade_user(db, username)
            # Re-fetch the user after downgrade
            db.refresh(user)
            return {
                "plan": "starter",
                "status": "expired",
                "tier": "starter",
                "start_date": None,
                "end_date": None,
            }

    # --- Check for past_due grace period ---
    # If past_due for more than 7 days, downgrade
    if user.subscription_status == "past_due":
        # For now, just report the status — the app UI should show a warning
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
    Return the Stripe Checkout Link for a given plan.

    Appends client_reference_id and metadata to the URL so the webhook
    handler can identify which user and plan the checkout belongs to.

    Stripe Payment Links support these query parameters:
      ?client_reference_id=<username>&prefilled_promo_code=<code>
      &metadata[plan]=<plan>

    The client_reference_id is returned in the checkout.session.completed
    webhook event, allowing us to map the payment to a CascadeTrade user.
    """
    base_url = STRIPE_PAYMENT_LINKS.get(plan.lower(), "")
    if not base_url:
        return ""

    if username:
        separator = "&" if "?" in base_url else "?"
        link = f"{base_url}{separator}client_reference_id={username}&metadata[plan]={plan.lower()}"
        return link

    return base_url


# ==========================================
# STRIPE WEBHOOK HANDLER
# ==========================================

def verify_webhook_signature(payload: bytes, sig_header: str) -> bool:
    """
    Verify that a webhook payload was genuinely sent by Stripe
    using the webhook signing secret.

    Uses HMAC-SHA256 to compare the computed signature with
    the one in the Stripe-Signature header.
    """
    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET not set — skipping verification (dev mode)")
        return True  # Allow in dev; must be set in production

    try:
        # Stripe-Signature header format: t=<timestamp>,v1=<signature>
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

        # Compute expected signature
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


def find_user_for_subscription(db: SessionLocal, event_data: dict):
    """
    Given a Stripe event's data object, find the corresponding CascadeTrade user.

    Tries multiple strategies:
    1. client_reference_id (set during checkout via get_payment_link)
    2. Stripe subscription_id stored in our DB
    3. Email match (if we stored the email)

    Returns the User object or None.
    """
    # Strategy 1: client_reference_id (from payment link URL parameter)
    client_ref = event_data.get("client_reference_id", "")
    if client_ref:
        user = db.query(User).filter(User.username == client_ref).first()
        if user:
            return user

    # Strategy 2: Look up by Stripe subscription ID in our database
    sub_id = event_data.get("subscription", "")
    if sub_id and isinstance(sub_id, str):
        user = get_user_by_subscription_id(db, sub_id)
        if user:
            return user

    # Strategy 3: Look up by Stripe customer email
    customer_email = ""
    customer_details = event_data.get("customer_details", {})
    if customer_details:
        customer_email = customer_details.get("email", "")
    if not customer_email:
        # Some events have it at a different path
        customer_email = event_data.get("customer_email", "")

    if customer_email:
        user = db.query(User).filter(User.email == customer_email).first()
        if user:
            return user

    return None


def determine_plan_from_event(event_data: dict) -> str:
    """
    Determine the plan (pro/fund) from a Stripe event.

    Checks metadata first (set via get_payment_link), then falls back
    to looking up the price ID in the line items.
    """
    # Strategy 1: metadata[plan] from payment link URL parameter
    metadata = event_data.get("metadata", {})
    if metadata and metadata.get("plan"):
        plan = metadata["plan"].lower()
        if plan in ("pro", "fund", "admin"):
            return plan

    # Strategy 2: Try to match by amount (fallback)
    # Pro = $29/month, Fund = $99/month
    amount_total = event_data.get("amount_total", 0)
    if amount_total:
        amount_dollars = amount_total / 100  # Stripe amounts are in cents
        if abs(amount_dollars - 99) < 1:
            return "fund"
        elif abs(amount_dollars - 29) < 1:
            return "pro"

    return ""


def handle_stripe_webhook_event(event: dict) -> dict:
    """
    Process a single Stripe webhook event.

    This is the main entry point called by the webhook server.
    Returns a dict with 'success' (bool) and 'message' (str).

    Supported event types:
    - checkout.session.completed — new subscription purchase
    - customer.subscription.updated — plan change or renewal
    - customer.subscription.deleted — cancellation
    - invoice.payment_failed — payment issue
    """
    event_type = event.get("type", "")
    event_data = event.get("data", {}).get("object", {})

    logger.info(f"Processing Stripe webhook: {event_type}")

    db = SessionLocal()

    try:
        # ---- checkout.session.completed ----
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

            # Calculate end_date (30 days from now for monthly subscriptions)
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

        # ---- customer.subscription.updated ----
        elif event_type == "customer.subscription.updated":
            subscription_id = event_data.get("id", "")
            stripe_status = event_data.get("status", "")

            user = get_user_by_subscription_id(db, subscription_id)
            if not user:
                logger.warning(f"User not found for subscription update: {subscription_id}")
                return {"success": False, "message": "User not found for subscription update"}

            if stripe_status == "active":
                # Subscription renewed or plan changed
                plan = determine_plan_from_event(event_data) or user.subscription_plan or "starter"
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

        # ---- customer.subscription.deleted ----
        elif event_type == "customer.subscription.deleted":
            subscription_id = event_data.get("id", "")
            user = get_user_by_subscription_id(db, subscription_id)

            if not user:
                logger.warning(f"User not found for subscription deletion: {subscription_id}")
                return {"success": False, "message": "User not found for subscription deletion"}

            downgrade_user(db, user.username)
            logger.info(f"Subscription deleted: {user.username} → starter")
            return {"success": True, "message": f"Subscription deleted for {user.username}"}

        # ---- invoice.payment_failed ----
        elif event_type == "invoice.payment_failed":
            subscription_id = event_data.get("subscription", "")
            user = get_user_by_subscription_id(db, subscription_id)

            if not user:
                # Try by client_reference_id from the invoice
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

def admin_set_tier(db: SessionLocal, username: str, tier: str,
                   expires: datetime.datetime = None) -> bool:
    """
    Admin override: manually set a user's tier and optionally set expiry.
    This bypasses Stripe and directly sets the tier.
    """
    from core.database import set_user_tier
    return set_user_tier(db, username, tier, expires=expires)
