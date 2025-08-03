import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configurable categories - edit this list as needed
EXPENSE_CATEGORIES = [
    "ăn uống",      # food & drinks
    "di chuyển",    # transportation  
    "giải trí",     # entertainment
    "mua sắm",      # shopping
    "hóa đơn",      # bills/utilities
    "sức khỏe",     # health/medical
    "giáo dục",     # education
    "gia đình",     # family
    "mèo",          # cat expenses
    "nội thất",     # furniture/home decoration
    "khác"          # other
]

# Allowed users
ALLOWED_USERS = [int(uid) for uid in os.getenv("ALLOWED_USERS").split(",")]

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")