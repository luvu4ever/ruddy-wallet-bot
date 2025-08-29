from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, date
from collections import defaultdict
import re
import logging

from database import db
from utils import (
    check_authorization, send_formatted_message, send_long_message,
    get_current_month, get_month_date_range, get_month_display,
    format_currency
)
from config import (
    EXPENSE_CATEGORIES, get_category_emoji
)

def format_expense_item_simple(expense):
    """Simple expense formatting without templates"""
    amount = float(expense["amount"])
    description = expense["description"]
    
    date_obj = datetime.strptime(expense["date"], "%Y-%m-%d")
    date_str = f"{date_obj.day:02d}/{date_obj.month:02d}"
    
    return f"{date_str} {description} `{format_currency(amount)}`"

async def list_expenses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced /list command with multiple modes:
    - /list - Overview of all categories
    - /list [category] - Category details for this month
    - /list dd/mm/yyyy - All expenses for specific date
    - /list [category] dd/mm/yyyy - Category expenses for specific date
    """
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        # Original behavior - show all categories overview
        await _show_all_categories_expenses(update, user_id)
        return
    
    # Parse arguments to determine mode
    parsed_args = _parse_list_arguments(args)
    
    if parsed_args["mode"] == "invalid":
        await send_formatted_message(update, parsed_args["error_message"])
        return
    
    # Handle different modes
    if parsed_args["mode"] == "category_month":
        await _show_category_expenses_for_month(
            update, user_id, parsed_args["category"], 
            parsed_args["month"], parsed_args["year"]
        )
    elif parsed_args["mode"] == "date_all":
        await _show_all_expenses_for_date(
            update, user_id, parsed_args["target_date"]
        )
    elif parsed_args["mode"] == "category_date":
        await _show_category_expenses_for_date(
            update, user_id, parsed_args["category"], parsed_args["target_date"]
        )

def _parse_list_arguments(args):
    """Parse /list command arguments to determine mode and extract parameters"""
    
    # Join all args to work with
    args_text = " ".join(args).strip()
    
    # Date patterns - support multiple formats
    date_patterns = [
        r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b',     # dd/mm/yyyy
        r'\b(\d{1,2})/(\d{1,2})/(\d{2})\b',      # dd/mm/yy  
        r'\b(\d{1,2})-(\d{1,2})-(\d{4})\b',      # dd-mm-yyyy
        r'\b(\d{1,2})-(\d{1,2})-(\d{2})\b',      # dd-mm-yy
        r'\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b',    # dd.mm.yyyy
        r'\b(\d{1,2})\.(\d{1,2})\.(\d{2})\b',    # dd.mm.yy
    ]
    
    # Try to find date in arguments
    found_date = None
    date_match = None
    
    for pattern in date_patterns:
        match = re.search(pattern, args_text)
        if match:
            day, month, year = match.groups()
            
            try:
                day = int(day)
                month = int(month)
                year = int(year)
                
                # Handle 2-digit years
                if year < 100:
                    if year <= 30:  # Assume 2000s
                        year += 2000
                    else:  # Assume 1900s
                        year += 1900
                
                # Validate date
                if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100:
                    try:
                        found_date = date(year, month, day)
                        date_match = match
                        break
                    except ValueError:
                        continue  # Invalid date like 31/02
                        
            except ValueError:
                continue
    
    # Remove date from args_text to get category
    if found_date and date_match:
        category_text = args_text.replace(date_match.group(), '').strip()
    else:
        category_text = args_text.strip()
    
    # Find matching category if category_text exists
    matched_category = None
    if category_text:
        matched_category = _find_matching_category(category_text)
        
        if not matched_category:
            return {
                "mode": "invalid",
                "error_message": f"""⛔ Không tìm thấy danh mục: `{category_text}`

📂 Có sẵn: {", ".join(EXPENSE_CATEGORIES[:6])}...

VD: `/list ăn uống`, `/list 15/08/2025`"""
            }
    
    # Determine mode based on what we found
    if found_date and matched_category:
        return {
            "mode": "category_date",
            "category": matched_category,
            "target_date": found_date
        }
    elif found_date and not matched_category:
        return {
            "mode": "date_all", 
            "target_date": found_date
        }
    elif matched_category and not found_date:
        # Category for current calendar month
        current_month, current_year = get_current_month()
        return {
            "mode": "category_month",
            "category": matched_category,
            "month": current_month,
            "year": current_year
        }
    else:
        return {
            "mode": "invalid",
            "error_message": f"""⛔ Cách dùng:
