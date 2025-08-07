import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =============================================================================
# BASIC CONFIGURATION
# =============================================================================

# Default category for subscriptions
DEFAULT_SUBSCRIPTION_CATEGORY = "cá nhân"

# Income types - simplified
INCOME_TYPES = {
    "construction": {"emoji": "🏗️", "description": "Construction income"},
    "salary": {"emoji": "💵", "description": "Monthly salary"},
    "random": {"emoji": "🎉", "description": "Additional income"}
}

def get_income_emoji(income_type):
    return INCOME_TYPES.get(income_type, {}).get("emoji", "💰")

# =============================================================================
# SIMPLE MESSAGE TEMPLATES
# =============================================================================

MESSAGE_TEMPLATES = {
    "list_overview": """📝 *CHI TIÊU THÁNG {month}/{year}*

{categories_content}

💰 *TỔNG CỘNG: {total}*

📊 *PHÂN TÍCH THU CHI:*
🏗️ *CÔNG TRÌNH:* Thu `{construction_income}` - Chi `{construction_expense}` = `{construction_net}`
💰 *KHÁC:* Thu `{general_income}` - Chi `{general_expense}` = `{general_net}`{wishlist_section}

💡 _Dùng `/list [danh mục]` để xem tất cả giao dịch của danh mục_""",

    "category_header": """{emoji} *{category}* - `{total}`{budget_info}""",
    "expense_item": """  {date} - {description} - `{amount}`""",
    "more_items": """  _... và {count} giao dịch khác_""",
    
    "summary_report": """📊 *BÁO CÁO THÁNG {month}/{year}*{subscription_info}

💵 *Thu nhập:* `{total_income}`
💰 *Chi tiêu:* `{total_expenses}`
📈 *Tiết kiệm ròng:* `{net_savings}`

🏗️ *PHÂN TÍCH CÔNG TRÌNH:*
💵 Thu nhập: `{construction_income}`
💰 Chi tiêu: `{construction_expense}`
📊 Lãi/lỗ: `{construction_net}`

💰 *PHÂN TÍCH KHÁC:*
💵 Thu nhập: `{general_income}`
💰 Chi tiêu: `{general_expense}`
📊 Lãi/lỗ: `{general_net}`{budget_info}

📊 *Giao dịch:* {expense_count} chi tiêu, {income_count} thu nhập""",

    "budget_section": """
💰 *BUDGET:*
💰 *Budget tháng:* `{budget_total}`
{budget_status} *{status_text}:* `{amount}`""",

    "savings_update": """✅ *ĐÃ CẬP NHẬT TIẾT KIỆM!*

💎 *TIẾT KIỆM MỚI*
💰 *Số tiền:* {amount}"""
}

# Simple formatting functions
def format_budget_info(remaining_budget, category):
    if category not in remaining_budget:
        return ""
    
    budget_data = remaining_budget[category]
    remaining = budget_data["remaining"]
    
    if remaining >= 0:
        return f" _(còn lại: {format_currency(remaining)})_"
    else:
        return f" _⚠️ (vượt: {format_currency(abs(remaining))})_"

def format_expense_item(expense):
    from datetime import datetime
    
    amount = float(expense["amount"])
    description = expense["description"]
    
    date_obj = datetime.strptime(expense["date"], "%Y-%m-%d")
    date_str = f"{date_obj.day:02d}/{date_obj.month:02d}"
    
    return MESSAGE_TEMPLATES["expense_item"].format(
        date=date_str,
        description=description,
        amount=format_currency(amount)
    )

# Currency formatting - single source of truth
def format_currency(amount: float) -> str:
    """Format currency in Vietnamese style"""
    return f"{amount:,.0f}đ"

# =============================================================================
# BOT MESSAGES - SIMPLIFIED
# =============================================================================

