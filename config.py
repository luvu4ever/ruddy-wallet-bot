import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =============================================================================
# BUSINESS LOGIC CONFIGURATION
# =============================================================================

# Default category for subscriptions when auto-added in summary
DEFAULT_SUBSCRIPTION_CATEGORY = "cá nhân"

# Income types configuration
INCOME_TYPES = {
    "construction": {
        "description": "Construction income (for công trình category only)",
        "emoji": "🏗️",
        "target_category": "công trình"
    },
    "salary": {
        "description": "Monthly salary (for all categories except công trình)",
        "emoji": "💵",
        "target_category": "general"
    },
    "random": {
        "description": "Additional income (for all categories except công trình)",
        "emoji": "🎉", 
        "target_category": "general"
    }
}

def get_income_types_list():
    """Get formatted income types for display"""
    return "\n".join([f"• {itype} {info['emoji']} \\- {info['description']}" 
                     for itype, info in INCOME_TYPES.items()])

def get_income_emoji(income_type):
    """Get emoji for income type"""
    return INCOME_TYPES.get(income_type, {}).get("emoji", "💰")

# =============================================================================
# TEXT CONFIGURATION - ENHANCED WITH RICH FORMATTING
# =============================================================================
BOT_MESSAGES = {
    "welcome": """
🤖 *CHÀO MỪNG ĐỾN VỚI BOT TÀI CHÍNH CÁ NHÂN\\!*

*📝 CÁCH SỬ DỤNG:*
• *Chi tiêu*: `50k bún bò huế`, `100k cát mèo`, `1\\.5m sofa`
• *Thu nhập*: `/income salary 3m`, `/income construction 2m`

*💰 ĐỊNH DẠNG TIỀN:*
• `50k` = 50,000đ | `1\\.5m` = 1,500,000đ | `3tr` = 3,000,000đ

*⚡ LỆNH NHANH:*
• `/list` \\- Xem chi tiêu tháng này
• `/summary` \\- Báo cáo tháng này  
• `/summary 8/2025` \\- Báo cáo tháng 8/2025
• `/income` \\- Xem loại thu nhập
• `/budget ăn uống 1\\.5m` \\- Đặt budget
• `/sublist` \\- Xem subscriptions
• `/saving` \\- Xem tiết kiệm
• `/wishlist` \\- Xem wishlist
• `/help` \\- Hướng dẫn

🤖 *AI tự động phân loại\\!* 🐾🎮
📅 *Subscriptions tự động hàng tháng\\!*
    """,
    
    "help": """
💡 *HƯỚNG DẪN NHANH*

*📝 GHI CHI TIÊU:*
• `50k bún bò huế` \\- ăn uống
• `100k cát mèo` \\- mèo cưng 🐾
• `1\\.5m sofa` \\- công trình 🏗️
• `50k đèn nhỏ` \\- linh tinh 🔧

*💵 THU NHẬP:*
• `/income salary 3m` \\- lương tháng
• `/income construction 2m` \\- thu nhập xây dựng
• `/income random 500k` \\- thu nhập thêm

*📅 SUBSCRIPTIONS:*
• `/subadd Spotify 33k` \\- thêm subscription
• `/sublist` \\- xem subscriptions
• `/subremove 1` \\- xóa subscription

*💰 BUDGET:*
• `/budget ăn uống 1\\.5m` \\- đặt budget
• `/budgetlist` \\- xem budget plans

*🔍 LỆNH KHÁC:*
• `/list` \\- xem chi tiêu tháng này
• `/summary` \\- báo cáo tháng này
• `/summary 8/2025` \\- báo cáo tháng 8/2025
• `/income` \\- quản lý thu nhập
• `/saving` \\- xem tiết kiệm
• `/category` \\- xem danh mục
• `/wishlist` \\- xem wishlist

🤖 *AI tự động phân loại\\!*
    """,
    
    "unknown_message": """
🤔 *Tôi không hiểu tin nhắn này\\.*

__Thử các cách sau:__
• `50k bún bò huế` \\(chi tiêu ăn uống\\)
• `100k cát mèo` \\(chi phí mèo\\)  
• `1\\.5m sofa` \\(công trình\\) hoặc `50k đèn nhỏ` \\(linh tinh\\)
• `/income salary 3m` \\(thu nhập\\)
• `/income construction 2m xây nhà` \\(thu nhập công trình\\)
    """,
    
    "unauthorized": "❌ *Sorry, you're not authorized to use this bot\\.*",
    
    "no_expenses_this_month": "📝 *Không có chi tiêu nào trong tháng {month}/{year}*",
    
    "no_budget": """
💰 *Chưa có budget plan nào\\!*

Dùng `/budget [category] [amount]` để đặt budget
*Ví dụ:* `/budget ăn uống 1\\.5m`
    """,
    
    "no_subscriptions": """
📅 *Không có subscription nào\\!*

Dùng `/subadd` để thêm subscription
_Subscription sẽ tự động được thêm khi tính /summary_
    """,
    
    "no_wishlist": """
🛍️ *Wishlist trống\\!*

Dùng `/wishadd [tên] [giá]` để thêm
    """,
    
    "savings_current": """
💰 *TIẾT KIỆM HIỆN TẠI*

`{amount}`
📅 _Cập nhật: {date}_
    """,
    
    "savings_none": """
💰 *TIẾT KIỆM HIỆN TẠI*

`0đ`

Dùng `/editsaving 500k` để đặt số tiền tiết kiệm\\!
    """,
    
    "subscription_added": """
✅ *Đã thêm subscription\\!*

📅 *{name}*: `{amount}/tháng`

💡 _Subscription sẽ tự động được thêm khi tính /summary_
    """,
    
    "budget_set": """
✅ *Đã đặt budget\\!*

{emoji} *{category}*: `{amount}/tháng`
    """,
    
    "wishlist_added": """
✅ *Đã thêm vào wishlist\\!*

🛍️ *{name}*: `{price_text}`{priority_text}
    """,
    
    "income_added": """
✅ *Đã thêm thu nhập\\!*

{emoji} *{type}*: `{amount}` \\- _{description}_
    """,
    
    "income_types": """
💰 *LOẠI THU NHẬP:*

{income_types}

*Cách dùng:* `/income [type] [amount] [description]`
*Ví dụ:* `/income salary 3m lương tháng 8`
    """,
    
    "format_errors": {
        "summary_date": "❌ *Format:* `/summary 8/2025` hoặc `/summary` \\(tháng này\\)",
        "month_range": "❌ *Tháng phải từ 1\\-12*",
        "budget_usage": """
❌ *Cách dùng:*
• `/budget ăn uống 1\\.5m`
• `/budget mèo 500k`  
• `/budget an uong 1tr` \\(gần giống cũng được\\)
        """,
        "invalid_amount": "❌ *Số tiền không hợp lệ\\.*\n_Ví dụ:_ `/budget ăn uống 1\\.5m`",
        "subscription_usage": """
❌ *Cách dùng:*
• `/subadd Spotify 33k`
• `/subadd Netflix 150k`
• `/subadd Premium 1\\.5tr`
        """,
        "wishlist_usage": """
❌ *Cách dùng:*
• `/wishadd iPhone 15 Pro 25m prio:1`
• `/wishadd iPhone` \\(không cần giá\\)

*Priority:* `1=cao🔴`, `2=trung bình🟡`, `3=thấp🟢` \\(mặc định\\)
        """,
        "savings_usage": "❌ *Cách dùng:* `/editsaving 500k` \\(để đặt tiết kiệm thành 500k\\)",
        "invalid_number": "❌ *Vui lòng nhập số hợp lệ:* {example}",
        "income_usage": """
❌ *Cách dùng:* `/income [type] [amount] [description]`
*Ví dụ:* `/income salary 3m lương tháng`
_Dùng /income để xem các loại_
        """,
        "invalid_income_type": """
❌ *Loại thu nhập không hợp lệ:* `{type}`
_Dùng /income để xem các loại có sẵn_
        """
    }
}

