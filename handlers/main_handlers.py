import logging
from datetime import datetime, date
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes
from difflib import get_close_matches

from database import db
from ai_parser import parse_message_with_gemini, generate_monthly_summary
from utils import (
    check_authorization, send_formatted_message, send_long_message,
    parse_amount, safe_parse_amount, parse_date_argument, get_month_date_range,
    get_current_salary_month, get_salary_month_display  # NEW: salary cycle functions
)
from config import (
    EXPENSE_CATEGORIES, get_category_emoji, get_all_category_info, 
    get_message, get_template, DEFAULT_SUBSCRIPTION_CATEGORY,
    format_budget_info, format_expense_item, format_currency
)

# Set up logging
logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_authorization(update):
        return
    
    # Register user in database
    user_data = {
        "telegram_id": update.effective_user.id,
        "first_name": update.effective_user.first_name,
        "username": update.effective_user.username
    }
    
    db.register_user(user_data)
    await send_formatted_message(update, get_message("welcome"))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced message handler with account-based expense processing and month-end confirmation"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Check for month-end confirmation first
    from .month_end_handlers import handle_month_end_confirmation
    if await handle_month_end_confirmation(update, context, message_text):
        return  # Message was handled as month-end confirmation
    
    # Parse with Gemini for regular expense processing
    parsed_data = parse_message_with_gemini(message_text, user_id)
    
    responses = []
    message_type = parsed_data.get("type", "unknown")
    
    # Handle different message types
    if message_type == "expenses":
        # Process expenses with account validation
        for expense in parsed_data.get("expenses", []):
            try:
                expense_result = await _process_expense_with_account_validation(
                    user_id, expense["amount"], expense["description"], 
                    expense.get("category", "khác")
                )
                responses.append(expense_result)
                
            except Exception as e:
                logging.error(f"Error processing expense: {e}")
                responses.append("❌ Lỗi khi xử lý chi tiêu")
    else:
        responses.append(get_message("unknown_message"))
    
    if responses:
        await update.message.reply_text("\n".join(responses))
        
async def _process_expense_with_account_validation(user_id, amount, description, category):
    """Process expense with account balance validation"""
    from config import get_account_for_category, get_account_emoji_enhanced, get_account_name_enhanced, format_currency, get_category_emoji
    from datetime import date
    
    # Get account for this category
    account_type = get_account_for_category(category)

    print(f"DEBUG - Category '{category}' maps to account '{account_type}'")
    
    # Check account balance
    current_balance = db.get_account_balance(user_id, account_type)
    
    # Validate sufficient funds
    if current_balance < amount:
        account_emoji = get_account_emoji_enhanced(account_type)
        account_name = get_account_name_enhanced(account_type)
        
        return f"""❌ *KHÔNG ĐỦ TIỀN!*

💰 *Chi tiêu*: {format_currency(amount)} - {description}
📂 *Danh mục*: {category} → {account_emoji} {account_name}
💳 *Số dư hiện tại*: {format_currency(current_balance)}
⚠️ *Thiếu*: {format_currency(amount - current_balance)}

💡 *GIẢI PHÁP:*
• `/accountedit {account_type} [số mới]` - Điều chỉnh số dư
• `/account` - Xem tất cả tài khoản"""
    
    # Save expense record
    expense_data = {
        "user_id": user_id,
        "amount": amount,
        "description": description,
        "category": category,
        "date": date.today().isoformat()
    }
    
    expense_result = db.insert_expense(expense_data)
    expense_id = expense_result.data[0]["id"] if expense_result.data else None
    
    # Deduct from account
    result, new_balance = db.update_account_balance(
        user_id, account_type, -amount,  # Negative for expense
        "expense", f"Expense: {description}", expense_id
    )
    
    # Success response with account info
    account_emoji = get_account_emoji_enhanced(account_type)
    account_name = get_account_name_enhanced(account_type)
    category_emoji = get_category_emoji(category)
    
    return f"""✅ *ĐÃ GHI CHI TIÊU!*

💰 *Chi tiêu*: {format_currency(amount)} - {description}
{category_emoji} *Danh mục*: {category}
{account_emoji} *Từ tài khoản*: {account_name}
💳 *Số dư còn lại*: {format_currency(new_balance)}

💡 _Xem chi tiết: `/account {account_type}`_"""