BOT_MESSAGES = {
    "welcome": """🤖 *CHÀO MỪNG ĐẾN VỚI BOT TÀI CHÍNH!*

*📝 CÁCH SỬ DỤNG:*
• *Chi tiêu:* `50k bún bò huế`, `1.5m sofa`
• *Thu nhập:* `/income salary 3m`

*⚡ LỆNH NHANH:*
📊 `/list` - Xem chi tiêu + wishlist analysis
📈 `/summary` - Báo cáo tháng
💵 `/income` - Quản lý thu nhập
💰 `/budget ăn uống 1.5m` - Đặt budget
🛍️ `/wishlist` - Xem wishlist (5 levels)
❓ `/help` - Hướng dẫn""",
    
    "help": """💡 *HƯỚNG DẪN*

*📝 CHI TIÊU:*
🍜 `50k bún bò huế` → ăn uống
🐾 `100k cát mèo` → mèo
🏗️ `1.5m sofa` → công trình

*💵 THU NHẬP:*
💰 `/income salary 3m` → lương tháng
🏗️ `/income construction 2m` → thu nhập xây dựng

*🛍️ WISHLIST (5 LEVELS):*
➕ `/wishadd iPhone 25m prio:1` → thêm (level 1-5)
📋 `/wishlist` → xem + phân tích tài chính
❌ `/wishremove 1` → xóa

*💰 BUDGET:*
💰 `/budget ăn uống 1.5m` → đặt budget
📊 `/budgetlist` → xem budget plans

*🔍 XEM:*
📊 `/list` → tổng quan + wishlist analysis
📈 `/summary` → báo cáo tháng
💎 `/saving` → tiết kiệm""",
    
    "unknown_message": """❓ *Tôi không hiểu tin nhắn này.*

*💡 THỬ:*
🍜 `50k bún bò huế` _(chi tiêu)_
💵 `/income salary 3m` _(thu nhập)_""",
    
    "unauthorized": """❌ *KHÔNG CÓ QUYỀN TRUY CẬP*""",
    
    "no_expenses_this_month": """📝 *KHÔNG CÓ CHI TIÊU*

📊 *Tháng {month}/{year}*
Chưa có giao dịch nào.""",
    
    "no_budget": """💰 *CHƯA CÓ BUDGET!*
Dùng `/budget ăn uống 1.5m` để đặt budget""",
    
    "no_subscriptions": """📅 *KHÔNG CÓ SUBSCRIPTION!*
Dùng `/subadd Spotify 33k` để thêm""",
    
    "savings_current": """💎 *TIẾT KIỆM HIỆN TẠI*
💰 *{amount}*
📅 _{date}_""",
    
    "savings_none": """💎 *TIẾT KIỆM: 0đ*
Dùng `/editsaving 500k` để cập nhật""",
    
    "income_types": """💰 *CÁC LOẠI THU NHẬP*

💵 *construction* 🏗️ - Construction income
💵 *salary* 💵 - Monthly salary  
💵 *random* 🎉 - Additional income

*Cách dùng:* `/income salary 3m lương tháng`""",
    
    "income_added": """✅ *ĐÃ THÊM THU NHẬP!*
{emoji} *{type}*: {amount}
📝 *{description}*""",
    
    "format_errors": {
        "savings_usage": "❌ Dùng: `/editsaving 500k`",
        "income_usage": "❌ Dùng: `/income salary 3m`",
        "invalid_number": "❌ Số không hợp lệ. VD: {example}",
        "invalid_income_type": "❌ Loại `{type}` không tồn tại. Dùng /income để xem các loại"
    }
}

# =============================================================================
# CATEGORIES - SIMPLIFIED
# =============================================================================

CATEGORIES = {
    "ăn uống": {"emoji": "🍜", "keywords": ["food", "drink", "bún", "phở", "cơm"]},
    "di chuyển": {"emoji": "🚗", "keywords": ["transport", "taxi", "grab", "xăng"]},
    "hóa đơn": {"emoji": "📄", "keywords": ["bill", "điện", "nước", "internet"]},
    "cá nhân": {"emoji": "🎮", "keywords": ["entertainment", "shopping", "áo", "quần"]},
    "mèo": {"emoji": "🐾", "keywords": ["cat", "pet", "mèo", "cát mèo"]},
    "công trình": {"emoji": "🏗️", "keywords": ["furniture", "sofa", "tủ lạnh", "giường"]},
    "linh tinh": {"emoji": "🔧", "keywords": ["small items", "tools", "đèn nhỏ", "ly"]},
    "khác": {"emoji": "📂", "keywords": ["other", "misc"]}
}

