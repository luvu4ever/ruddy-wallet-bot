import logging
from datetime import datetime, date
from telegram import Update
from telegram.ext import ContextTypes

from database import db
from ai_parser import parse_message_with_gemini, generate_monthly_summary
from utils import (
    check_authorization, send_formatted_message, send_long_message,
    parse_amount, safe_parse_amount, parse_date_argument, get_month_date_range,
    get_current_salary_month, get_salary_month_display  # NEW: salary cycle functions
)
from config import (
    get_message, get_template, DEFAULT_SUBSCRIPTION_CATEGORY,
    format_currency
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