async def savings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current savings amount"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    savings_data = db.get_savings(user_id)
    
    if savings_data.data:
        current_savings = float(savings_data.data[0]["current_amount"])
        last_updated = savings_data.data[0]["last_updated"]
        message = get_message("savings_current", 
            amount=format_currency(current_savings), 
            date=last_updated[:10])
        await send_formatted_message(update, message)
    else:
        await send_formatted_message(update, get_message("savings_none"))

async def edit_savings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set savings to specific amount: /editsaving 500k"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await send_formatted_message(update, get_message("format_errors")["savings_usage"])
        return
    
    success, new_amount, error_msg = safe_parse_amount(args[0])
    if not success:
        example_msg = get_message("format_errors")["invalid_number"].format(
            example="/editsaving 500k hoặc /editsaving 1.5tr")
        await send_formatted_message(update, example_msg)
        return
    
    # Update savings record
    savings_data = {
        "user_id": user_id,
        "current_amount": new_amount,
        "last_updated": datetime.now().isoformat()
    }
    
    db.upsert_savings(savings_data)
    
    message = get_template("savings_update", amount=format_currency(new_amount))
    await send_formatted_message(update, message)

async def category_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show expenses by category with budget info: /category ăn uống [month/year]"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        # Show all categories
        category_info = get_all_category_info()
        message = f"""📂 *DANH MỤC CHI TIÊU*

*📂 TẤT CẢ DANH MỤC*

{category_info}

*💡 CÁCH DÙNG:*
• `/category ăn uống` - Chi tiêu ăn uống tháng lương này + budget
• `/category mèo 8/2025` - Chi tiêu mèo tháng lương 8/2025 (26/7-25/8/2025)
• `/category công trình` - Chi tiêu công trình tháng lương này

📅 *Tháng lương:* 26-25 (VD: T8 = 26/7-25/8)"""
        await send_formatted_message(update, message)
        return
    
    # Parse arguments - category name and optional date
    category_input = None
    # Use current salary month as default
    target_month, target_year = get_current_salary_month()
    
    # Check if any argument looks like a date (contains "/")
    date_arg = None
    category_args = []
    
    for arg in args:
        if "/" in arg:
            date_arg = arg
        else:
            category_args.append(arg)
    
    # Parse date if provided
    if date_arg:
        success, target_month, target_year, error_msg = parse_date_argument(date_arg)
        if not success:
            await send_formatted_message(update, error_msg)
            return
    
    # Get category name
    if category_args:
        category_input = " ".join(category_args).lower()
    else:
        await send_formatted_message(update, "❌ Vui lòng chỉ định tên danh mục\n💡 Ví dụ: `/category ăn uống`")
        return
    
    # Find matching category
    matched_category = _find_matching_category(category_input)
    if not matched_category:
        available_categories = ", ".join(EXPENSE_CATEGORIES)
        message = f"""❌ *KHÔNG TÌM THẤY DANH MỤC*

🔍 *Tìm kiếm:* `{category_input}`

*📂 CÁC DANH MỤC CÓ SẴN:*
{available_categories}

*💡 VÍ DỤ:*
• `/category ăn uống`
• `/category mèo`
• `/category công trình 8/2025` (tháng lương 8 = 26/7-25/8/2025)"""
        await send_formatted_message(update, message)
        return
    
    # Get expenses for this category and salary month
    month_start, month_end = get_month_date_range(target_year, target_month)
    expenses = db.get_expenses_by_category(user_id, matched_category, month_start)
    
    if not expenses.data:
        category_emoji = get_category_emoji(matched_category)
        date_range = get_salary_month_display(target_year, target_month)
        message = f"""📂 *KHÔNG CÓ CHI TIÊU*

{category_emoji} *{matched_category.upper()} - THÁNG LƯƠNG {target_month}/{target_year}*
📅 *({date_range})*

Không có chi tiêu nào cho danh mục này trong tháng lương {target_month}/{target_year}

💡 _Thử danh mục khác hoặc tháng khác_"""
        await send_formatted_message(update, message)
        return
    
    # Get budget information
    from .budget_handlers import calculate_remaining_budget
    remaining_budget = calculate_remaining_budget(user_id, month_start)
    
    # Calculate total spent in this category
    total_spent = sum(float(expense["amount"]) for expense in expenses.data)
    
    # Format budget info
    budget_section = ""
    if matched_category in remaining_budget:
        budget_data = remaining_budget[matched_category]
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
Đặt budget cho danh mục này: `/budget {matched_category} [số tiền]`"""
    
    # Sort expenses by date (newest first) and format all
    sorted_expenses = sorted(expenses.data, key=lambda x: x["date"], reverse=True)
    expense_lines = [format_expense_item(expense) for expense in sorted_expenses]
    
    category_emoji = get_category_emoji(matched_category)
    date_range = get_salary_month_display(target_year, target_month)
    
    message = f"""{category_emoji} *TẤT CẢ CHI TIÊU {matched_category.upper()}*

