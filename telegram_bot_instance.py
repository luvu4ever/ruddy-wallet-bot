from telegram import Bot
from config import TELEGRAM_BOT_TOKEN

# Global bot instance for scheduler access
_bot_instance = None

def set_bot_instance(bot: Bot):
    """Set the global bot instance"""
    global _bot_instance
    _bot_instance = bot

def get_bot_instance() -> Bot:
    """Get the global bot instance"""
    return _bot_instance

def create_bot_instance() -> Bot:
    """Create a new bot instance"""
    return Bot(token=TELEGRAM_BOT_TOKEN)