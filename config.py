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
# MESSAGE TEMPLATES - ALL FORMATTING HERE
# =============================================================================

# Message templates for different scenarios
MESSAGE_TEMPLATES = {
    "list_overview": """📝 *CHI TIÊU THÁNG {month}/{year}*

{categories_content}

💰 *TỔNG CỘNG: {total}*

📊 *PHÂN TÍCH THU CHI:*
🏗️ *CÔNG TRÌNH:* Thu `{construction_income}` - Chi `{construction_expense}` = `{construction_net}`
💰 *KHÁC:* Thu `{general_income}` - Chi `{general_expense}` = `{general_net}`

💡 _Dùng `/list [danh mục]` để xem tất cả giao dịch của danh mục_""",

    "category_header": """{emoji} *{category}* - `{total}`{budget_info}""",
    
    "expense_item": """  {date} - {description} - `{amount}`""",
    
    "more_items": """  _... và {count} giao dịch khác_""",
    
    "category_full": """{emoji} *TẤT CẢ CHI TIÊU {category}*

📊 *Tháng {month}/{year}*

{expenses_list}

💰 *Tổng cộng:* `{total}`
📊 *Số giao dịch:* {count} lần""",

    "category_empty": """📂 *KHÔNG CÓ CHI TIÊU*

{emoji} *{category} - {month}/{year}*

Không có chi tiêu nào cho danh mục này trong tháng {month}/{year}

💡 _Thử danh mục khác hoặc tháng khác_""",

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

    "category_summary": """{emoji} *CHI TIÊU {category}*

📊 *Tháng {month}/{year}*

{summary_lines}

💰 *TỔNG CỘNG: {total}*""",

    "savings_update": """✅ *ĐÃ CẬP NHẬT TIẾT KIỆM!*

💎 *TIẾT KIỆM MỚI*
💰 *Số tiền:* {amount}""",
}

# Budget info formatting
def format_budget_info(remaining_budget, category):
    """Format budget information for a category"""
    if category not in remaining_budget:
        return ""
    
    budget_data = remaining_budget[category]
    remaining = budget_data["remaining"]
    
    if remaining >= 0:
        return f" _(còn lại: {format_currency(remaining)})_"
    else:
        return f" _⚠️ (vượt: {format_currency(abs(remaining))})_"

def format_expense_item(expense, date_format="day_month"):
    """Format individual expense item"""
    from datetime import datetime
    
    amount = float(expense["amount"])
    description = expense["description"]
    
    if date_format == "day_month":
        date_obj = datetime.strptime(expense["date"], "%Y-%m-%d")
        date_str = f"{date_obj.day:02d}/{date_obj.month:02d}"
    else:
        date_str = expense["date"][5:10]  # MM-DD format
    
    return MESSAGE_TEMPLATES["expense_item"].format(
        date=date_str,
        description=description,
        amount=format_currency(amount)
    )

def format_currency(amount: float) -> str:
    """Format currency in Vietnamese style"""
    return f"{amount:,.0f}đ"