📊 *Tháng lương {target_month}/{target_year}*
📅 *({date_range})*

{chr(10).join(expense_lines)}{budget_section}

💰 *Tổng chi tiêu:* `{format_currency(total_spent)}`
📊 *Số giao dịch:* {len(sorted_expenses)} lần"""
    
    await send_long_message(update, message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show quick help in Vietnamese"""
    if not await check_authorization(update):
        return
    
    await send_formatted_message(update, get_message("help"))

async def monthly_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate monthly summary: /summary or /summary 8/2025"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    # Parse date argument
    if args:
        success, target_month, target_year, error_msg = parse_date_argument(args[0])
        if not success:
            await send_formatted_message(update, error_msg)
            return
    else:
        # Use current salary month
        target_month, target_year = get_current_salary_month()
    
    # Get data for the target salary month
    month_start, month_end = get_month_date_range(target_year, target_month)
    expenses = db.get_monthly_expenses(user_id, month_start)
    income = db.get_monthly_income(user_id, month_start)
    
    # Auto-add subscriptions on 26th
    subscription_expenses = await _add_monthly_subscriptions(user_id, target_year, target_month, month_start, expenses)
    if subscription_expenses:
        expenses = db.get_monthly_expenses(user_id, month_start)
    
    # Calculate breakdown
    from .budget_handlers import get_total_budget
    from .income_handlers import calculate_income_by_type, calculate_expenses_by_income_type
    from .wishlist_handlers import get_wishlist_priority_sums
    
    total_budget = get_total_budget(user_id)
    income_breakdown = calculate_income_by_type(user_id, month_start)
    expense_breakdown = calculate_expenses_by_income_type(user_id, month_start)
    wishlist_sums = get_wishlist_priority_sums(user_id)
    
    total_expenses = expense_breakdown["total"]
    total_income = income_breakdown["total"]
    net_savings = total_income - total_expenses
    
    # Calculate money left after different wishlist levels
    money_after_level1 = net_savings - wishlist_sums["level1"]
    money_after_level1_and_2 = net_savings - wishlist_sums["level1_and_2"]
    
    # Budget analysis
    budget_remaining = total_budget - total_expenses if total_budget > 0 else 0
    money_after_all = budget_remaining - wishlist_sums["level1_and_2"]
    
    # Format subscription info
    subscription_info = ""
    if subscription_expenses:
        sub_names = [sub["description"].replace(" (subscription)", "") for sub in subscription_expenses]
        subscription_info = f"\n🔄 _Đã thêm subscriptions: {', '.join(sub_names)}_"
    
    # Format budget info
    budget_info = ""
    if total_budget > 0:
        if budget_remaining >= 0:
            budget_info = get_template("budget_section",
                budget_total=format_currency(total_budget),
                budget_status="✅",
                status_text="Còn lại",
                amount=format_currency(budget_remaining)
            )
        else:
            budget_info = get_template("budget_section",
                budget_total=format_currency(total_budget),
                budget_status="⚠️",
                status_text="Vượt budget",
                amount=format_currency(abs(budget_remaining))
            )
    
    # Add enhanced wishlist planning info to budget section
    if wishlist_sums["level1"] > 0 or wishlist_sums["level2"] > 0:
        budget_info += f"\n\n🛍️ *WISHLIST ANALYSIS:*"
        
        if wishlist_sums["level1"] > 0:
            budget_info += f"\n🔒 *Level 1 (Untouchable):* `{format_currency(wishlist_sums['level1'])}`"
        
        if wishlist_sums["level2"] > 0:
            budget_info += f"\n🚨 *Level 2 (Next Sale):* `{format_currency(wishlist_sums['level2'])}`"
        
        # Money left analysis
        if money_after_level1 >= 0:
            budget_info += f"\n✅ *Sau Level 1:* `{format_currency(money_after_level1)}`"
        else:
            budget_info += f"\n⚠️ *Thiếu cho Level 1:* `{format_currency(abs(money_after_level1))}`"
        
        if money_after_level1_and_2 >= 0:
            budget_info += f"\n✅ *Sau Level 1+2:* `{format_currency(money_after_level1_and_2)}`"
        else:
            budget_info += f"\n⚠️ *Thiếu cho Level 1+2:* `{format_currency(abs(money_after_level1_and_2))}`"
        
        # Budget + wishlist analysis
        if total_budget > 0:
            if money_after_all >= 0:
                budget_info += f"\n💰 *Sau Budget+Level1+2:* `{format_currency(money_after_all)}`"
            else:
                budget_info += f"\n🔴 *Vượt Budget+Level1+2:* `{format_currency(abs(money_after_all))}`"
    
    # Get salary month display range
    date_range = get_salary_month_display(target_year, target_month)
    
    # Create summary using template
    message = get_template("summary_report",
        month=target_month,
        year=target_year,
        date_range=date_range,
        subscription_info=subscription_info,
        total_income=format_currency(total_income),
        total_expenses=format_currency(total_expenses),
        net_savings=format_currency(net_savings),
        construction_income=format_currency(income_breakdown["construction"]),
        construction_expense=format_currency(expense_breakdown["construction"]),
        construction_net=format_currency(income_breakdown["construction"] - expense_breakdown["construction"]),
        general_income=format_currency(income_breakdown["general"]),
        general_expense=format_currency(expense_breakdown["general"]),
        general_net=format_currency(income_breakdown["general"] - expense_breakdown["general"]),
        budget_info=budget_info,
        expense_count=len(expenses.data),
        income_count=len(income.data)
    )
    
    await send_formatted_message(update, message)

