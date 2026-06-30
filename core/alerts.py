import requests
import logging

logging.basicConfig(level=logging.INFO)


def send_discord_alert(webhook_url: str, message: str):
    """Send a text message to a Discord channel via webhook."""
    if not webhook_url or "discord.com/api/webhooks" not in webhook_url:
        return False

    payload = {
        "content": message,
        "username": "CascadeTrade Bot",
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=5)
        if response.status_code == 204:
            return True
        else:
            logging.error(f"Discord alert failed: {response.status_code}")
            return False
    except Exception as e:
        logging.error(f"Discord connection error: {e}")
        return False


def send_discord_file(webhook_url: str, file_data: bytes, filename: str, message: str):
    """Upload a file (like a CSV) directly to a Discord channel via webhook."""
    if not webhook_url or "discord.com/api/webhooks" not in webhook_url:
        return False

    payload = {
        "content": message,
        "username": "CascadeTrade Bot",
    }

    files = {
        "file": (filename, file_data, "text/csv"),
    }

    try:
        response = requests.post(webhook_url, data=payload, files=files, timeout=10)
        if response.status_code in [200, 204]:
            return True
        else:
            logging.error(f"Discord file upload failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logging.error(f"Discord file upload error: {e}")
        return False
