import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_SUBSCRIPTION_CATEGORY = "cá nhân"

INCOME_TYPES = {
    "mama": {"emoji": "✅", "description": "Mama income"},    
    "salary": {"emoji": "💵", "description": "Monthly salary"},
    "random": {"emoji": "🎉", "description": "Additional income"}
}

def get_income_emoji(income_type):
    return INCOME_TYPES.get(income_type, {}).get("emoji", "💰")

MESSAGE_TEMPLATES = {
    "list_overview": """📋 *THÁNG {month}/{year}*
📅 {date_range}

{categories_content}

💰 *TỔNG: {total}*

💵 Thu: `{mama_income}` + `{general_income}`
💸 Chi: `{mama_expense}` + `{general_expense}` 
📈 Tiết kiệm: `{mama_net}` + `{general_net}`{wishlist_section}""",

    "summary_report": """📊 *BÁO CÁO {month}/{year}*
📅 {date_range}{subscription_info}

💵 Thu: `{total_income}`
💰 Chi: `{total_expenses}` 
📈 Tiết kiệm: `{net_savings}`

🗯️ Mama: Thu `{mama_income}` - Chi `{mama_expense}` = `{mama_net}`
💰 Khác: Thu `{general_income}` - Chi `{general_expense}` = `{general_net}`{budget_info}

📊 {expense_count} chi tiêu, {income_count} thu nhập""",

    "savings_update": """✅ *CẬP NHẬT TIẾT KIỆM*

💰 {amount}""",

    "expense_item": """{date} {description} `{amount}`""",
    
    "category_header": """{emoji} *{category}* - `{total}`{budget_info}""",
    "more_items": """_... +{count} giao dịch_""",
    
    "budget_section": """
💰 *BUDGET:*
💰 Budget tháng: `{budget_total}`
{budget_status} {status_text}: `{amount}`"""
}

def format_budget_info(remaining_budget, category):
    from utils import format_currency
    
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
    from utils import format_currency
    
    amount = float(expense["amount"])
    description = expense["description"]
    
    date_obj = datetime.strptime(expense["date"], "%Y-%m-%d")
    date_str = f"{date_obj.day:02d}/{date_obj.month:02d}"
    
    return MESSAGE_TEMPLATES["expense_item"].format(
        date=date_str,
        description=description,
        amount=format_currency(amount)
    )

BOT_MESSAGES = {
    "welcome": """🤖 *CHÀO MỪNG!*

*📝 SỬ DỤNG:*
• `50k cà phê` → ghi chi tiêu
• `/income salary 3m` → thu nhập

*⚡ LỆNH:*
📊 `/list` - Tổng quan
📊 `/list ăn uống` - Chi tiết danh mục
📊 `/list 15/08/2025` - Chi tiêu ngày
📈 `/summary` - Báo cáo tháng
💰 `/budget ăn uống 1.5m` - Đặt budget
🛍️ `/wishlist` - Wishlist
❓ `/help` - Hướng dẫn""",
    
    "help": """💡 *HƯỚNG DẪN*

*📝 CHI TIÊU:*
• `50k bún bò`, `1.5m sofa`

*💵 THU NHẬP:*
• `/income salary 3m`
• `/income mama 2m`

*📊 XEM:*
• `/list` - Tổng quan
• `/list ăn uống` - Chi tiết danh mục  
• `/list 15/08/2025` - Chi tiêu ngày
• `/summary` - Báo cáo tháng

*💰 QUẢN LÝ:*
• `/budget ăn uống 1.5m` - Đặt budget
• `/account` - Xem tài khoản
• `/allocation` - Phân bổ thu nhập

*🛍️ WISHLIST:*
• `/wishadd iPhone 25m prio:1` - Thêm
• `/wishlist` - Xem + phân tích
• `/wishremove iPhone` - Xóa

*📅 THÁNG:* 1-31 (T8 = 1/8-31/8)""",
    
    "no_expenses_this_month": """📋 Tháng {month}/{year}

Chưa có chi tiêu nào.""",
    
    "savings_current": """💰 *TIẾT KIỆM*

💎 {amount}
📅 {date}""",
    
    "savings_none": """💰 Chưa có tiết kiệm.
Dùng `/editsaving 500k` để bắt đầu.""",
    
    "unknown_message": """❓ Không hiểu tin nhắn.

VD: `50k cà phê`, `/help`"""
}

CATEGORIES = {
    "ăn uống": {"emoji": "🍜", "keywords": ["food", "drink", "bún", "phở", "cơm"]},
    "di chuyển": {"emoji": "🚗", "keywords": ["transport", "taxi", "grab", "xăng"]},
    "hóa đơn": {"emoji": "📄", "keywords": ["bill", "điện", "nước", "internet"]},
    "cá nhân": {"emoji": "🎮", "keywords": ["entertainment", "shopping", "áo", "quần"]},
    "mèo": {"emoji": "🐾", "keywords": ["cat", "pet", "mèo", "cát mèo"]},
    "mama": {"emoji": "✅", "keywords": ["mama", "big items", "furniture"]},
    "linh tinh": {"emoji": "🔧", "keywords": ["small items", "tools", "đèn nhỏ", "ly"]},
    "khác": {"emoji": "📂", "keywords": ["other", "misc"]}
}

