from config import ALLOWED_USERS

def is_authorized(user_id: int) -> bool:
    """Check if user is authorized to use the bot"""
    return user_id in ALLOWED_USERS

def format_currency(amount: float) -> str:
    """Format currency in Vietnamese style"""
    return f"{amount:,.0f}đ"

def parse_amount(amount_str: str) -> float:
    """Parse amount with k/m notation"""
    amount_str = amount_str.lower()
    if amount_str.endswith('k'):
        return float(amount_str[:-1]) * 1000
    elif amount_str.endswith('m'):
        return float(amount_str[:-1]) * 1000000
    else:
        return float(amount_str)