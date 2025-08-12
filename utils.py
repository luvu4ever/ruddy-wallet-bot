from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config import ALLOWED_USERS
from datetime import date, datetime

def is_authorized(user_id: int) -> bool:
    """Check if user is authorized"""
    return user_id in ALLOWED_USERS

def format_currency(amount: float) -> str:
    """Format currency in Vietnamese style"""
    return f"{amount:,.0f}đ"

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
        await update.message.reply_text("❌ Sorry, you're not authorized to use this bot.")
        return False
    return True

def safe_int_conversion(value: str) -> tuple[bool, int, str]:
    """Safely convert string to integer"""
    try:
        return True, int(value), ""
    except ValueError:
        return False, 0, "❌ Vui lòng nhập số hợp lệ"

def safe_parse_amount(amount_str: str) -> tuple[bool, float, str]:
    """Safely parse amount with error handling"""
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
            continuation = continuation_prefix + chunk
            await send_formatted_message(update, continuation)

def get_current_salary_month() -> tuple[int, int]:
    """Get current salary month and year based on today's date
    
    Returns:
        tuple[int, int]: (salary_month, salary_year)
        
    Logic:
        - If today >= 26th: current calendar month is the salary month
        - If today < 26th: previous calendar month is the salary month
    """
    today = datetime.now()
    
    if today.day >= 26:
        # We're in the salary month of current calendar month
        salary_month = today.month
        salary_year = today.year
    else:
        # We're in the salary month of previous calendar month
        if today.month == 1:
            salary_month = 12
            salary_year = today.year - 1
        else:
            salary_month = today.month - 1
            salary_year = today.year
    
    return salary_month, salary_year

def get_month_date_range(year: int, month: int) -> tuple[date, date]:
    """Get start and end dates for a salary month (26th to 25th)
    
    Args:
        year: The year of the salary month
        month: The salary month number (1-12)
        
    Returns:
        tuple: (start_date, end_date) where:
        - start_date: 26th of previous calendar month
        - end_date: 25th of current calendar month
        
    Example:
        get_month_date_range(2025, 8) returns (2025-07-26, 2025-08-25)
    """
    # Start date: 26th of previous calendar month
    if month == 1:
        start_month = 12
        start_year = year - 1
    else:
        start_month = month - 1
        start_year = year
    
    start_date = date(start_year, start_month, 26)
    
    # End date: 25th of current calendar month
    end_date = date(year, month, 25)
    
    return start_date, end_date

def get_salary_month_display(year: int, month: int) -> str:
    """Get display string for salary month range
    
    Args:
        year: The year of the salary month
        month: The salary month number (1-12)
        
    Returns:
        str: Display string like "26/7-25/8/2025"
    """
    start_date, end_date = get_month_date_range(year, month)
    return f"{start_date.day}/{start_date.month}-{end_date.day}/{end_date.month}/{year}"

def parse_date_argument(date_str: str) -> tuple[bool, int, int, str]:
    """Parse date argument in format MM/YYYY for salary months
    
    Args:
        date_str: Date string in format MM/YYYY
        
    Returns:
        tuple: (success, month, year, error_message)
    """
    try:
        if '/' not in date_str:
            return False, 0, 0, "❌ Format: /summary 8/2025 (tháng lương 8 = 26/7-25/8/2025)"
        
        month_str, year_str = date_str.split('/')
        month = int(month_str)
        year = int(year_str)
        
        if month < 1 or month > 12:
            return False, 0, 0, "❌ Tháng phải từ 1-12"
        
        return True, month, year, ""
        
    except ValueError:
        return False, 0, 0, "❌ Format: /summary 8/2025 (tháng lương 8 = 26/7-25/8/2025)"

def is_salary_month_start_today() -> bool:
    """Check if today is the 26th (start of new salary month)
    
    Returns:
        bool: True if today is 26th of any month
    """
    return datetime.now().day == 26