import logging
from datetime import datetime, date
from telegram import Update
from telegram.ext import ContextTypes

from database import db
from ai_parser import parse_message_with_gemini, generate_monthly_summary
from utils import (
    check_authorization, send_formatted_message, send_long_message,
    parse_amount, safe_parse_amount, parse_date_argument, get_month_date_range,
    get_current_month, get_month_display, format_currency
)
from config import (
    get_message, get_template, DEFAULT_SUBSCRIPTION_CATEGORY
)

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_authorization(update):
        return
    
    user_data = {
        "telegram_id": update.effective_user.id,
        "first_name": update.effective_user.first_name,
        "username": update.effective_user.username
    }
    
    db.register_user(user_data)
    await send_formatted_message(update, get_message("welcome"))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    message_text = update.message.text
    
    from .month_end_handlers import handle_month_end_confirmation
    if await handle_month_end_confirmation(update, context, message_text):
        return
    
    parsed_data = parse_message_with_gemini(message_text, user_id)
    
    responses = []
    message_type = parsed_data.get("type", "unknown")
    
    if message_type == "expenses":
        for expense in parsed_data.get("expenses", []):
            try:
                expense_result = await _process_expense_simple(
                    user_id, expense["amount"], expense["description"], 
                    expense.get("category", "khác")
                )
                responses.append(expense_result)
                
            except Exception as e:
                logging.error(f"Error processing expense: {e}")
                responses.append("⛔ Lỗi khi xử lý chi tiêu")
    else:
        responses.append(get_message("unknown_message"))
    
    if responses:
        await update.message.reply_text("\n".join(responses))
        
async def _process_expense_simple(user_id, amount, description, category):
    from config import get_account_for_category, get_account_emoji_enhanced, get_account_name_enhanced, get_category_emoji
    from datetime import date
    
    account_type = get_account_for_category(category)
    
    expense_data = {
        "user_id": user_id,
        "amount": amount,
        "description": description,
        "category": category,
        "date": date.today().isoformat()
    }
    
    expense_result = db.insert_expense(expense_data)
    expense_id = expense_result.data[0]["id"] if expense_result.data else None
    
    result, new_balance = db.update_account_balance(
        user_id, account_type, -amount,
        "expense", f"Expense: {description}", expense_id
    )
    
    account_emoji = get_account_emoji_enhanced(account_type)
    account_name = get_account_name_enhanced(account_type)
    category_emoji = get_category_emoji(category)
    
    if new_balance < 0:
        return f"""⚠️ *ĐÃ GHI CHI TIÊU - SỐ ÂM!*

💰 *Chi tiêu*: {format_currency(amount)} - {description}
{category_emoji} *Danh mục*: {category}
{account_emoji} *Từ tài khoản*: {account_name}
🔴 *Số dư hiện tại*: {format_currency(new_balance)} _(Số ÂM!)_

⚠️ *CẢNH BÁO*: Tài khoản {account_name} đã âm {format_currency(abs(new_balance))}

💡 _Xem chi tiết: `/account {account_type}`_"""
    else:
        return f"""✅ *ĐÃ GHI CHI TIÊU!*

💰 *Chi tiêu*: {format_currency(amount)} - {description}
{category_emoji} *Danh mục*: {category}
{account_emoji} *Từ tài khoản*: {account_name}
💳 *Số dư còn lại*: {format_currency(new_balance)}

💡 _Xem chi tiết: `/account {account_type}`_"""