async def list_expenses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simple /list command - always shows overview of all categories with top 8 items each"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    
    # Always show all categories with top 8 items each + budget info + wishlist analysis
    await _show_all_categories_expenses(update, user_id)

# Helper functions
async def _show_all_categories_expenses(update: Update, user_id: int):
    """Show all categories with top 8 items each + budget info + wishlist analysis + account info"""
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
Hãy bắt đầu ghi chi tiêu bằng cách nhắn: `50k cà phê`"""
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

    print(f"DEBUG - Account balances for user {user_id}: {account_balances}")
    
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
        
        # Enhanced category header with account info
        header = f"""{category_emoji} *{category.upper()}* - `{format_currency(category_total)}`{budget_info}
{account_emoji} _{account_name}: {format_currency(account_balance)}_{balance_warning}"""
        
        # Top 8 items
        items = sorted(expenses_by_category[category], key=lambda x: x["date"], reverse=True)[:8]
        expense_items = [format_expense_item(item) for item in items]
        
        # More items info
        if len(expenses_by_category[category]) > 8:
            remaining_count = len(expenses_by_category[category]) - 8
            more_info = get_template("more_items", count=remaining_count)
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
    
    await send_long_message(update, message)

# Add this helper function at the end of the file
async def _initialize_all_accounts(user_id):
    """Initialize all account types with 0 balance"""
    from datetime import datetime
    
    all_account_types = ["need", "fun", "saving", "invest", "construction"]
    
    for account_type in all_account_types:
        account_data = {
            "user_id": user_id,
            "account_type": account_type,
            "current_balance": 0,
            "last_updated": datetime.now().isoformat()
        }
        db.upsert_account(account_data)

def _find_matching_category(category_input: str) -> str:
    """Find matching category with better Vietnamese support"""
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

async def _add_monthly_subscriptions(user_id, target_year, target_month, month_start, expenses):
    """Add monthly subscriptions to expenses if not already added - now uses 26th timing"""
    from utils import is_salary_month_start_today
    
    subscriptions = db.get_subscriptions(user_id)
    subscription_expenses = []
    
    if subscriptions.data:
        for subscription in subscriptions.data:
            # Check if subscription expense already exists for this salary month
            existing_sub_expense = None
            for expense in expenses.data:
                if (expense["description"] == f"{subscription['service_name']} (subscription)" and
                    expense["date"] >= month_start.isoformat() and
                    expense["date"] <= f"{target_year}-{target_month:02d}-25"):
                    existing_sub_expense = expense
                    break
            
            # If not exists, add it (using month_start which is the 26th)
            if not existing_sub_expense:
                subscription_expense = {
                    "user_id": user_id,
                    "amount": subscription["amount"],
                    "description": f"{subscription['service_name']} (subscription)",
                    "category": DEFAULT_SUBSCRIPTION_CATEGORY,
                    "date": month_start.isoformat()  # This is the 26th of previous calendar month
                }
                
                db.insert_expense(subscription_expense)
                subscription_expenses.append(subscription_expense)
    
    return subscription_expenses