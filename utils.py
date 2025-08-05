from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config import ALLOWED_USERS

def is_authorized(user_id: int) -> bool:
    """Check if user is authorized to use the bot"""
    return user_id in ALLOWED_USERS

def format_currency(amount: float) -> str:
    """Format currency in Vietnamese style"""
    return f"{amount:,.0f}đ"

def parse_amount(amount_str: str) -> float:
    """Parse amount with k/m/tr notation"""
    amount_str = amount_str.lower()
    if amount_str.endswith('k'):
        return float(amount_str[:-1]) * 1000
    elif amount_str.endswith('m') or amount_str.endswith('tr'):
        # Handle both 'm' and 'tr' as million
        if amount_str.endswith('tr'):
            return float(amount_str[:-2]) * 1000000
        else:
            return float(amount_str[:-1]) * 1000000
    else:
        return float(amount_str)

# Common handler utilities
async def send_formatted_message(update: Update, message: str, parse_mode: ParseMode = ParseMode.MARKDOWN):
    """Send a formatted message with markdown parsing"""
    await update.message.reply_text(message, parse_mode=parse_mode)

async def check_authorization(update: Update) -> bool:
    """Check authorization and send unauthorized message if needed"""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ Sorry, you're not authorized to use this bot.")
        return False
    return True

def validate_args(args: list, min_length: int, error_message: str = None) -> bool:
    """Validate command arguments length"""
    if len(args) < min_length:
        return False
    return True

async def send_usage_error(update: Update, usage_message: str):
    """Send usage error message"""
    await send_formatted_message(update, usage_message)

def safe_int_conversion(value: str, error_message: str = "❌ Vui lòng nhập số hợp lệ") -> tuple[bool, int, str]:
    """
    Safely convert string to integer
    Returns: (success: bool, value: int, error_message: str)
    """
    try:
        return True, int(value), ""
    except ValueError:
        return False, 0, error_message

def safe_parse_amount(amount_str: str) -> tuple[bool, float, str]:
    """
    Safely parse amount with proper error handling
    Returns: (success: bool, amount: float, error_message: str)
    """
    try:
        amount = parse_amount(amount_str)
        return True, amount, ""
    except ValueError:
        return False, 0.0, "❌ Số tiền không hợp lệ. Ví dụ: 50k, 1.5m, 3tr"

def split_long_message(message: str, max_length: int = 4000) -> list[str]:
    """Split long messages into chunks"""
    if len(message) <= max_length:
        return [message]
    
    chunks = []
    current_chunk = ""
    lines = message.split('\n')
    
    for line in lines:
        if len(current_chunk + line + '\n') > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = line + '\n'
            else:
                # Line itself is too long, force split
                chunks.append(line[:max_length].strip())
                current_chunk = line[max_length:] + '\n'
        else:
            current_chunk += line + '\n'
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks

async def send_long_message(update: Update, message: str, continuation_prefix: str = "📝 *Tiếp tục...*\n\n"):
    """Send long message, splitting if necessary"""
    chunks = split_long_message(message)
    
    for i, chunk in enumerate(chunks):
        if i == 0:
            await send_formatted_message(update, chunk)
        else:
            await send_formatted_message(update, f"{continuation_prefix}{chunk}")

def format_priority_display(priority: int) -> tuple[str, str]:
    """Get priority emoji and name for display"""
    from config import get_priority_emoji, get_priority_name
    return get_priority_emoji(priority), get_priority_name(priority)

def format_category_display(category: str) -> str:
    """Get category emoji for display"""
    from config import get_category_emoji
    return get_category_emoji(category)

class MessageFormatter:
    """Helper class for consistent message formatting"""
    
    @staticmethod
    def format_item_list(items: list, formatter_func) -> str:
        """Format a list of items using a formatter function"""
        return "\n".join([formatter_func(i, item) for i, item in enumerate(items, 1)])
    
    @staticmethod
    def format_currency_item(index: int, item: dict, name_key: str, amount_key: str) -> str:
        """Format currency item for display"""
        name = item[name_key]
        amount = item.get(amount_key, 0)
        return f"{index}. *{name}*: {format_currency(amount)}"
    
    @staticmethod
    def format_summary_section(title: str, emoji: str, items: list, total: float) -> str:
        """Format a summary section with title, items, and total"""
        section = f"{emoji} *{title}:*\n"
        section += "\n".join(items)
        if total > 0:
            section += f"\n💰 *Tổng*: {format_currency(total)}"
        return section

def get_month_date_range(year: int, month: int) -> tuple:
    """Get start and end dates for a given month"""
    from datetime import date
    
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1)
    else:
        month_end = date(year, month + 1, 1)
    
    return month_start, month_end

def parse_date_argument(date_str: str) -> tuple[bool, int, int, str]:
    """
    Parse date argument in format MM/YYYY
    Returns: (success: bool, month: int, year: int, error_message: str)
    """
    try:
        if '/' not in date_str:
            return False, 0, 0, "❌ Format: /summary 8/2025 hoặc /summary (tháng này)"
        
        month_str, year_str = date_str.split('/')
        month = int(month_str)
        year = int(year_str)
        
        if month < 1 or month > 12:
            return False, 0, 0, "❌ Tháng phải từ 1-12"
        
        return True, month, year, ""
        
    except ValueError:
        return False, 0, 0, "❌ Format: /summary 8/2025 hoặc /summary (tháng này)"