async def savings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await send_formatted_message(update, "⛔ Cách dùng: `/editsaving 500k`")
        return
    
    success, new_amount, error_msg = safe_parse_amount(args[0])
    if not success:
        await send_formatted_message(update, "⛔ Số tiền không hợp lệ. VD: `/editsaving 500k` hoặc `/editsaving 1.5tr`")
        return
    
    savings_data = {
        "user_id": user_id,
        "current_amount": new_amount,
        "last_updated": datetime.now().isoformat()
    }
    
    db.upsert_savings(savings_data)
    
    message = get_template("savings_update", amount=format_currency(new_amount))
    await send_formatted_message(update, message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_authorization(update):
        return
    
    await send_formatted_message(update, get_message("help"))

async def monthly_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if args:
        success, target_month, target_year, error_msg = parse_date_argument(args[0])
        if not success:
            await send_formatted_message(update, error_msg)
            return
    else:
        target_month, target_year = get_current_month()
    
    month_start, month_end = get_month_date_range(target_year, target_month)
    expenses = db.get_monthly_expenses(user_id, month_start)
    income = db.get_monthly_income(user_id, month_start)
    
    subscription_expenses = await _add_monthly_subscriptions(user_id, target_year, target_month, month_start, expenses)
    if subscription_expenses:
        expenses = db.get_monthly_expenses(user_id, month_start)
    
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
    
    money_after_level1 = net_savings - wishlist_sums["level1"]
    money_after_level1_and_2 = net_savings - wishlist_sums["level1_and_2"]
    
    budget_remaining = total_budget - total_expenses if total_budget > 0 else 0
    money_after_all = budget_remaining - wishlist_sums["level1_and_2"]
    
    subscription_info = ""
    if subscription_expenses:
        sub_names = [sub["description"].replace(" (subscription)", "") for sub in subscription_expenses]
        subscription_info = f"\n📄 _Đã thêm subscriptions: {', '.join(sub_names)}_"
    
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
    
    if wishlist_sums["level1"] > 0 or wishlist_sums["level2"] > 0:
        budget_info += f"\n\n🛒 *WISHLIST ANALYSIS:*"
        
        if wishlist_sums["level1"] > 0:
            budget_info += f"\n🔒 *Level 1 (Untouchable):* `{format_currency(wishlist_sums['level1'])}`"
        
        if wishlist_sums["level2"] > 0:
            budget_info += f"\n🚨 *Level 2 (Next Sale):* `{format_currency(wishlist_sums['level2'])}`"
        
        if money_after_level1 >= 0:
            budget_info += f"\n✅ *Sau Level 1:* `{format_currency(money_after_level1)}`"
        else:
            budget_info += f"\n⚠️ *Thiếu cho Level 1:* `{format_currency(abs(money_after_level1))}`"
        
        if money_after_level1_and_2 >= 0:
            budget_info += f"\n✅ *Sau Level 1+2:* `{format_currency(money_after_level1_and_2)}`"
        else:
            budget_info += f"\n⚠️ *Thiếu cho Level 1+2:* `{format_currency(abs(money_after_level1_and_2))}`"
        
        if total_budget > 0:
            if money_after_all >= 0:
                budget_info += f"\n💰 *Sau Budget+Level1+2:* `{format_currency(money_after_all)}`"
            else:
                budget_info += f"\n🔴 *Vượt Budget+Level1+2:* `{format_currency(abs(money_after_all))}`"
    
    date_range = get_month_display(target_year, target_month)
    
    message = get_template("summary_report",
        month=target_month,
        year=target_year,
        date_range=date_range,
        subscription_info=subscription_info,
        total_income=format_currency(total_income),
        total_expenses=format_currency(total_expenses),
        net_savings=format_currency(net_savings),
        mama_income=format_currency(income_breakdown["mama"]),
        mama_expense=format_currency(expense_breakdown["mama"]),
        mama_net=format_currency(income_breakdown["mama"] - expense_breakdown["mama"]),
        general_income=format_currency(income_breakdown["general"]),
        general_expense=format_currency(expense_breakdown["general"]),
        general_net=format_currency(income_breakdown["general"] - expense_breakdown["general"]),
        budget_info=budget_info,
        expense_count=len(expenses.data),
        income_count=len(income.data)
    )
    
    await send_formatted_message(update, message)

async def _add_monthly_subscriptions(user_id, target_year, target_month, month_start, expenses):
    is_month_start_today = datetime.now().day == 1
    
    subscriptions = db.get_subscriptions(user_id)
    subscription_expenses = []
    
    if subscriptions.data:
        for subscription in subscriptions.data:
            existing_sub_expense = None
            for expense in expenses.data:
                if (expense["description"] == f"{subscription['service_name']} (subscription)" and
                    expense["date"] >= month_start.isoformat() and
                    expense["date"] <= month_start.replace(day=31).isoformat()):
                    existing_sub_expense = expense
                    break
            
            if not existing_sub_expense:
                subscription_expense = {
                    "user_id": user_id,
                    "amount": subscription["amount"],
                    "description": f"{subscription['service_name']} (subscription)",
                    "category": DEFAULT_SUBSCRIPTION_CATEGORY,
                    "date": month_start.isoformat()
                }
                
                db.insert_expense(subscription_expense)
                subscription_expenses.append(subscription_expense)
    
    return subscription_expenses