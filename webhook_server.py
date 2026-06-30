"""
webhook_server.py
CascadeTrade Terminal — Stripe Webhook Server

Run this alongside your Streamlit app to receive Stripe webhook events.
Stripe cannot send webhooks directly to Streamlit, so this small Flask
server acts as a bridge.

SETUP:
1. Install: pip install flask
2. Set environment variables:
     STRIPE_WEBHOOK_SECRET=whsec_xxxxx
     (STRIPE_SECRET_KEY is optional unless calling the Stripe API directly)
3. Run: python webhook_server.py
4. For local testing, expose via ngrok:
     ngrok http 5001
5. In Stripe Dashboard → Webhooks, add the ngrok URL:
     https://<your-ngrok-id>.ngrok.io/stripe/webhook
"""

import os
import json
import logging
from flask import Flask, request, jsonify

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("webhook_server")

app = Flask(__name__)

# Import the handler from our payments module
from core.payments import verify_webhook_signature, handle_stripe_webhook_event


@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    """Receive and process Stripe webhook events."""
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")

    # Verify the webhook came from Stripe
    if not verify_webhook_signature(payload, sig_header):
        logger.warning("⚠️ Webhook signature verification failed")
        return jsonify({"error": "Invalid signature"}), 400

    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        logger.error("Failed to parse webhook payload as JSON")
        return jsonify({"error": "Invalid JSON"}), 400

    # Process the event
    result = handle_stripe_webhook_event(event)

    if result["success"]:
        logger.info(f"✅ Webhook processed: {result['message']}")
        return jsonify({"received": True, "message": result["message"]}), 200
    else:
        logger.error(f"❌ Webhook failed: {result['message']}")
        return jsonify({"error": result["message"]}), 400


@app.route("/stripe/webhook", methods=["GET"])
def stripe_webhook_info():
    """Info endpoint to verify the webhook server is running."""
    return jsonify({
        "service": "CascadeTrade Webhook Server",
        "status": "running",
        "endpoints": {
            "POST /stripe/webhook": "Receive Stripe webhook events",
        },
    })


@app.route("/health", methods=["GET"])
def health_check():
    """Simple health check."""
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("WEBHOOK_PORT", 10000)))
    debug = os.environ.get("WEBHOOK_DEBUG", "false").lower() == "true"
    logger.info(f"🚀 CascadeTrade Webhook Server starting on port {port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
