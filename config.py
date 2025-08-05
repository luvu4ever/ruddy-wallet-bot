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
    return "\n".join([f"• {itype} {info['emoji']} - {info['description']}" 
                     for itype, info in INCOME_TYPES.items()])

def get_income_emoji(income_type):
    """Get emoji for income type"""
    return INCOME_TYPES.get(income_type, {}).get("emoji", "💰")

# =============================================================================
# TEXT CONFIGURATION - CHANGE MESSAGES HERE
# =============================================================================
BOT_MESSAGES = {
    "welcome": """
🤖 **Chào mừng đến với Bot Tài chính cá nhân!**

**Cách sử dụng:**
• **Chi tiêu**: "50k bún bò huế", "100k cát mèo", "1.5m sofa"
• **Thu nhập**: "/income salary 3m", "/income construction 2m"

**Định dạng tiền:**
• 50k = 50,000đ | 1.5m = 1,500,000đ | 3tr = 3,000,000đ

**Lệnh:**
• /list - Xem chi tiêu tháng này
• /summary - Báo cáo tháng này
• /summary 8/2025 - Báo cáo tháng 8/2025
• /income - Xem loại thu nhập
• /budget ăn uống 1.5m - Đặt budget
• /sublist - Xem subscriptions
• /saving - Xem tiết kiệm
• /wishlist - Xem wishlist
• /help - Hướng dẫn

AI tự động phân loại! 🤖🐾🎮
Subscriptions tự động hàng tháng! 📅
    """,
    
    "help": """
💰 **Hướng dẫn nhanh**

**Ghi chi tiêu:**
• `50k bún bò huế` - ăn uống
• `100k cát mèo` - mèo cưng 🐾
• `1.5m sofa` - công trình 🏗️
• `50k đèn nhỏ` - linh tinh 🔧

**Thu nhập:**
• `/income salary 3m` - lương tháng
• `/income construction 2m` - thu nhập xây dựng
• `/income random 500k` - thu nhập thêm

**Subscriptions:**
• `/subadd Spotify 33k` - thêm subscription
• `/sublist` - xem subscriptions
• `/subremove 1` - xóa subscription

**Budget:**
• `/budget ăn uống 1.5m` - đặt budget
• `/budgetlist` - xem budget plans

**Lệnh:**
• `/list` - xem chi tiêu tháng này
• `/summary` - báo cáo tháng này
• `/summary 8/2025` - báo cáo tháng 8/2025
• `/income` - quản lý thu nhập
• `/saving` - xem tiết kiệm
• `/category` - xem danh mục
• `/wishlist` - xem wishlist

AI tự động phân loại! 🤖
    """,
    
    "unknown_message": "🤔 Tôi không hiểu tin nhắn này. Thử:\n• '50k bún bò huế' (chi tiêu ăn uống)\n• '100k cát mèo' (chi phí mèo)\n• '1.5m sofa' (công trình) hoặc '50k đèn nhỏ' (linh tinh)\n• '/income salary 3m' (thu nhập)\n• '/income construction 2m xây nhà' (thu nhập công trình)",
    
    "unauthorized": "❌ Sorry, you're not authorized to use this bot.",
    
    "no_expenses_this_month": "📝 Không có chi tiêu nào trong tháng {month}/{year}",
    
    "no_budget": "💰 Chưa có budget plan nào!\n\nDùng /budget [category] [amount] để đặt budget\nVí dụ: /budget ăn uống 1.5m",
    
    "no_subscriptions": "📅 Không có subscription nào!\n\nDùng /subadd để thêm subscription\nSubscription sẽ tự động được thêm khi tính /summary",
    
    "no_wishlist": "📝 Wishlist trống!\n\nDùng /wishadd [tên] [giá] để thêm",
    
    "savings_current": "💰 **Tiết kiệm hiện tại**: {amount}\n📅 Cập nhật: {date}",
    
    "savings_none": "💰 **Tiết kiệm hiện tại**: 0đ\n\nDùng /editsaving 500k để đặt số tiền tiết kiệm!",
    
    "subscription_added": "✅ Đã thêm subscription!\n📅 **{name}**: {amount}/tháng\n\n💡 Subscription sẽ tự động được thêm khi tính /summary",
    
    "budget_set": "✅ Đã đặt budget!\n{emoji} **{category}**: {amount}/tháng",
    
    "wishlist_added": "✅ Đã thêm vào wishlist!\n🛍️ **{name}**: {amount}",
    
    "income_added": "✅ Đã thêm thu nhập!\n{emoji} **{type}**: {amount} - {description}",
    
    "income_types": """
💰 **Loại thu nhập:**

{income_types}

**Cách dùng:** /income [type] [amount] [description]
**Ví dụ:** /income salary 3m lương tháng 8
    """,
    
    "format_errors": {
        "summary_date": "❌ Format: /summary 8/2025 hoặc /summary (tháng này)",
        "month_range": "❌ Tháng phải từ 1-12",
        "budget_usage": "❌ Cách dùng: /budget ăn uống 1.5m\nhoặc /budget mèo 500k\nhoặc /budget an uong 1tr (gần giống cũng được)",
        "invalid_amount": "❌ Số tiền không hợp lệ. Ví dụ: /budget ăn uống 1.5m",
        "subscription_usage": "❌ Cách dùng: /subadd Spotify 33k\nhoặc /subadd Netflix 150k\nhoặc /subadd Premium 1.5tr",
        "wishlist_usage": "❌ Cách dùng: /wishadd iPhone 15 Pro 25m",
        "savings_usage": "❌ Cách dùng: /editsaving 500k (để đặt tiết kiệm thành 500k)",
        "invalid_number": "❌ Vui lòng nhập số hợp lệ: {example}",
        "income_usage": "❌ Cách dùng: /income [type] [amount] [description]\nVí dụ: /income salary 3m lương tháng\nDùng /income để xem các loại",
        "invalid_income_type": "❌ Loại thu nhập không hợp lệ: '{type}'\nDùng /income để xem các loại có sẵn"
    }
}

# Console startup messages
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

# Error messages
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
    return "\n".join([f"• {cat} {get_category_emoji(cat)} - {get_category_description(cat)}" 
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