• `/list` - Tổng quan
• `/list ăn uống` - Chi tiết danh mục  
• `/list 15/08/2025` - Chi tiêu ngày"""
        }

async def _show_category_expenses_for_month(update: Update, user_id: int, category: str, target_month: int, target_year: int):
    """Show all expenses for specific category in calendar month"""
    
    # Get expenses for this category and calendar month
    month_start, month_end = get_month_date_range(target_year, target_month)
    expenses = db.get_expenses_by_category(user_id, category, month_start)
    
    if not expenses.data:
        category_emoji = get_category_emoji(category)
        date_range = get_month_display(target_year, target_month)
        message = f"""📂 {category_emoji} *{category.upper()}*

📅 Tháng {target_month}/{target_year} ({date_range})

Không có chi tiêu nào."""
        await send_formatted_message(update, message)
        return
    
    # Get budget and account info
    try:
        from .budget_handlers import calculate_remaining_budget
        remaining_budget = calculate_remaining_budget(user_id, month_start)
    except ImportError:
        remaining_budget = {}
    
    from config import get_account_for_category
    account_type = get_account_for_category(category)
    account_balance = db.get_account_balance(user_id, account_type)
    
    # Calculate total spent
    total_spent = sum(float(expense["amount"]) for expense in expenses.data)
    
    # Budget status (detailed)
    budget_info = ""
    if category in remaining_budget:
        budget_data = remaining_budget[category]
        budget_amount = budget_data["budget"]
        spent_amount = budget_data["spent"]
        remaining = budget_data["remaining"]
        
        # Calculate percentage used
        percentage_used = (spent_amount / budget_amount * 100) if budget_amount > 0 else 0
        
        if remaining >= 0:
            budget_info = f"""
💰 *BUDGET THÁNG:*
  • Tổng budget: `{format_currency(budget_amount)}`
  • Đã dùng: `{format_currency(spent_amount)}` ({percentage_used:.1f}%)
  • Còn lại: `{format_currency(remaining)}`"""
        else:
            budget_info = f"""
💰 *BUDGET THÁNG:*
  • Tổng budget: `{format_currency(budget_amount)}`
  • Đã dùng: `{format_currency(spent_amount)}` ({percentage_used:.1f}%)
  • ⚠️ Vượt budget: `{format_currency(abs(remaining))}`"""
    else:
        budget_info = f"\n💡 *Chưa đặt budget cho {category}*\nDùng `/budget {category} [số tiền]` để đặt budget"
    
    # Sort expenses by date (newest first)
    sorted_expenses = sorted(expenses.data, key=lambda x: x["date"], reverse=True)
    expense_lines = [format_expense_item_simple(expense) for expense in sorted_expenses]
    
    category_emoji = get_category_emoji(category)
    date_range = get_month_display(target_year, target_month)
    
    message = f"""{category_emoji} *{category.upper()}*

📅 {date_range}
💳 Tài khoản: `{format_currency(account_balance)}`{budget_info}

{chr(10).join(expense_lines)}

💰 Tổng: `{format_currency(total_spent)}` ({len(sorted_expenses)} giao dịch)"""
    
    await send_long_message(update, message)

async def _show_all_expenses_for_date(update: Update, user_id: int, target_date: date):
    """Show all expenses for a specific date"""
    
    # Get all expenses for the target date
    expenses_data = db.supabase.table("expenses").select("*").eq("user_id", user_id).eq("date", target_date.isoformat()).execute()
    
    formatted_date = target_date.strftime("%d/%m/%Y")
    weekday = target_date.strftime("%A")
    vietnamese_weekdays = {
        "Monday": "T2", "Tuesday": "T3", "Wednesday": "T4", 
        "Thursday": "T5", "Friday": "T6", "Saturday": "T7", "Sunday": "CN"
    }
    vn_weekday = vietnamese_weekdays.get(weekday, weekday)
    
    if not expenses_data.data:
        message = f"""📅 *{formatted_date} ({vn_weekday})*

Không có chi tiêu nào."""
        await send_formatted_message(update, message)
        return
    
    # Group expenses by category
    expenses_by_category = defaultdict(list)
    total_day = 0
    
    for expense in expenses_data.data:
        category = expense["category"]
        amount = float(expense["amount"])
        expenses_by_category[category].append(expense)
        total_day += amount
    
    # Build message
    message = f"""📅 *{formatted_date} ({vn_weekday})*