# Console startup messages (no changes needed for console)
STARTUP_MESSAGES = {
    "starting": "🤖 Simplified Personal Finance Bot is starting...",
    "categories": "📂 Categories: {categories}",
    "notation": "💰 K/M/TR notation: 50k=50,000đ, 1.5m=1,500,000đ, 3tr=3,000,000đ",
    "wishlist": "📝 Simple wishlist: add, view, remove",
    "subscriptions": "📅 Subscription feature: auto-added when calculating summary",
    "budget": "💰 Budget planning: set spending limits per category",
    "summary": "📊 Summary with date: /summary or /summary 8/2025",
    "list_feature": "📝 New feature: /list command to view all monthly expenses by category"
}

# Error messages (no changes needed for console)
ERROR_MESSAGES = {
    "bot_conflict": "❌ Bot conflict error: Another bot instance is running!",
    "solutions": "🔧 Solutions:\n1. Stop other bot instances\n2. Wait 30 seconds and try again\n3. Check if bot is running elsewhere",
    "unexpected": "❌ Unexpected error: {error}",
    "restarting": "🔧 Restarting in 30 seconds..."
}

# Functions to get messages
def get_message(key, **kwargs):
    """Get a configured message with optional formatting"""
    message = BOT_MESSAGES.get(key, f"Message '{key}' not found")
    if kwargs:
        return message.format(**kwargs)
    return message

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
# CATEGORY CONFIGURATION - CHANGE EVERYTHING HERE
# =============================================================================
CATEGORIES = {
    "ăn uống": {
        "emoji": "🍜",
        "description": "food & drinks",
        "ai_keywords": ["food", "drink", "restaurant", "coffee", "bún", "phở", "cơm", "nước"],
        "examples": ["bún bò huế", "cà phê", "cơm trưa"]
    },
    "di chuyển": {
        "emoji": "🚗",
        "description": "transportation",
        "ai_keywords": ["transport", "taxi", "bus", "fuel", "xe ôm", "grab", "xăng", "vé xe"],
        "examples": ["xe ôm", "xăng xe", "vé bus"]
    },
    "hóa đơn": {
        "emoji": "📄",
        "description": "bills & utilities",
        "ai_keywords": ["bill", "utility", "rent", "insurance", "điện", "nước", "internet", "thuê nhà"],
        "examples": ["tiền điện", "tiền nước", "thuê nhà"]
    },
    "cá nhân": {
        "emoji": "🎮",
        "description": "personal (entertainment + shopping)",
        "ai_keywords": ["entertainment", "shopping", "clothes", "movie", "game", "book", "áo", "quần", "phim"],
        "examples": ["áo sơ mi", "xem phim", "mua sách"]
    },
    "mèo": {
        "emoji": "🐾",
        "description": "cat expenses",
        "ai_keywords": ["cat", "pet", "mèo", "cát mèo", "thức ăn mèo", "thuốc mèo"],
        "examples": ["cát mèo", "thức ăn mèo", "thuốc mèo"]
    },
    "công trình": {
        "emoji": "🏗️",
        "description": "large furniture/construction items",
        "ai_keywords": ["large furniture", "construction", "sofa", "tủ lạnh", "giường", "bàn lớn", "renovation"],
        "examples": ["sofa da", "tủ lạnh", "giường ngủ"]
    },
    "linh tinh": {
        "emoji": "🔧",
        "description": "small miscellaneous items",
        "ai_keywords": ["small items", "tools", "accessories", "đèn nhỏ", "ly tách", "dao kéo", "dụng cụ"],
        "examples": ["đèn ngủ", "ly tách", "dao kéo"]
    },
    "khác": {
        "emoji": "📂",
        "description": "other",
        "ai_keywords": ["other", "misc", "khác"],
        "examples": ["các khoản khác"]
    }
}

