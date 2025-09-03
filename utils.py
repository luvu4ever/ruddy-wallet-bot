from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config import ALLOWED_USERS
from datetime import date, datetime, timedelta

def is_authorized(user_id: int) -> bool:
    """Check if user is authorized"""
    return user_id in ALLOWED_USERS

def format_currency(amount: float) -> str:
    """Format currency in Vietnamese style - SINGLE SOURCE OF TRUTH"""
    return f"{amount:,.0f}₫"

def parse_amount(amount_str: str) -> float:
    """Parse amount with k/m/tr notation"""
    amount_str = amount_str.lower()
    if amount_str.endswith('k'):
        return float(amount_str[:-1]) * 1000
    elif amount_str.endswith('m'):
        return float(amount_str[:-1]) * 1000000
    elif amount_str.endswith('tr'):
        return float(amount_str[:-2]) * 1000000
    else:
        return float(amount_str)

async def send_formatted_message(update: Update, message: str, parse_mode: ParseMode = ParseMode.MARKDOWN_V2):
    """Send formatted message with fallback"""
    try:
        await update.message.reply_text(message, parse_mode=parse_mode)
    except Exception:
        try:
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await update.message.reply_text(message)

async def check_authorization(update: Update) -> bool:
    """Check authorization and send error if needed"""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Sorry, you're not authorized to use this bot.")
        return False
    return True

def safe_int_conversion(value: str) -> tuple[bool, int, str]:
    """Safely convert string to integer - ADDED BACK FOR COMPATIBILITY"""
    try:
        return True, int(value), ""
    except ValueError:
        return False, 0, "⛔ Vui lòng nhập số hợp lệ"

def safe_parse_amount(amount_str: str) -> tuple[bool, float, str]:
    """Safely parse amount with error handling"""
    try:
        amount = parse_amount(amount_str)
        return True, amount, ""
    except ValueError:
        return False, 0.0, "⛔ Số tiền không hợp lệ. Ví dụ: 50k, 1.5m, 3tr"

async def send_long_message(update: Update, message: str, continuation_prefix: str = "📄 *Tiếp tục...*\n\n"):
    """Send long message, splitting if necessary - with inlined split logic"""
    max_length = 4000
    
    if len(message) <= max_length:
        chunks = [message]
    else:
        # Inline split logic (previously split_long_message function)
        chunks = []
        current_chunk = ""
        lines = message.split('\n')
        
        for line in lines:
            if len(current_chunk + line + '\n') > max_length:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = line + '\n'
                else:
                    chunks.append(line[:max_length].strip())
                    current_chunk = line[max_length:] + '\n'
            else:
                current_chunk += line + '\n'
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
    
    for i, chunk in enumerate(chunks):
        if i == 0:
            await send_formatted_message(update, chunk)
        else:
            continuation = continuation_prefix + chunk
            await send_formatted_message(update, continuation)

def get_current_month() -> tuple[int, int]:
    """Get current calendar month and year
    
    Returns:
        tuple[int, int]: (month, year)
    """
    today = datetime.now()
    return today.month, today.year

def get_month_date_range(year: int, month: int) -> tuple[date, date]:
    """Get start and end dates for a calendar month (1st to last day)
    
    Args:
        year: The year 
        month: The month number (1-12)
        
    Returns:
        tuple: (start_date, end_date) where:
        - start_date: 1st of the month
        - end_date: Last day of the month
        
    Example:
        get_month_date_range(2025, 8) returns (2025-08-01, 2025-08-31)
    """
    start_date = date(year, month, 1)
    
    # Calculate last day of month
    if month == 12:
        end_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)
    
    return start_date, end_date

def get_month_display(year: int, month: int) -> str:
    """Get display string for calendar month
    
    Args:
        year: The year
        month: The month number (1-12)
        
    Returns:
        str: Display string like "1/8-31/8/2025"
    """
    start_date, end_date = get_month_date_range(year, month)
    return f"{start_date.day}/{start_date.month}-{end_date.day}/{end_date.month}/{year}"

def parse_date_argument(date_str: str) -> tuple[bool, int, int, str]:
    """Parse date argument in format MM/YYYY for calendar months
    
    Args:
        date_str: Date string in format MM/YYYY
        
    Returns:
        tuple: (success, month, year, error_message)
    """
    try:
        if '/' not in date_str:
            return False, 0, 0, "⛔ Format: /summary 8/2025 (tháng 8 = 1/8-31/8/2025)"
        
        month_str, year_str = date_str.split('/')
        month = int(month_str)
        year = int(year_str)
        
        if month < 1 or month > 12:
            return False, 0, 0, "⛔ Tháng phải từ 1-12"
        
        return True, month, year, ""
        
    except ValueError:
        return False, 0, 0, "⛔ Format: /summary 8/2025 (tháng 8 = 1/8-31/8/2025)"