"""
    
    # Sort categories by total spending
    category_totals = {cat: sum(float(exp["amount"]) for exp in items) 
                      for cat, items in expenses_by_category.items()}
    sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    
    for category, category_total in sorted_categories:
        category_emoji = get_category_emoji(category)
        
        message += f"{category_emoji} *{category}* `{format_currency(category_total)}`\n"
        
        # Show items for this category
        items = sorted(expenses_by_category[category], key=lambda x: x["id"])
        for item in items:
            description = item["description"]
            amount = float(item["amount"])
            message += f"• {description} `{format_currency(amount)}`\n"
        message += "\n"
    
    message += f"💰 Tổng: `{format_currency(total_day)}` ({len(expenses_data.data)} giao dịch)"
    
    await send_formatted_message(update, message)

async def _show_category_expenses_for_date(update: Update, user_id: int, category: str, target_date: date):
    """Show expenses for specific category on specific date"""
    
    # Get expenses for this category and date
    expenses_data = db.supabase.table("expenses").select("*").eq("user_id", user_id).eq("category", category).eq("date", target_date.isoformat()).execute()
    
    formatted_date = target_date.strftime("%d/%m/%Y")
    weekday = target_date.strftime("%A") 
    vietnamese_weekdays = {
        "Monday": "T2", "Tuesday": "T3", "Wednesday": "T4", 
        "Thursday": "T5", "Friday": "T6", "Saturday": "T7", "Sunday": "CN"
    }
    vn_weekday = vietnamese_weekdays.get(weekday, weekday)
    category_emoji = get_category_emoji(category)
    
    if not expenses_data.data:
        message = f"""{category_emoji} *{category.upper()}*

📅 {formatted_date} ({vn_weekday})

Không có chi tiêu nào."""
        await send_formatted_message(update, message)
        return
    
    # Calculate total and build expense list
    total_spent = sum(float(expense["amount"]) for expense in expenses_data.data)
    sorted_expenses = sorted(expenses_data.data, key=lambda x: x["id"])
    
    message = f"""{category_emoji} *{category.upper()}*

📅 {formatted_date} ({vn_weekday})

"""
    
    for expense in sorted_expenses:
        description = expense["description"]
        amount = float(expense["amount"])
        message += f"• {description} `{format_currency(amount)}`\n"
    
    message += f"\n💰 Tổng: `{format_currency(total_spent)}` ({len(sorted_expenses)} giao dịch)"
    
    await send_formatted_message(update, message)

async def _show_all_categories_expenses(update: Update, user_id: int):
    """Show overview - MUCH more concise"""
    target_month, target_year = get_current_month()
    month_start, month_end = get_month_date_range(target_year, target_month)
    
    expenses = db.get_monthly_expenses(user_id, month_start)
    
    if not expenses.data:
        date_range = get_month_display(target_year, target_month)
        message = f"""📋 Tháng {target_month}/{target_year}
📅 {date_range}

