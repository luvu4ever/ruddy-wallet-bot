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
    amount = float(expense["amount"])
    description = expense["description"]
    
    date_obj = datetime.strptime(expense["date"], "%Y-%m-%d")
    date_str = f"{date_obj.day:02d}/{date_obj.month:02d}"
    
    return f"{date_str} {description} `{format_currency(amount)}`"

async def list_expenses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await _show_all_categories_summary(update, user_id)
        return
    
    parsed_args = _parse_list_arguments(args)
    
    if parsed_args["mode"] == "invalid":
        await send_formatted_message(update, parsed_args["error_message"])
        return
    
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

async def _show_all_categories_summary(update: Update, user_id: int):
    """Show clean summary of all categories - no detailed expense items"""
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
    
    # Get budget and account data
    try:
        from .budget_handlers import calculate_remaining_budget, get_total_budget
        remaining_budget = calculate_remaining_budget(user_id, month_start)
        total_budget = get_total_budget(user_id)
    except ImportError:
        remaining_budget = {}
        total_budget = 0
    
    try:
        from .income_handlers import calculate_income_by_type
        income_breakdown = calculate_income_by_type(user_id, month_start)
    except ImportError:
        income_breakdown = {"total": 0}
    
    # Get account balances
    account_balances = {}
    all_account_types = ["need", "fun", "mama", "saving", "invest"]
    
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
    
    # Build category summaries
    categories_content = []
    category_totals = {cat: sum(float(exp["amount"]) for exp in items) 
                      for cat, items in expenses_by_category.items()}
    
    # Sort by spending amount (highest first)
    sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    
    for category, category_total in sorted_categories:
        category_emoji = get_category_emoji(category)
        
        # Get account for this category
        from config import get_account_for_category
        account_type = get_account_for_category(category)
        account_balance = account_balances.get(account_type, 0)
        
        # Build budget info
        budget_info = ""
        if category in remaining_budget:
            budget_data = remaining_budget[category]
            budget_amount = budget_data["budget"]
            spent_amount = budget_data["spent"]
            remaining = budget_data["remaining"]
            
            # Calculate percentage used
            percentage_used = (spent_amount / budget_amount * 100) if budget_amount > 0 else 0
            
            if remaining >= 0:
                budget_info = f" | Budget: `{format_currency(budget_amount)}` ({percentage_used:.0f}% dùng, còn `{format_currency(remaining)}`)"
            else:
                budget_info = f" | Budget: `{format_currency(budget_amount)}` ({percentage_used:.0f}% dùng, ⚠️ vượt `{format_currency(abs(remaining))}`)"
        else:
            budget_info = " | Chưa đặt budget"
        
        # Format category section (multiple lines)
        category_section = f"{category_emoji} *{category}*: `{format_currency(category_total)}`\n"
        category_section += f"  💳 Tài khoản: `{format_currency(account_balance)}`"
        
        if category in remaining_budget:
            budget_data = remaining_budget[category]
            budget_amount = budget_data["budget"]
            spent_amount = budget_data["spent"]
            remaining = budget_data["remaining"]
            
            # Calculate percentage used
            percentage_used = (spent_amount / budget_amount * 100) if budget_amount > 0 else 0
            
            category_section += f"\n  💰 Budget: `{format_currency(budget_amount)}` ({percentage_used:.0f}% dùng)"
            
            if remaining >= 0:
                category_section += f"\n  ✅ Còn lại: `{format_currency(remaining)}`"
            else:
                category_section += f"\n  ⚠️ Vượt: `{format_currency(abs(remaining))}`"
        else:
            category_section += f"\n  💡 Chưa đặt budget"
        
        categories_content.append(category_section)
    
    # Calculate totals
    total_income = income_breakdown["total"]
    net_savings = total_income - total_month
    spending_total = account_balances.get('need', 0) + account_balances.get('fun', 0)
    
    # Budget summary
    budget_summary = ""
    if total_budget > 0:
        budget_remaining = total_budget - total_month
        budget_used_pct = (total_month / total_budget * 100) if total_budget > 0 else 0
        
        if budget_remaining >= 0:
            budget_summary = f"\n💰 *Budget tháng*: `{format_currency(total_budget)}` ({budget_used_pct:.0f}% dùng, còn `{format_currency(budget_remaining)}`)"
        else:
            budget_summary = f"\n💰 *Budget tháng*: `{format_currency(total_budget)}` ({budget_used_pct:.0f}% dùng, ⚠️ vượt `{format_currency(abs(budget_remaining))}`)"
    
    date_range = get_month_display(target_year, target_month)
    
    message = f"""📋 *THÁNG {target_month}/{target_year}*
📅 {date_range}

{chr(10).join(categories_content)}

💰 *TỔNG CHI TIÊU: {format_currency(total_month)}*
💵 Thu nhập: `{format_currency(total_income)}`
📈 Tiết kiệm: `{format_currency(net_savings)}`{budget_summary}

💳 *TÀI KHOẢN:*
🏠 Need + Fun: `{format_currency(spending_total)}`
💰 Tiết kiệm: `{format_currency(account_balances.get('saving', 0))}`
📈 Đầu tư: `{format_currency(account_balances.get('invest', 0))}`
🗯️ Mama: `{format_currency(account_balances.get('mama', 0))}`

💡 *Xem chi tiết*: `/list [tên danh mục]` hoặc `/list [ngày]`"""
    
    await send_long_message(update, message)

