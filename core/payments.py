"""
core/payments.py
QuantPro Terminal — Subscription & Payment Handling
Handles database updates for Stripe subscription events.
"""

import os
import datetime
from core.database import SessionLocal, User

# ==========================================
# STRIPE PAYMENT LINKS
# ==========================================
# You will create these in your Stripe Dashboard (Product -> Payment Link)
# Paste the URLs here once created.
STRIPE_PAYMENT_LINKS = {
    "pro": os.environ.get("STRIPE_PRO_LINK", "https://buy.stripe.com/your_pro_link_here"),
    "fund": os.environ.get("STRIPE_FUND_LINK", "https://buy.stripe.com/your_fund_link_here"),
}


# ==========================================
# SUBSCRIPTION MANAGEMENT
# ==========================================

def upgrade_user(db: SessionLocal, username: str, plan: str, subscription_id: str = "", 
                 start_date: datetime.datetime = None, end_date: datetime.datetime = None) -> bool:
    """
    Upgrade a user to a paid plan (pro or fund).
    Called when a Stripe checkout.session.completed webhook is received.
    """
    valid_plans = ["pro", "fund", "admin"]
    if plan not in valid_plans:
        return False

    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False

    user.subscription_plan = plan
    user.tier = plan  # Update tier to match subscription
    user.subscription_status = "active"
    user.subscription_id = subscription_id
    user.subscription_start = start_date if start_date else datetime.datetime.utcnow()
    user.subscription_end = end_date  # Can be None for lifetime or monthly billing
    
    db.commit()
    return True


def downgrade_user(db: SessionLocal, username: str) -> bool:
    """
    Downgrade a user back to starter.
    Called when a Stripe customer.subscription.deleted webhook is received.
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False

    user.subscription_plan = "starter"
    user.tier = "starter"
    user.subscription_status = "cancelled"
    user.subscription_id = None
    user.subscription_start = None
    user.subscription_end = None
    
    db.commit()
    return True


def update_payment_failed(db: SessionLocal, username: str) -> bool:
    """
    Mark a user's subscription as past_due if payment fails.
    Called when a Stripe invoice.payment_failed webhook is received.
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False

    user.subscription_status = "past_due"
    # Optionally downgrade tier immediately, or give them a grace period.
    # For now, we'll just change the status so the app can warn them.
    # user.tier = "starter" 
    
    db.commit()
    return True


def check_subscription(db: SessionLocal, username: str) -> dict:
    """
    Check a user's current subscription status and tier.
    Returns a dictionary with plan details.
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return {"plan": "starter", "status": "inactive", "tier": "starter"}

    # Check if subscription has expired
    if user.subscription_end and user.subscription_end < datetime.datetime.utcnow():
        # Subscription expired, downgrade automatically
        downgrade_user(db, username)
        return {"plan": "starter", "status": "expired", "tier": "starter"}

    return {
        "plan": getattr(user, 'subscription_plan', 'starter') or 'starter',
        "status": getattr(user, 'subscription_status', 'inactive') or 'inactive',
        "tier": getattr(user, 'tier', 'starter') or 'starter',
        "start_date": str(user.subscription_start) if user.subscription_start else None,
        "end_date": str(user.subscription_end) if user.subscription_end else None,
    }


def get_payment_link(plan: str) -> str:
    """
    Return the Stripe Checkout Link for a given plan.
    """
    return STRIPE_PAYMENT_LINKS.get(plan.lower(), "")


# ==========================================
# WEBHOOK HANDLER (For Future FastAPI/Flask Integration)
# ==========================================
# NOTE: Streamlit cannot receive webhooks directly. 
# To fully automate this, you will eventually need a small Flask/FastAPI 
# server running alongside this app (e.g., on /stripe-webhook) that receives 
# the Stripe events and calls the functions above.
# 
# Example of how the webhook logic would look:
#
# def handle_stripe_webhook(event):
#     if event['type'] == 'checkout.session.completed':
#         username = event['data']['object']['client_reference_id']
#         plan = event['data']['object']['metadata']['plan']
#         sub_id = event['data']['object']['subscription']
#         db = SessionLocal()
#         upgrade_user(db, username, plan, sub_id)
#         db.close()
#         
#     elif event['type'] == 'customer.subscription.deleted':
#         username = event['data']['object']['metadata']['username']
#         db = SessionLocal()
#         downgrade_user(db, username)
#         db.close()