EXPENSE_CATEGORIES = list(CATEGORIES.keys())

def get_category_emoji(category):
    return CATEGORIES.get(category, {}).get("emoji", "📂")

def get_all_category_info():
    return "\n".join([f"• {cat} {get_category_emoji(cat)}" for cat in EXPENSE_CATEGORIES])

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

ACCOUNT_TYPES = {
    "expense": {"emoji": "💸", "description": "Chi tiêu"},
    "saving": {"emoji": "💰", "description": "Tiết kiệm"},
    "invest": {"emoji": "📈", "description": "Đầu tư"},
    "mama": {"emoji": "✅", "description": "Mama"} 
}

def get_account_emoji(account_type):
    return ACCOUNT_TYPES.get(account_type, {}).get("emoji", "💳")

def get_account_description(account_type):
    return ACCOUNT_TYPES.get(account_type, {}).get("description", "Tài khoản")

def get_all_account_types():
    return list(ACCOUNT_TYPES.keys())

ACCOUNT_DESCRIPTIONS = {
    "need": {"emoji": "🏠", "name": "Thiết yếu", "description": "Ăn uống, di chuyển, hóa đơn, mèo"},
    "fun": {"emoji": "🎮", "name": "Giải trí", "description": "Cá nhân, linh tinh"},
    "saving": {"emoji": "💰", "name": "Tiết kiệm", "description": "Tiết kiệm tích lũy"},
    "invest": {"emoji": "📈", "name": "Đầu tư", "description": "Đầu tư dài hạn"},
    "mama": {"emoji": "✅", "name": "Mama", "description": "Thu chi mama"}
}

def get_account_description_enhanced(account_type):
    return ACCOUNT_DESCRIPTIONS.get(account_type, {}).get("description", "Tài khoản")

def get_account_name_enhanced(account_type):
    return ACCOUNT_DESCRIPTIONS.get(account_type, {}).get("name", account_type.title())

def get_account_emoji_enhanced(account_type):
    return ACCOUNT_DESCRIPTIONS.get(account_type, {}).get("emoji", "💳")

CATEGORY_TO_ACCOUNT = {
    "ăn uống": "need",
    "di chuyển": "need", 
    "hóa đơn": "need",
    "mèo": "need",
    "cá nhân": "fun",
    "linh tinh": "fun",
    "mama": "mama",
    "khác": "fun"
}

def get_account_for_category(category):
    return CATEGORY_TO_ACCOUNT.get(category, "fun")

def get_categories_for_account(account_type):
    return [cat for cat, acc in CATEGORY_TO_ACCOUNT.items() if acc == account_type]

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

STARTUP_MESSAGES = {
    "starting": "🤖 Simplified Personal Finance Bot is starting...",
    "categories": "📂 Categories: {categories}",
    "notation": "💰 K/M/TR notation: 50k=50,000₫, 1.5m=1,500,000₫, 3tr=3,000,000₫",
    "wishlist": "📋 Wishlist with 5 levels: 1=Untouchable, 2=Next Sale, 3=Want Soon, 4=Want Eventually, 5=Nice to Have",
    "subscriptions": "📅 Subscription feature: auto-added on 1st of each month",
    "budget": "💰 Budget planning: set spending limits per category",
    "calendar_month": "📅 Calendar months: Each month runs 1st-last day (Month 8 = Aug 1 - Aug 31)",
    "summary": "📊 Summary with calendar months: /summary or /summary 8/2025 (1/8-31/8/2025)",
    "list_feature": "📋 Enhanced /list command: shows wishlist analysis for calendar month"
}

ERROR_MESSAGES = {
    "bot_conflict": "⛔ Bot conflict error: Another bot instance is running!",
    "solutions": "🔧 Solutions:\n1. Stop other bot instances\n2. Wait 30 seconds and try again\n3. Check if bot is running elsewhere",
    "unexpected": "⛔ Unexpected error: {error}",
    "restarting": "🔧 Restarting in 30 seconds..."
}

def get_startup_message(key, **kwargs):
    message = STARTUP_MESSAGES.get(key, f"Startup message '{key}' not found")
    if kwargs:
        return message.format(**kwargs)
    return message

def get_error_message(key, **kwargs):
    message = ERROR_MESSAGES.get(key, f"Error message '{key}' not found")
    if kwargs:
        return message.format(**kwargs)
    return message

ALLOWED_USERS = [int(uid) for uid in os.getenv("ALLOWED_USERS").split(",")]
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")