# Derived data - auto-generated from CATEGORIES
EXPENSE_CATEGORIES = list(CATEGORIES.keys())

# Helper functions
def get_category_emoji(category):
    """Get emoji for category"""
    return CATEGORIES.get(category, {}).get("emoji", "📂")

def get_category_description(category):
    """Get description for category"""
    return CATEGORIES.get(category, {}).get("description", "unknown")

def get_category_examples(category):
    """Get examples for category"""
    return CATEGORIES.get(category, {}).get("examples", [])

def get_all_category_info():
    """Get formatted category info for display"""
    return "\n".join([f"• {cat} {get_category_emoji(cat)} \\- {get_category_description(cat)}" 
                     for cat in EXPENSE_CATEGORIES])

def get_ai_categorization_rules():
    """Generate AI categorization rules from config"""
    rules = []
    for category, info in CATEGORIES.items():
        keywords = ", ".join(info["ai_keywords"])
        rules.append(f"- For {info['description']} ({keywords}), use \"{category}\" category")
    return "\n".join(rules)

def get_category_list_display():
    """Get category list for console display"""
    return ", ".join(EXPENSE_CATEGORIES)

# Wishlist priority configuration  
WISHLIST_PRIORITIES = {
    1: {"emoji": "🚨", "name": "Cao", "color": "đỏ"},      # 1 = high priority
    2: {"emoji": "⚠️", "name": "Trung bình", "color": "vàng"}, # 2 = medium priority
    3: {"emoji": "🌿", "name": "Thấp", "color": "xanh"}     # 3 = low priority  
}

def get_priority_emoji(priority):
    """Get emoji for wishlist priority"""
    return WISHLIST_PRIORITIES.get(priority, {}).get("emoji", "🟢")

def get_priority_name(priority):
    """Get name for wishlist priority"""
    return WISHLIST_PRIORITIES.get(priority, {}).get("name", "Thấp")

# =============================================================================
# OTHER CONFIGURATION
# =============================================================================

# Allowed users
ALLOWED_USERS = [int(uid) for uid in os.getenv("ALLOWED_USERS").split(",")]

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")