Chưa có chi tiêu nào."""
        await send_formatted_message(update, message)
        return
    
    # Get required data with error handling
    try:
        from .budget_handlers import calculate_remaining_budget, get_total_budget
        remaining_budget = calculate_remaining_budget(user_id, month_start)
        total_budget = get_total_budget(user_id)
    except ImportError:
        remaining_budget = {}
        total_budget = 0
    
    try:
        from .wishlist_handlers import get_wishlist_priority_sums
        wishlist_sums = get_wishlist_priority_sums(user_id)
    except ImportError:
        wishlist_sums = {"level1": 0, "level2": 0, "level1_and_2": 0}
    
    try:
        from .income_handlers import calculate_income_by_type, calculate_expenses_by_income_type
        income_breakdown = calculate_income_by_type(user_id, month_start)
        expense_breakdown = calculate_expenses_by_income_type(user_id, month_start)
    except ImportError:
        income_breakdown = {"total": 0, "construction": 0, "general": 0}
        expense_breakdown = {"total": 0, "construction": 0, "general": 0}
    
    # Get account balances
    account_balances = {}
    all_account_types = ["need", "fun", "construction", "saving", "invest"]
    
    accounts_data = db.get_accounts(user_id)
    if not accounts_data.data:
        await _initialize_all_accounts(user_id)
    
    for account_type in all_account_types:
        account_balances[account_type] = db.get_account_balance(user_id, account_type)

    # Group expenses by category
    expenses_by_category = defaultdict(list)
    total_month = 0
    
    for expense in expenses.data:
        category = expense["category"]
        amount = float(expense["amount"])
        expenses_by_category[category].append(expense)
        total_month += amount
    
    # Build categories content - FIXED STRUCTURE
    categories_content = []
    category_totals = {cat: sum(float(exp["amount"]) for exp in items) 
                      for cat, items in expenses_by_category.items()}
    
    sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    
    for category, category_total in sorted_categories:
        category_emoji = get_category_emoji(category)
        
        # Build budget info for this category
        budget_text = ""
        if category in remaining_budget:
            budget_data = remaining_budget[category]
            budget_amount = budget_data["budget"]
            spent_amount = budget_data["spent"]
            remaining = budget_data["remaining"]
            
            if remaining >= 0:
                budget_text = f"\n  💰 Budget: `{format_currency(budget_amount)}` | Dùng: `{format_currency(spent_amount)}` | Còn: `{format_currency(remaining)}`"
            else:
                budget_text = f"\n  💰 Budget: `{format_currency(budget_amount)}` | Dùng: `{format_currency(spent_amount)}` | ⚠️ Vượt: `{format_currency(abs(remaining))}`"
        
        # Category header on its own line
        header = f"{category_emoji} *{category}* `{format_currency(category_total)}`{budget_text}"
        
        # Show only top 3 items
        items = sorted(expenses_by_category[category], key=lambda x: x["date"], reverse=True)[:3]
        expense_items = []
        
        for item in items:
            expense_items.append(f"  {format_expense_item_simple(item)}")
        
        # Add count if more items - on separate line
        if len(expenses_by_category[category]) > 3:
            remaining_count = len(expenses_by_category[category]) - 3
            expense_items.append(f"  _... +{remaining_count} giao dịch_")
        
        # Combine header with items
        category_section = header + "\n" + "\n".join(expense_items)
        categories_content.append(category_section)
    
    # Financial summary - CONCISE
    total_income = income_breakdown["total"]
    net_savings = total_income - total_month
    
    # Account summary - SIMPLE
    spending_total = account_balances.get('need', 0) + account_balances.get('fun', 0)
    
    # Wishlist summary - BRIEF
    wishlist_info = ""
    if wishlist_sums["level1"] > 0:
        after_level1 = net_savings - wishlist_sums["level1"]
        if after_level1 >= 0:
            wishlist_info = f"\n🔒 Sau Level 1: `{format_currency(after_level1)}`"
        else:
            wishlist_info = f"\n🔒 Thiếu Level 1: `{format_currency(abs(after_level1))}`"
    
    # Budget summary - BRIEF
    budget_info = ""
    if total_budget > 0:
        budget_remaining = total_budget - total_month
        if budget_remaining >= 0:
            budget_info = f"\n💰 Budget còn: `{format_currency(budget_remaining)}`"
        else:
            budget_info = f"\n⚠️ Vượt budget: `{format_currency(abs(budget_remaining))}`"
    
    date_range = get_month_display(target_year, target_month)
    
    message = f"""📋 *THÁNG {target_month}/{target_year}*
📅 {date_range}

{chr(10).join(categories_content)}

💰 *TỔNG: {format_currency(total_month)}*

💵 Thu: `{format_currency(total_income)}`
📈 Tiết kiệm: `{format_currency(net_savings)}`{wishlist_info}{budget_info}

💳 Tài khoản tiêu dùng: `{format_currency(spending_total)}`
💰 Tiết kiệm: `{format_currency(account_balances.get('saving', 0))}`"""
    
    await send_long_message(update, message)

def _find_matching_category(category_input: str) -> str:
    """Find matching category - simplified"""
    from difflib import get_close_matches
    
    if not category_input:
        return None
    
    category_input = category_input.strip().lower()
    
    # Try exact match first
    if category_input in EXPENSE_CATEGORIES:
        return category_input
    
    # Try fuzzy matching
    try:
        close_matches = get_close_matches(category_input, EXPENSE_CATEGORIES, n=1, cutoff=0.4)
        if close_matches:
            return close_matches[0]
    except Exception:
        pass
    
    # Try partial matching
    for category in EXPENSE_CATEGORIES:
        if category_input in category or category in category_input:
            return category
    
    # Try common variations
    variations = {
        "an": "ăn uống", "anuong": "ăn uống", "food": "ăn uống",
        "meo": "mèo", "cat": "mèo",
        "congtrinh": "công trình", "construction": "công trình",
        "dichuyen": "di chuyển", "transport": "di chuyển",
        "hoadon": "hóa đơn", "bills": "hóa đơn",
        "canhan": "cá nhân", "personal": "cá nhân",
        "linhtinh": "linh tinh", "misc": "linh tinh"
    }
    
    return variations.get(category_input)

async def _initialize_all_accounts(user_id):
    """Initialize all account types with 0 balance"""
    all_account_types = ["need", "fun", "saving", "invest", "construction"]
    
    for account_type in all_account_types:
        existing_account = db.get_account_by_type(user_id, account_type)
        
        if not existing_account.data:
            account_data = {
                "user_id": user_id,
                "account_type": account_type,
                "current_balance": 0,
                "last_updated": datetime.now().isoformat()
            }
            try:
                db.supabase.table("accounts").insert(account_data).execute()
            except Exception as e:
                logging.error(f"Error initializing account {account_type}: {e}")