EXPENSE_CATEGORIES = list(CATEGORIES.keys())

def get_category_emoji(category):
    return CATEGORIES.get(category, {}).get("emoji", "📂")

def get_all_category_info():
    return "\n".join([f"• {cat} {get_category_emoji(cat)}" for cat in EXPENSE_CATEGORIES])

def get_ai_categorization_rules():
    """Generate simple AI categorization rules"""
    rules = []
    for category, info in CATEGORIES.items():
        keywords = ", ".join(info["keywords"])
        rules.append(f"- For {keywords}, use \"{category}\" category")
    return "\n".join(rules)

# =============================================================================
# WISHLIST PRIORITIES - 5 LEVELS
# =============================================================================

WISHLIST_PRIORITIES = {
    1: {"emoji": "🔒", "name": "Untouchable"},
    2: {"emoji": "🚨", "name": "Next Sale"},
    3: {"emoji": "⚠️", "name": "Want Soon"},
    4: {"emoji": "🔵", "name": "Want Eventually"},
    5: {"emoji": "🌿", "name": "Nice to Have"}
}

def get_priority_emoji(priority):
    return WISHLIST_PRIORITIES.get(priority, {}).get("emoji", "🌿")

def get_priority_name(priority):
    return WISHLIST_PRIORITIES.get(priority, {}).get("name", "Nice to Have")

def get_priority_description(priority):
    descriptions = {
        1: "Essential/committed purchases",
        2: "Planned for next sale/opportunity", 
        3: "Want to buy soon",
        4: "Want to buy eventually",
        5: "Nice to have (lowest priority)"
    }
    return descriptions.get(priority, "Nice to have")

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_message(key, **kwargs):
    message = BOT_MESSAGES.get(key, f"Message '{key}' not found")
    if kwargs:
        return message.format(**kwargs)
    return message

def get_template(key, **kwargs):
    template = MESSAGE_TEMPLATES.get(key, f"Template '{key}' not found")
    if kwargs:
        return template.format(**kwargs)
    return template

# =============================================================================
# STARTUP AND ERROR MESSAGES
# =============================================================================

STARTUP_MESSAGES = {
    "starting": "🤖 Simplified Personal Finance Bot is starting...",
    "categories": "📂 Categories: {categories}",
    "notation": "💰 K/M/TR notation: 50k=50,000đ, 1.5m=1,500,000đ, 3tr=3,000,000đ",
    "wishlist": "📝 Wishlist with 5 levels: 1=Untouchable, 2=Next Sale, 3=Want Soon, 4=Want Eventually, 5=Nice to Have",
    "subscriptions": "📅 Subscription feature: auto-added when calculating summary",
    "budget": "💰 Budget planning: set spending limits per category",
    "summary": "📊 Summary with date: /summary or /summary 8/2025",
    "list_feature": "📝 Enhanced /list command: shows wishlist analysis"
}

ERROR_MESSAGES = {
    "bot_conflict": "❌ Bot conflict error: Another bot instance is running!",
    "solutions": "🔧 Solutions:\n1. Stop other bot instances\n2. Wait 30 seconds and try again\n3. Check if bot is running elsewhere",
    "unexpected": "❌ Unexpected error: {error}",
    "restarting": "🔧 Restarting in 30 seconds..."
}

def get_category_list_display():
    """Get category list for console display"""
    return ", ".join(EXPENSE_CATEGORIES)

def get_startup_message(key, **kwargs):
    """Get a startup message with optional formatting"""
    message = STARTUP_MESSAGES.get(key, f"Startup message '{key}' not found")
    if kwargs:
        return message.format(**kwargs)
    return message

def get_error_message(key, **kwargs):
    """Get an error message with optional formatting"""
    message = ERROR_MESSAGES.get(key, f"Error message '{key}' not found")
    if kwargs:
        return message.format(**kwargs)
    return message

# =============================================================================
# ENVIRONMENT VARIABLES
# =============================================================================

ALLOWED_USERS = [int(uid) for uid in os.getenv("ALLOWED_USERS").split(",")]
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")