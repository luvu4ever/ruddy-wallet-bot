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

# Enhanced text formatting utilities
class MessageFormatter:
    """Rich text formatting for Telegram messages"""
    
    # Basic formatting
    @staticmethod
    def bold(text: str) -> str:
        """Bold text: *text*"""
        return f"*{text}*"
    
    @staticmethod
    def italic(text: str) -> str:
        """Italic text: _text_"""
        return f"_{text}_"
    
    @staticmethod
    def code(text: str) -> str:
        """Inline code: `text`"""
        return f"`{text}`"
    
    @staticmethod
    def pre(text: str) -> str:
        """Preformatted text block: ```text```"""
        return f"```\n{text}\n```"
    
    @staticmethod
    def underline(text: str) -> str:
        """Underlined text: __text__"""
        return f"__{text}__"
    
    @staticmethod
    def strikethrough(text: str) -> str:
        """Strikethrough text: ~text~"""
        return f"~{text}~"
    
    # Combination formatting
    @staticmethod
    def bold_italic(text: str) -> str:
        """Bold and italic: *_text_*"""
        return f"*_{text}_*"
    
    @staticmethod
    def bold_underline(text: str) -> str:
        """Bold and underlined: *__text__*"""
        return f"*__{text}__*"
    
    # Semantic formatting
    @staticmethod
    def title(text: str) -> str:
        """Format as title - bold and larger appearance"""
        return f"*{text.upper()}*"
    
    @staticmethod
    def subtitle(text: str) -> str:
        """Format as subtitle - bold italic"""
        return f"*_{text}_*"
    
    @staticmethod
    def highlight(text: str) -> str:
        """Highlight important text - bold underline"""
        return f"*__{text}__*"
    
    @staticmethod
    def money(amount: str) -> str:
        """Format money amounts"""
        return f"`{amount}`"
    
    @staticmethod
    def category(text: str) -> str:
        """Format category names"""
        return f"_{text.upper()}_"
    
    @staticmethod
    def command(text: str) -> str:
        """Format command text"""
        return f"`{text}`"
    
    @staticmethod
    def success(text: str) -> str:
        """Format success messages"""
        return f"✅ *{text}*"
    
    @staticmethod
    def error(text: str) -> str:
        """Format error messages"""
        return f"❌ *{text}*"
    
    @staticmethod
    def warning(text: str) -> str:
        """Format warning messages"""
        return f"⚠️ *{text}*"
    
    @staticmethod
    def info(text: str) -> str:
        """Format info messages"""
        return f"ℹ️ _{text}_"

# Enhanced message formatting
class MessageBuilder:
    """Build rich formatted messages"""
    
    def __init__(self):
        self.lines = []
    
    def add_title(self, text: str, emoji: str = "") -> 'MessageBuilder':
        """Add a title line"""
        title = f"{emoji} {MessageFormatter.title(text)}" if emoji else MessageFormatter.title(text)
        self.lines.append(title)
        return self
    
    def add_subtitle(self, text: str, emoji: str = "") -> 'MessageBuilder':
        """Add a subtitle line"""
        subtitle = f"{emoji} {MessageFormatter.subtitle(text)}" if emoji else MessageFormatter.subtitle(text)
        self.lines.append(subtitle)
        return self
    
    def add_section(self, title: str, content: str, emoji: str = "") -> 'MessageBuilder':
        """Add a section with title and content"""
        section_title = f"{emoji} {MessageFormatter.bold(title)}:" if emoji else f"{MessageFormatter.bold(title)}:"
        self.lines.append(section_title)
        self.lines.append(content)
        return self
    
    def add_line(self, text: str) -> 'MessageBuilder':
        """Add a regular line"""
        self.lines.append(text)
        return self
    
    def add_bullet(self, text: str, bullet: str = "•") -> 'MessageBuilder':
        """Add a bullet point"""
        self.lines.append(f"{bullet} {text}")
        return self
    
    def add_money_line(self, label: str, amount: str, emoji: str = "💰") -> 'MessageBuilder':
        """Add a money line with formatting"""
        self.lines.append(f"{emoji} {MessageFormatter.bold(label)}: {MessageFormatter.money(amount)}")
        return self
    
    def add_separator(self) -> 'MessageBuilder':
        """Add empty line separator"""
        self.lines.append("")
        return self
    
    def add_divider(self, char: str = "─", length: int = 20) -> 'MessageBuilder':
        """Add a visual divider"""
        self.lines.append(char * length)
        return self
    
    def build(self) -> str:
        """Build the final message"""
        return "\n".join(self.lines)

# Common handler utilities (keeping existing ones)
async def send_formatted_message(update: Update, message: str, parse_mode: ParseMode = ParseMode.MARKDOWN_V2):
    """Send a formatted message with MarkdownV2 parsing for better formatting"""
    try:
        await update.message.reply_text(message, parse_mode=parse_mode)
    except Exception as e:
        # Fallback to regular markdown if MarkdownV2 fails
        try:
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except:
            # Ultimate fallback - send without formatting
            await update.message.reply_text(message)

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

async def send_long_message(update: Update, message: str, continuation_prefix: str = "📝 *Tiếp tục\\.\\.\\.*\n\n"):
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
            return False, 0, 0, "❌ Format: /summary 8/2025 hoặc /summary \\(tháng này\\)"
        
        month_str, year_str = date_str.split('/')
        month = int(month_str)
        year = int(year_str)
        
        if month < 1 or month > 12:
            return False, 0, 0, "❌ Tháng phải từ 1\\-12"
        
        return True, month, year, ""
        
    except ValueError:
        return False, 0, 0, "❌ Format: /summary 8/2025 hoặc /summary \\(tháng này\\)"

# MarkdownV2 utilities for better formatting
def escape_markdown_v2(text: str) -> str:
    """Escape special characters for MarkdownV2"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def format_money_v2(amount: float) -> str:
    """Format money for MarkdownV2"""
    return f"`{amount:,.0f}đ`"

def format_section_header(title: str, emoji: str = "") -> str:
    """Format section header for MarkdownV2"""
    escaped_title = escape_markdown_v2(title.upper())
    return f"{emoji} *{escaped_title}*" if emoji else f"*{escaped_title}*"