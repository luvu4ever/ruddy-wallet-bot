from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, date
from collections import defaultdict
import re
import logging

from database import db
from utils import (
    check_authorization, send_formatted_message, send_long_message,
    get_current_salary_month, get_month_date_range, get_salary_month_display,
    format_currency
)
from config import (
    EXPENSE_CATEGORIES, get_category_emoji, format_budget_info, 
    format_expense_item, get_template
)

async def list_expenses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced /list command with multiple modes:
    - /list - Overview of all categories (current)
    - /list [category] - All expenses for specific category this salary month
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
        await _show_category_expenses_for_salary_month(
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
            available_categories = ", ".join(EXPENSE_CATEGORIES)
            return {
                "mode": "invalid",
                "error_message": f"""❌ *KHÔNG TÌM THẤY DANH MỤC*

🔍 *Tìm kiếm:* `{category_text}`

*📂 CÁC DANH MỤC CÓ SẴN:*
{available_categories}

*💡 VÍ DỤ:*
• `/list ăn uống` - Chi tiêu ăn uống tháng lương này
• `/list mèo 15/08/2025` - Chi tiêu mèo ngày 15/08/2025
• `/list 20/08/2025` - Tất cả chi tiêu ngày 20/08/2025"""
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
        # Category for current salary month
        current_month, current_year = get_current_salary_month()
        return {
            "mode": "category_month",
            "category": matched_category,
            "month": current_month,
            "year": current_year
        }
    else:
        return {
            "mode": "invalid",
            "error_message": f"""❌ *KHÔNG HIỂU LỆNH*

*💡 CÁCH DÙNG `/list`:*
• `/list` - Tổng quan tất cả danh mục
• `/list ăn uống` - Chi tiêu ăn uống tháng lương này
• `/list 15/08/2025` - Tất cả chi tiêu ngày 15/08/2025
• `/list mèo 20/8/25` - Chi tiêu mèo ngày 20/08/2025

*📅 ĐỊNH DẠNG NGÀY HỖ TRỢ:*
• `dd/mm/yyyy` - 15/08/2025
• `dd/mm/yy` - 15/08/25  
• `dd-mm-yyyy` - 15-08-2025
• `dd.mm.yyyy` - 15.08.2025

*📂 DANH MỤC:* {", ".join(EXPENSE_CATEGORIES[:5])}..."""
        }

async def _show_category_expenses_for_salary_month(update: Update, user_id: int, category: str, target_month: int, target_year: int):
    """Show all expenses for specific category in salary month (enhanced category command)"""
    
    # Get expenses for this category and salary month
    month_start, month_end = get_month_date_range(target_year, target_month)
    expenses = db.get_expenses_by_category(user_id, category, month_start)
    
    if not expenses.data:
        category_emoji = get_category_emoji(category)
        date_range = get_salary_month_display(target_year, target_month)
        message = f"""📂 *KHÔNG CÓ CHI TIÊU*

{category_emoji} *{category.upper()} - THÁNG LƯƠNG {target_month}/{target_year}*
📅 *({date_range})*

Không có chi tiêu nào cho danh mục này trong tháng lương {target_month}/{target_year}

💡 _Thử danh mục khác: `/list ăn uống`_
💡 _Xem tổng quan: `/list`_"""
        await send_formatted_message(update, message)
        return
    
    # Get budget information
    from .budget_handlers import calculate_remaining_budget
    remaining_budget = calculate_remaining_budget(user_id, month_start)
    
    # Get account information for this category
    from config import get_account_for_category, get_account_emoji_enhanced, get_account_name_enhanced
    account_type = get_account_for_category(category)
    account_balance = db.get_account_balance(user_id, account_type)
    account_emoji = get_account_emoji_enhanced(account_type)
    account_name = get_account_name_enhanced(account_type)
    
    # Calculate total spent in this category
    total_spent = sum(float(expense["amount"]) for expense in expenses.data)
    
    # Format budget info
    budget_section = ""
    if category in remaining_budget:
        budget_data = remaining_budget[category]
        budget_amount = budget_data["budget"]
        spent_amount = budget_data["spent"]
        remaining = budget_data["remaining"]
        
        if remaining >= 0:
            budget_section = f"""
💰 *BUDGET THÁNG LƯƠNG {target_month}/{target_year}:*
💰 Ngân sách: `{format_currency(budget_amount)}`
💸 Đã chi: `{format_currency(spent_amount)}`
✅ Còn lại: `{format_currency(remaining)}`
📊 Đã dùng: {(spent_amount/budget_amount*100):.1f}%"""
        else:
            budget_section = f"""
💰 *BUDGET THÁNG LƯƠNG {target_month}/{target_year}:*
💰 Ngân sách: `{format_currency(budget_amount)}`
💸 Đã chi: `{format_currency(spent_amount)}`
⚠️ Vượt budget: `{format_currency(abs(remaining))}`
📊 Vượt: {(spent_amount/budget_amount*100):.1f}%"""
    else:
        budget_section = f"""
💡 *CHƯA CÓ BUDGET*
Đặt budget cho danh mục này: `/budget {category} [số tiền]`"""
    
    # Add account info section
    account_section = f"""
💳 *TÀI KHOẢN LIÊN KẾT:*
{account_emoji} *{account_name}*: `{format_currency(account_balance)}`"""
    
    # Sort expenses by date (newest first) and format all
    sorted_expenses = sorted(expenses.data, key=lambda x: x["date"], reverse=True)
    expense_lines = []
    
    for expense in sorted_expenses:
        expense_lines.append(format_expense_item(expense))
    
    category_emoji = get_category_emoji(category)
    date_range = get_salary_month_display(target_year, target_month)
    
    message = f"""{category_emoji} *TẤT CẢ CHI TIÊU {category.upper()}*

📊 *Tháng lương {target_month}/{target_year}*
📅 *({date_range})*{account_section}{budget_section}

📝 *TẤT CẢ GIAO DỊCH:*
{chr(10).join(expense_lines)}

💰 *Tổng chi tiêu:* `{format_currency(total_spent)}`
📊 *Số giao dịch:* {len(sorted_expenses)} lần

💡 *Xem tổng quan:* `/list`"""
    
    await send_long_message(update, message)

async def _show_all_expenses_for_date(update: Update, user_id: int, target_date: date):
    """Show all expenses for a specific date"""
    
    # Get all expenses for the target date
    expenses_data = db.supabase.table("expenses").select("*").eq("user_id", user_id).eq("date", target_date.isoformat()).execute()
    
    if not expenses_data.data:
        formatted_date = target_date.strftime("%d/%m/%Y")
        weekday = target_date.strftime("%A")
        vietnamese_weekdays = {
            "Monday": "Thứ Hai", "Tuesday": "Thứ Ba", "Wednesday": "Thứ Tư", 
            "Thursday": "Thứ Năm", "Friday": "Thứ Sáu", "Saturday": "Thứ Bảy", "Sunday": "Chủ Nhật"
        }
        vn_weekday = vietnamese_weekdays.get(weekday, weekday)
        
        message = f"""📅 *KHÔNG CÓ CHI TIÊU*

📅 *{formatted_date} ({vn_weekday})*

Không có chi tiêu nào trong ngày này.

💡 *Thử lệnh khác:*
• `/list` - Tổng quan tháng lương này
• `/list ăn uống` - Chi tiêu ăn uống
• `/list {(target_date.day+1):02d}/{target_date.month:02d}/{target_date.year}` - Ngày khác"""
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
    formatted_date = target_date.strftime("%d/%m/%Y")
    weekday = target_date.strftime("%A")
    vietnamese_weekdays = {
        "Monday": "Thứ Hai", "Tuesday": "Thứ Ba", "Wednesday": "Thứ Tư", 
        "Thursday": "Thứ Năm", "Friday": "Thứ Sáu", "Saturday": "Thứ Bảy", "Sunday": "Chủ Nhật"
    }
    vn_weekday = vietnamese_weekdays.get(weekday, weekday)
    
    message = f"""📅 *CHI TIÊU NGÀY {formatted_date}*
📅 *({vn_weekday})*

"""
    
    # Sort categories by total spending
    category_totals = {cat: sum(float(exp["amount"]) for exp in items) 
                      for cat, items in expenses_by_category.items()}
    sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    
    for category, category_total in sorted_categories:
        category_emoji = get_category_emoji(category)
        
        message += f"{category_emoji} *{category.upper()}* - `{format_currency(category_total)}`\n"
        
        # Show all items for this category on this date
        items = sorted(expenses_by_category[category], key=lambda x: x["id"])
        for item in items:
            description = item["description"]
            amount = float(item["amount"])
            message += f"  • {description} - `{format_currency(amount)}`\n"
        message += "\n"
    
    message += f"💰 *TỔNG CHI TIÊU NGÀY:* `{format_currency(total_day)}`\n"
    message += f"📊 *SỐ GIAO DỊCH:* {len(expenses_data.data)} lần\n\n"
    message += f"💡 *Xem chi tiết danh mục:* `/list [danh mục] {formatted_date}`"
    
    await send_formatted_message(update, message)

async def _show_category_expenses_for_date(update: Update, user_id: int, category: str, target_date: date):
    """Show expenses for specific category on specific date"""
    
    # Get expenses for this category and date
    expenses_data = db.supabase.table("expenses").select("*").eq("user_id", user_id).eq("category", category).eq("date", target_date.isoformat()).execute()
    
    formatted_date = target_date.strftime("%d/%m/%Y")
    weekday = target_date.strftime("%A") 
    vietnamese_weekdays = {
        "Monday": "Thứ Hai", "Tuesday": "Thứ Ba", "Wednesday": "Thứ Tư", 
        "Thursday": "Thứ Năm", "Friday": "Thứ Sáu", "Saturday": "Thứ Bảy", "Sunday": "Chủ Nhật"
    }
    vn_weekday = vietnamese_weekdays.get(weekday, weekday)
    
    if not expenses_data.data:
        category_emoji = get_category_emoji(category)
        message = f"""📅 *KHÔNG CÓ CHI TIÊU*

{category_emoji} *{category.upper()} - {formatted_date}*
📅 *({vn_weekday})*

Không có chi tiêu nào cho danh mục này trong ngày {formatted_date}

💡 *Thử lệnh khác:*
• `/list {formatted_date}` - Tất cả chi tiêu ngày {formatted_date}
• `/list {category}` - Chi tiêu {category} tháng lương này
• `/list` - Tổng quan tháng lương"""
        await send_formatted_message(update, message)
        return
    
    # Calculate total and build expense list
    total_spent = sum(float(expense["amount"]) for expense in expenses_data.data)
    sorted_expenses = sorted(expenses_data.data, key=lambda x: x["id"])
    
    # Get account info for this category
    from config import get_account_for_category, get_account_emoji_enhanced, get_account_name_enhanced
    account_type = get_account_for_category(category)
    account_balance = db.get_account_balance(user_id, account_type)
    account_emoji = get_account_emoji_enhanced(account_type)
    account_name = get_account_name_enhanced(account_type)
    
    category_emoji = get_category_emoji(category)
    
    message = f"""{category_emoji} *CHI TIÊU {category.upper()}*

📅 *{formatted_date} ({vn_weekday})*

💳 *Tài khoản liên kết:*
{account_emoji} *{account_name}*: `{format_currency(account_balance)}`

📝 *CHI TIẾT GIAO DỊCH:*
"""
    
    for expense in sorted_expenses:
        description = expense["description"]
        amount = float(expense["amount"])
        message += f"• *{description}*: `{format_currency(amount)}`\n"
    
    message += f"""
💰 *Tổng chi tiêu:* `{format_currency(total_spent)}`
📊 *Số giao dịch:* {len(sorted_expenses)} lần

💡 *Xem thêm:*
• `/list {formatted_date}` - Tất cả danh mục ngày {formatted_date}
• `/list {category}` - Chi tiêu {category} tháng lương này"""
    
    await send_formatted_message(update, message)

async def _show_all_categories_expenses(update: Update, user_id: int):
    """Original function - show all categories with top 8 items each + budget info + wishlist analysis + account info"""
    # Use current salary month instead of calendar month
    target_month, target_year = get_current_salary_month()
    month_start, month_end = get_month_date_range(target_year, target_month)
    
    expenses = db.get_monthly_expenses(user_id, month_start)
    
    if not expenses.data:
        date_range = get_salary_month_display(target_year, target_month)
        message = f"""📝 *CHƯA CÓ CHI TIÊU*

📅 *Tháng lương {target_month}/{target_year}*
📅 *({date_range})*

Chưa có chi tiêu nào trong tháng lương này.
Hãy bắt đầu ghi chi tiêu bằng cách nhắn: `50k cà phê`

💡 *Lệnh /list nâng cao:*
• `/list ăn uống` - Xem chi tiêu ăn uống
• `/list 15/08/2025` - Xem chi tiêu ngày 15/08/2025"""
        await send_formatted_message(update, message)
        return
    
    # Import required functions
    from .budget_handlers import calculate_remaining_budget, get_total_budget
    from .wishlist_handlers import get_wishlist_priority_sums
    from .income_handlers import calculate_income_by_type, calculate_expenses_by_income_type
    
    # Calculate data
    remaining_budget = calculate_remaining_budget(user_id, month_start)
    wishlist_sums = get_wishlist_priority_sums(user_id)
    income_breakdown = calculate_income_by_type(user_id, month_start)
    expense_breakdown = calculate_expenses_by_income_type(user_id, month_start)
    
    # Get account balances - make sure accounts exist first
    account_balances = {}
    all_account_types = ["need", "fun", "construction", "saving", "invest"]
    
    # Initialize accounts if they don't exist
    accounts_data = db.get_accounts(user_id)
    if not accounts_data.data:
        await _initialize_all_accounts(user_id)
    
    # Get current balances
    for account_type in all_account_types:
        account_balances[account_type] = db.get_account_balance(user_id, account_type)

    expenses_by_category = defaultdict(list)
    total_month = 0
    
    for expense in expenses.data:
        category = expense["category"]
        amount = float(expense["amount"])
        expenses_by_category[category].append(expense)
        total_month += amount
    
    # Build categories content
    categories_content = []
    category_totals = {cat: sum(float(exp["amount"]) for exp in items) 
                      for cat, items in expenses_by_category.items()}
    
    sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    
    for category, category_total in sorted_categories:
        category_emoji = get_category_emoji(category)
        budget_info = format_budget_info(remaining_budget, category)
        
        # Add account info for this category
        from config import get_account_for_category, get_account_emoji_enhanced, get_account_name_enhanced
        account_type = get_account_for_category(category)
        account_balance = account_balances.get(account_type, 0)
        account_emoji = get_account_emoji_enhanced(account_type)
        account_name = get_account_name_enhanced(account_type)
        
        # Add low balance warning
        balance_warning = ""
        if account_balance < 500000:  # Less than 500k
            balance_warning = f" ⚠️"
        
        # Enhanced category header with account info and clickable command
        header = f"""{category_emoji} *{category.upper()}* - `{format_currency(category_total)}`{budget_info}
{account_emoji} _{account_name}: {format_currency(account_balance)}_{balance_warning}
💡 _Chi tiết: `/list {category}`_"""
        
        # Top 8 items
        items = sorted(expenses_by_category[category], key=lambda x: x["date"], reverse=True)[:8]
        expense_items = [format_expense_item(item) for item in items]
        
        # More items info with helpful command
        if len(expenses_by_category[category]) > 8:
            remaining_count = len(expenses_by_category[category]) - 8
            more_info = f"  _... và {remaining_count} giao dịch khác (xem: `/list {category}`)_"
            expense_items.append(more_info)
        
        categories_content.append(header + "\n" + "\n".join(expense_items))
    
    # Calculate financial data
    total_income = income_breakdown["total"]
    total_expenses = expense_breakdown["total"]
    net_savings = total_income - total_expenses
    
    # Calculate wishlist scenarios
    money_after_level1 = net_savings - wishlist_sums["level1"]
    money_after_level1_and_2 = net_savings - wishlist_sums["level1_and_2"]
    
    # Budget analysis
    total_budget = get_total_budget(user_id)
    budget_remaining = total_budget - total_expenses if total_budget > 0 else 0
    money_after_all = budget_remaining - wishlist_sums["level1_and_2"]
    
    # Build wishlist section
    wishlist_section = ""
    if wishlist_sums["level1"] > 0 or wishlist_sums["level2"] > 0:
        wishlist_section += "\n\n🛍️ *WISHLIST ANALYSIS:*"
        
        if wishlist_sums["level1"] > 0:
            wishlist_section += f"\n🔒 *Level 1:* `{format_currency(wishlist_sums['level1'])}`"
        
        if wishlist_sums["level2"] > 0:
            wishlist_section += f"\n🚨 *Level 2:* `{format_currency(wishlist_sums['level2'])}`"
        
        if money_after_level1 >= 0:
            wishlist_section += f"\n✅ *Sau Level 1:* `{format_currency(money_after_level1)}`"
        else:
            wishlist_section += f"\n⚠️ *Thiếu Level 1:* `{format_currency(abs(money_after_level1))}`"
        
        if money_after_level1_and_2 >= 0:
            wishlist_section += f"\n✅ *Sau Level 1+2:* `{format_currency(money_after_level1_and_2)}`"
        else:
            wishlist_section += f"\n⚠️ *Thiếu Level 1+2:* `{format_currency(abs(money_after_level1_and_2))}`"
        
        if total_budget > 0:
            if money_after_all >= 0:
                wishlist_section += f"\n💰 *Sau Budget+Level1+2:* `{format_currency(money_after_all)}`"
            else:
                wishlist_section += f"\n🔴 *Vượt Budget+Level1+2:* `{format_currency(abs(money_after_all))}`"
    
    # Build account summary section - ALWAYS show this
    spending_total = account_balances.get('need', 0) + account_balances.get('fun', 0)
    account_section = f"""

💳 *TÀI KHOẢN HIỆN TẠI:*
🛒 *Tiêu dùng* (Thiết yếu + Giải trí): `{format_currency(spending_total)}`
🍚 *Thiết yếu*: `{format_currency(account_balances.get('need', 0))}`
🎮 *Giải trí*: `{format_currency(account_balances.get('fun', 0))}`
🏗️ *Xây dựng*: `{format_currency(account_balances.get('construction', 0))}`
💰 *Tiết kiệm*: `{format_currency(account_balances.get('saving', 0))}`
📈 *Đầu tư*: `{format_currency(account_balances.get('invest', 0))}`"""
    
    # Create message - combine wishlist section and account section
    full_analysis_section = wishlist_section + account_section
    
    # Get salary month display range
    date_range = get_salary_month_display(target_year, target_month)
    
    message = get_template("list_overview",
        month=target_month,
        year=target_year,
        date_range=date_range,
        categories_content="\n\n".join(categories_content),
        total=format_currency(total_month),
        construction_income=format_currency(income_breakdown["construction"]),
        construction_expense=format_currency(expense_breakdown["construction"]),
        construction_net=format_currency(income_breakdown["construction"] - expense_breakdown["construction"]),
        general_income=format_currency(income_breakdown["general"]),
        general_expense=format_currency(expense_breakdown["general"]),
        general_net=format_currency(income_breakdown["general"] - expense_breakdown["general"]),
        wishlist_section=full_analysis_section  # This now includes both wishlist and account info
    )
    
    # Add enhanced usage instructions
    enhanced_usage = f"""

💡 *LỆNH /list NÂNG CAO:*
• `/list [danh mục]` - Chi tiết danh mục (VD: `/list ăn uống`)
• `/list [ngày]` - Chi tiêu theo ngày (VD: `/list 15/08/2025`)
• `/list [danh mục] [ngày]` - Kết hợp (VD: `/list mèo 20/8/25`)

📅 *Định dạng ngày:* dd/mm/yyyy, dd/mm/yy, dd-mm-yyyy, dd.mm.yyyy"""
    
    final_message = message + enhanced_usage
    
    await send_long_message(update, final_message)

def _find_matching_category(category_input: str) -> str:
    """Find matching category with better Vietnamese support"""
    from difflib import get_close_matches
    
    if not category_input:
        return None
    
    # Clean the input
    category_input = category_input.strip().lower()
    
    # Try exact match first
    if category_input in EXPENSE_CATEGORIES:
        return category_input
    
    # Try fuzzy matching with lower cutoff for better Vietnamese matching
    try:
        close_matches = get_close_matches(category_input, EXPENSE_CATEGORIES, n=1, cutoff=0.4)
        if close_matches:
            return close_matches[0]
    except Exception as e:
        logging.error(f"Error in fuzzy matching: {e}")
    
    # Try partial matching - check if input is contained in any category
    try:
        for category in EXPENSE_CATEGORIES:
            if category_input in category or category in category_input:
                return category
    except Exception as e:
        logging.error(f"Error in partial matching: {e}")
    
    # Try matching without Vietnamese accents/spaces
    try:
        simplified_input = category_input.replace(" ", "").replace("ă", "a").replace("ê", "e").replace("ô", "o")
        for category in EXPENSE_CATEGORIES:
            simplified_category = category.replace(" ", "").replace("ă", "a").replace("ê", "e").replace("ô", "o")
            if simplified_input == simplified_category:
                return category
    except Exception as e:
        logging.error(f"Error in simplified matching: {e}")
    
    # Try common variations
    try:
        variations = {
            "an": "ăn uống",
            "anuong": "ăn uống", 
            "food": "ăn uống",
            "meo": "mèo",
            "cat": "mèo",
            "congtrinh": "công trình",
            "construction": "công trình",
            "dichuyển": "di chuyển",
            "dichuyen": "di chuyển",
            "transport": "di chuyển",
            "hoadon": "hóa đơn",
            "bills": "hóa đơn",
            "canhan": "cá nhân",
            "personal": "cá nhân",
            "linhtinh": "linh tinh",
            "misc": "linh tinh"
        }
        
        if category_input in variations:
            return variations[category_input]
    except Exception as e:
        logging.error(f"Error in variations matching: {e}")
    
    return None

async def _initialize_all_accounts(user_id):
    """Initialize all account types with 0 balance"""
    from datetime import datetime
    
    all_account_types = ["need", "fun", "saving", "invest", "construction"]
    
    for account_type in all_account_types:
        # Check if account already exists
        existing_account = db.get_account_by_type(user_id, account_type)
        
        if not existing_account.data:
            # Only create if it doesn't exist
            account_data = {
                "user_id": user_id,
                "account_type": account_type,
                "current_balance": 0,
                "last_updated": datetime.now().isoformat()
            }
            try:
                db.supabase.table("accounts").insert(account_data).execute()
            except Exception as e:
                logging.error(f"Error initializing account {account_type} for user {user_id}: {e}")
                # Continue with other accounts even if one fails