# Keep existing detailed functions for specific category/date views
async def _show_category_expenses_for_month(update: Update, user_id: int, category: str, target_month: int, target_year: int):
    """Show detailed expenses for a specific category"""
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
    
    try:
        from .budget_handlers import calculate_remaining_budget
        remaining_budget = calculate_remaining_budget(user_id, month_start)
    except ImportError:
        remaining_budget = {}
    
    from config import get_account_for_category
    account_type = get_account_for_category(category)
    account_balance = db.get_account_balance(user_id, account_type)
    
    total_spent = sum(float(expense["amount"]) for expense in expenses.data)
    
    budget_info = ""
    if category in remaining_budget:
        budget_data = remaining_budget[category]
        budget_amount = budget_data["budget"]
        spent_amount = budget_data["spent"]
        remaining = budget_data["remaining"]
        
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
    
    expenses_by_category = defaultdict(list)
    total_day = 0
    
    for expense in expenses_data.data:
        category = expense["category"]
        amount = float(expense["amount"])
        expenses_by_category[category].append(expense)
        total_day += amount
    
    message = f"""📅 *{formatted_date} ({vn_weekday})*

"""
    
    category_totals = {cat: sum(float(exp["amount"]) for exp in items) 
                      for cat, items in expenses_by_category.items()}
    sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    
    for category, category_total in sorted_categories:
        category_emoji = get_category_emoji(category)
        
        message += f"{category_emoji} *{category}* `{format_currency(category_total)}`\n"
        
        items = sorted(expenses_by_category[category], key=lambda x: x["id"])
        for item in items:
            description = item["description"]
            amount = float(item["amount"])
            message += f"• {description} `{format_currency(amount)}`\n"
        message += "\n"
    
    message += f"💰 Tổng: `{format_currency(total_day)}` ({len(expenses_data.data)} giao dịch)"
    
    await send_formatted_message(update, message)

async def _show_category_expenses_for_date(update: Update, user_id: int, category: str, target_date: date):
    """Show expenses for a specific category on a specific date"""
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

def _parse_list_arguments(args):
    """Parse arguments for list command"""
    args_text = " ".join(args).strip()
    
    # Date patterns
    date_patterns = [
        r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b',
        r'\b(\d{1,2})/(\d{1,2})/(\d{2})\b',
        r'\b(\d{1,2})-(\d{1,2})-(\d{4})\b',
        r'\b(\d{1,2})-(\d{1,2})-(\d{2})\b',
        r'\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b',
        r'\b(\d{1,2})\.(\d{1,2})\.(\d{2})\b',
    ]
    
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
                
                if year < 100:
                    if year <= 30:
                        year += 2000
                    else:
                        year += 1900
                
                if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100:
                    try:
                        found_date = date(year, month, day)
                        date_match = match
                        break
                    except ValueError:
                        continue
                        
            except ValueError:
                continue
    
    if found_date and date_match:
        category_text = args_text.replace(date_match.group(), '').strip()
    else:
        category_text = args_text.strip()
    
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

def _find_matching_category(category_input: str) -> str:
    """Find matching category with fuzzy search"""
    from difflib import get_close_matches
    
    if not category_input:
        return None
    
    category_input = category_input.strip().lower()
    
    # Exact match
    if category_input in EXPENSE_CATEGORIES:
        return category_input
    
    # Fuzzy match
    try:
        close_matches = get_close_matches(category_input, EXPENSE_CATEGORIES, n=1, cutoff=0.4)
        if close_matches:
            return close_matches[0]
    except Exception:
        pass
    
    # Substring match
    for category in EXPENSE_CATEGORIES:
        if category_input in category or category in category_input:
            return category
    
    # Common variations
    variations = {
        "an": "ăn uống", "anuong": "ăn uống", "food": "ăn uống",
        "meo": "mèo", "cat": "mèo",
        "mama": "mama",
        "dichuyen": "di chuyển", "transport": "di chuyển",
        "hoadon": "hóa đơn", "bills": "hóa đơn",
        "canhan": "cá nhân", "personal": "cá nhân",
        "linhtinh": "linh tinh", "misc": "linh tinh"
    }
    
    return variations.get(category_input)