# =============================================================================
# ORIGINAL BOT MESSAGES - ENHANCED WITH CLEAN FORMATTING
# =============================================================================
BOT_MESSAGES = {
    "welcome": """🤖 *CHÀO MỪNG ĐẾN VỚI BOT TÀI CHÍNH CÁ NHÂN!*

*📝 CÁCH SỬ DỤNG:*
• *Chi tiêu:* `50k bún bò huế`, `100k cát mèo`, `1.5m sofa`
• *Thu nhập:* `/income salary 3m`, `/income construction 2m`

*💰 ĐỊNH DẠNG TIỀN:*
• `50k` = 50,000đ | `1.5m` = 1,500,000đ | `3tr` = 3,000,000đ

*⚡ LỆNH NHANH:*
📊 `/list` - Top 8 chi tiêu theo danh mục + budget
📈 `/summary` - Báo cáo tháng này
📅 `/summary 8/2025` - Báo cáo tháng 8/2025
💵 `/income` - Xem loại thu nhập
💰 `/budget ăn uống 1.5m` - Đặt budget
📅 `/sublist` - Xem subscriptions
💎 `/saving` - Xem tiết kiệm
🛍️ `/wishlist` - Xem wishlist
❓ `/help` - Hướng dẫn

*🔍 XEM CHI TIẾT DANH MỤC:*
📋 `/list ăn uống` - Tất cả chi tiêu ăn uống tháng này
📋 `/list mèo 8/2025` - Tất cả chi tiêu mèo tháng 8/2025

🤖 *AI tự động phân loại!* 🐾🎮
📅 *Subscriptions tự động hàng tháng!*""",
    
    "help": """💡 *HƯỚNG DẪN CHI TIẾT*

*📝 GHI CHI TIÊU:*
🍜 `50k bún bò huế` → ăn uống
🐾 `100k cát mèo` → mèo cưng
🏗️ `1.5m sofa` → công trình
🔧 `50k đèn nhỏ` → linh tinh

*💵 THU NHẬP:*
💰 `/income salary 3m` → lương tháng
🏗️ `/income construction 2m` → thu nhập xây dựng
🎉 `/income random 500k` → thu nhập thêm

*📅 SUBSCRIPTIONS:*
➕ `/subadd Spotify 33k` → thêm subscription
📋 `/sublist` → xem subscriptions
❌ `/subremove 1` → xóa subscription

*💰 BUDGET:*
💰 `/budget ăn uống 1.5m` → đặt budget
📊 `/budgetlist` → xem budget plans

*🔍 XEM CHI TIÊU:*
📊 `/list` → top 8 chi tiêu theo danh mục
📈 `/summary` → báo cáo tháng này
📅 `/summary 8/2025` → báo cáo tháng 8/2025
📋 `/list ăn uống` → tất cả chi tiêu ăn uống tháng này
📋 `/list mèo 8/2025` → tất cả chi tiêu mèo tháng 8/2025

*🔍 LỆNH KHÁC:*
💵 `/income` → quản lý thu nhập
💎 `/saving` → xem tiết kiệm
📂 `/category` → xem danh mục
🛍️ `/wishlist` → xem wishlist

🤖 *AI tự động phân loại!*""",
    
    "unknown_message": """❓ *Tôi không hiểu tin nhắn này.*

*💡 THỬ CÁC CÁCH SAU:*

🍜 `50k bún bò huế` _(chi tiêu ăn uống)_
🐾 `100k cát mèo` _(chi phí mèo)_  
🏗️ `1.5m sofa` _(công trình)_
🔧 `50k đèn nhỏ` _(linh tinh)_
💵 `/income salary 3m` _(thu nhập)_
🏗️ `/income construction 2m xây nhà` _(thu nhập công trình)_""",
    
    "unauthorized": """❌ *KHÔNG CÓ QUYỀN TRUY CẬP*

🚫 Bạn không có quyền sử dụng bot này.""",
    
    "no_expenses_this_month": """📝 *KHÔNG CÓ CHI TIÊU NÀO*

📊 *Tháng {month}/{year}*

Chưa có giao dịch nào được ghi nhận.

💡 Hãy thử ghi chi tiêu: `50k bún bò huế`""",
    
    "no_budget": """💰 *CHƯA CÓ BUDGET PLAN NÀO!*

*💡 CÁCH ĐẶT BUDGET:*

*Cú pháp:* `/budget [category] [amount]`

*Ví dụ:*
• `/budget ăn uống 1.5m`
• `/budget mèo 500k`
• `/budget công trình 5m`""",
    
    "no_subscriptions": """📅 *KHÔNG CÓ SUBSCRIPTION NÀO!*

*💡 CÁCH THÊM SUBSCRIPTION:*

*Cú pháp:* `/subadd [tên] [giá]`

*Ví dụ:*
• `/subadd Spotify 33k`
• `/subadd Netflix 150k`
• `/subadd Disney+ 79k`

💡 _Subscription sẽ tự động được thêm khi tính /summary_""",
    
    "no_wishlist": """🛍️ *WISHLIST TRỐNG!*

*💡 CÁCH THÊM WISHLIST:*

*Cú pháp:* `/wishadd [tên] [giá] [priority]`

*Ví dụ:*
• `/wishadd iPhone 15 Pro 25m prio:1` _(cao)_
• `/wishadd MacBook prio:2` _(trung bình)_
• `/wishadd AirPods` _(thấp - mặc định)_

🚨 *Priority:* `1=cao`, `2=trung bình`, `3=thấp`""",
    
    "savings_current": """💎 *TIẾT KIỆM HIỆN TẠI*

💰 *SỐ DƯ HIỆN TẠI*
*{amount}*

📅 _Cập nhật lần cuối: {date}_""",
    
    "savings_none": """💎 *TIẾT KIỆM HIỆN TẠI*

💰 *SỐ DƯ HIỆN TẠI*
*0đ*

*💡 CÁCH CẬP NHẬT:*
Dùng `/editsaving 500k` để đặt số tiền tiết kiệm!""",
    
    "subscription_added": """✅ *ĐÃ THÊM SUBSCRIPTION!*

📅 *SUBSCRIPTION MỚI*
📅 *Tên:* {name}
💰 *Giá:* {amount}/tháng

💡 _Subscription sẽ tự động được thêm khi tính /summary_""",
    
    "budget_set": """✅ *ĐÃ ĐẶT BUDGET!*

💰 *BUDGET MỚI*
{emoji} *Danh mục:* {category}
💰 *Ngân sách:* {amount}/tháng""",
    
    "wishlist_added": """✅ *ĐÃ THÊM VÀO WISHLIST!*

🛍️ *WISHLIST MỚI*
🛍️ *Tên:* {name}
💰 *Giá:* {price_text}{priority_text}""",
    
    "income_added": """✅ *ĐÃ THÊM THU NHẬP!*

💵 *THU NHẬP MỚI*
{emoji} *Loại:* {type}
💰 *Số tiền:* {amount}
📝 *Mô tả:* {description}""",
    
    "income_types": """💰 *CÁC LOẠI THU NHẬP*

💵 *LOẠI THU NHẬP*

{income_types}

*💡 CÁCH SỬ DỤNG*

*Cú pháp:* `/income [type] [amount] [description]`
*Ví dụ:* `/income salary 3m lương tháng 8`""",
    
    "format_errors": {
        "summary_date": """❌ *ĐỊNH DẠNG NGÀY KHÔNG ĐÚNG*

*💡 CÁCH DÙNG ĐÚNG:*
• `/summary` _(tháng này)_
• `/summary 8/2025` _(tháng 8/2025)_""",
        
        "month_range": """❌ *THÁNG KHÔNG HỢP LỆ*

🗓️ *LƯU Ý:* Tháng phải từ *1-12*""",
        
        "budget_usage": """❌ *CÁCH DÙNG BUDGET KHÔNG ĐÚNG*

*💡 CÚ PHÁP ĐÚNG:*
• `/budget ăn uống 1.5m`
• `/budget mèo 500k`  
• `/budget an uong 1tr` _(gần giống cũng được)_""",
        
        "invalid_amount": """❌ *SỐ TIỀN KHÔNG HỢP LỆ*

*💡 VÍ DỤ ĐÚNG:* `/budget ăn uống 1.5m`""",
        
        "subscription_usage": """❌ *CÁCH DÙNG SUBSCRIPTION KHÔNG ĐÚNG*

*💡 CÚ PHÁP ĐÚNG:*
• `/subadd Spotify 33k`
• `/subadd Netflix 150k`
• `/subadd Premium 1.5tr`""",
        
        "wishlist_usage": """❌ *CÁCH DÙNG WISHLIST KHÔNG ĐÚNG*

*💡 CÚ PHÁP ĐÚNG:*
• `/wishadd iPhone 15 Pro 25m prio:1`
• `/wishadd iPhone` _(không cần giá)_

🚨 *PRIORITY:*
`1` = cao 🔴 | `2` = trung bình 🟡 | `3` = thấp 🟢 _(mặc định)_""",
        
        "savings_usage": """❌ *CÁCH DÙNG SAVINGS KHÔNG ĐÚNG*

*💡 CÚ PHÁP ĐÚNG:*
`/editsaving 500k` _(để đặt tiết kiệm thành 500k)_""",
        
        "invalid_number": """❌ *SỐ KHÔNG HỢP LỆ*

*💡 VÍ DỤ ĐÚNG:* {example}""",
        
        "income_usage": """❌ *CÁCH DÙNG INCOME KHÔNG ĐÚNG*

*💡 CÚ PHÁP ĐÚNG:*
*Cú pháp:* `/income [type] [amount] [description]`
*Ví dụ:* `/income salary 3m lương tháng`

💡 _Dùng /income để xem các loại_""",
        
        "invalid_income_type": """❌ *LOẠI THU NHẬP KHÔNG HỢP LỆ*

❌ *LỖI:* Loại `{type}` không tồn tại.

💡 _Dùng /income để xem các loại có sẵn_"""
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
    "list_feature": "📝 Enhanced /list command: top 8 recent expenses per category or full category view"
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

def get_template(key, **kwargs):
    """Get a message template with formatting"""
    template = MESSAGE_TEMPLATES.get(key, f"Template '{key}' not found")
    if kwargs:
        return template.format(**kwargs)
    return template

# =============================================================================
# CATEGORY CONFIGURATION
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