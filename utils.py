from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config import ALLOWED_USERS

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
    except:
        try:
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except:
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

async def send_long_message(update: Update, message: str):
    """Send long message, splitting if necessary"""
    chunks = split_long_message(message)
    
    for i, chunk in enumerate(chunks):
        if i == 0:
            await send_formatted_message(update, chunk)
        else:
            continuation = "📝 *Tiếp tục...*\n\n" + chunk
            await send_formatted_message(update, continuation)

def get_month_date_range(year: int, month: int) -> tuple:
    """Get start and end dates for a month"""
    from datetime import date
    
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1)
    else:
        month_end = date(year, month + 1, 1)
    
    return month_start, month_end

def parse_date_argument(date_str: str) -> tuple[bool, int, int, str]:
    """Parse date argument in format MM/YYYY"""
    try:
        if '/' not in date_str:
            return False, 0, 0, "❌ Format: /summary 8/2025"
        
        month_str, year_str = date_str.split('/')
        month = int(month_str)
        year = int(year_str)
        
        if month < 1 or month > 12:
            return False, 0, 0, "❌ Tháng phải từ 1-12"
        
        return True, month, year, ""
        
    except ValueError:
        return False, 0, 0, "❌ Format: /summary 8/2025"