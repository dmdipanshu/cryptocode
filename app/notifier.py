import requests
from app.config import config

class Notifier:
    def send_telegram_message(self, message):
        """Sends a message to the configured Telegram chat."""
        if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
            print(message) # Fallback to console if not configured
            return
        
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': config.TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Failed to send Telegram message: {e}")

notifier = Notifier()
