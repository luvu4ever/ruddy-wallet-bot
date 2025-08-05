import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
        "emoji": "🛍️",
        "description": "personal (entertainment + shopping)",
        "ai_keywords": ["entertainment", "shopping", "clothes", "movie", "game", "book", "áo", "quần", "phim"],
        "examples": ["áo sơ mi", "xem phim", "mua sách"]
    },
    "mèo": {
        "emoji": "🐱",
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