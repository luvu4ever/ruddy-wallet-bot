import logging
from datetime import datetime, date
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes

from database import db
from ai_parser import parse_message_with_gemini, generate_monthly_summary
from utils import (
    check_authorization, send_formatted_message, send_long_message,
    parse_amount, format_currency, safe_parse_amount, parse_date_argument,
    get_month_date_range, MessageFormatter
)
from config import (
    EXPENSE_CATEGORIES, get_category_emoji, get_all_category_info, 
    get_message, DEFAULT_SUBSCRIPTION_CATEGORY
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
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Parse with Gemini
    parsed_data = parse_message_with_gemini(message_text, user_id)
    
    responses = []
    message_type = parsed_data.get("type", "unknown")
    
    # Handle different message types
    if message_type == "expenses":
        # Save expenses
        for expense in parsed_data.get("expenses", []):
            expense_data = {
                "user_id": user_id,
                "amount": expense["amount"],
                "description": expense["description"],
                "category": expense.get("category", "khác"),
                "date": date.today().isoformat()
            }
            
            db.insert_expense(expense_data)
            responses.append(f"💰 Spent: {format_currency(expense['amount'])} - {expense['description']} ({expense.get('category', 'khác')})")
    else:
        responses.append(get_message("unknown_message"))
    
    if responses:
        await update.message.reply_text("\n".join(responses))

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
    
    message = f"✅ Đã cập nhật tiết kiệm!\n💰 *Tiết kiệm hiện tại*: {format_currency(new_amount)}"
    await send_formatted_message(update, message)

async def category_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show expenses by category: /category ăn uống"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        # Show all categories
        category_info = get_all_category_info()
        message = f"📂 *Danh mục chi tiêu:*\n\n{category_info}\n\nDùng: `/category [tên category]` để xem chi tiết"
        await send_formatted_message(update, message)
        return
    
    category = " ".join(args).lower()
    
    # Get this month's expenses for this category
    today = datetime.now()
    month_start = today.replace(day=1).date()
    
    expenses = db.get_expenses_by_category(user_id, category, month_start)
    
    if not expenses.data:
        message = f"📂 Không có chi tiêu nào cho danh mục '{category}' tháng này"
        await send_formatted_message(update, message)
        return
    
    # Group by description and sum amounts
    items_summary = defaultdict(lambda: {"total": 0, "count": 0})
    
    for expense in expenses.data:
        desc = expense["description"]
        amount = float(expense["amount"])
        items_summary[desc]["total"] += amount
        items_summary[desc]["count"] += 1
    
    # Create summary
    total_category = sum(item["total"] for item in items_summary.values())
    
    summary_lines = []
    for desc, data in sorted(items_summary.items(), key=lambda x: x[1]["total"], reverse=True):
        if data["count"] > 1:
            summary_lines.append(f"• {desc}: {format_currency(data['total'])} ({data['count']} lần)")
        else:
            summary_lines.append(f"• {desc}: {format_currency(data['total'])}")
    
    # Add special emoji for different categories
    category_emoji = get_category_emoji(category)
    
    summary_text = f"{category_emoji} *{category.title()}* - Tháng này\n\n"
    summary_text += "\n".join(summary_lines[:15])  # Limit to 15 items
    summary_text += f"\n\n💰 *Tổng cộng: {format_currency(total_category)}*"
    
    if len(summary_lines) > 15:
        summary_text += f"\n\n... và {len(summary_lines) - 15} mục khác"
    
    await send_formatted_message(update, summary_text)

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
        # Use current month
        today = datetime.now()
        target_month = today.month
        target_year = today.year
    
    # Calculate month boundaries
    month_start, month_end = get_month_date_range(target_year, target_month)
    
    # Get expenses and income for the target month
    expenses = db.get_monthly_expenses(user_id, month_start)
    income = db.get_monthly_income(user_id, month_start)
    
    # Auto-add subscriptions to expenses for this month
    subscription_expenses = await _add_monthly_subscriptions(user_id, target_year, target_month, month_start, expenses)
    
    # Refresh expenses data after adding subscriptions
    if subscription_expenses:
        expenses = db.get_monthly_expenses(user_id, month_start)
    
    # Get total budget
    from .budget_handlers import get_total_budget
    total_budget = get_total_budget(user_id)
    
    # Generate enhanced summary data
    expense_data = expenses.data
    income_data = income.data
    
    # Calculate totals with income type separation
    from .income_handlers import calculate_income_by_type, calculate_expenses_by_income_type
    income_breakdown = calculate_income_by_type(user_id, month_start)
    expense_breakdown = calculate_expenses_by_income_type(user_id, month_start)
    
    total_expenses = expense_breakdown["total"]
    total_income = income_breakdown["total"]
    
    # Show added subscriptions
    subscription_info = ""
    if subscription_expenses:
        sub_names = [sub["description"].replace(" (subscription)", "") for sub in subscription_expenses]
        subscription_info = f"\n🔄 *Đã thêm subscriptions*: {', '.join(sub_names)}"
    
    # Create income/expense breakdown info
    breakdown_info = _format_breakdown_info(income_breakdown, expense_breakdown)
    
    summary = generate_monthly_summary(expense_data, income_data, target_month, target_year)
    
    # Add budget information to summary
    budget_summary = _format_budget_summary(total_budget, total_expenses)
    
    if summary:
        full_summary = f"📊 *Báo cáo tháng {target_month}/{target_year}*{subscription_info}\n\n{summary}{breakdown_info}{budget_summary}"
        await send_formatted_message(update, full_summary)
    else:
        # Fallback summary with budget and breakdown
        fallback_summary = _format_fallback_summary(
            target_month, target_year, subscription_info, total_income, 
            total_expenses, expense_data, income_data, breakdown_info, budget_summary
        )
        await send_formatted_message(update, fallback_summary)

async def list_expenses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all expenses this month organized by category: /list"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    
    # Get this month's expenses
    today = datetime.now()
    month_start = today.replace(day=1).date()
    
    expenses = db.get_monthly_expenses(user_id, month_start)
    
    if not expenses.data:
        message = get_message("no_expenses_this_month", month=today.month, year=today.year)
        await send_formatted_message(update, message)
        return
    
    # Calculate remaining budget
    from .budget_handlers import calculate_remaining_budget
    remaining_budget = calculate_remaining_budget(user_id, month_start)
    
    # Group expenses by category
    expenses_by_category = defaultdict(list)
    total_month = 0
    
    for expense in expenses.data:
        category = expense["category"]
        amount = float(expense["amount"])
        description = expense["description"]
        date = expense["date"]
        
        expenses_by_category[category].append({
            "amount": amount,
            "description": description,
            "date": date
        })
        total_month += amount
    
    # Build response
    response_text = _build_expense_list_response(
        today, expenses_by_category, remaining_budget, total_month, user_id, month_start
    )
    
    # Send long message (will split if needed)
    await send_long_message(update, response_text)

# Helper functions
async def _add_monthly_subscriptions(user_id, target_year, target_month, month_start, expenses):
    """Add monthly subscriptions to expenses if not already added"""
    subscriptions = db.get_subscriptions(user_id)
    subscription_expenses = []
    
    if subscriptions.data:
        for subscription in subscriptions.data:
            # Check if subscription expense already exists for this month
            existing_sub_expense = None
            for expense in expenses.data:
                if (expense["description"] == f"{subscription['service_name']} (subscription)" and
                    expense["date"][:7] == f"{target_year}-{target_month:02d}"):
                    existing_sub_expense = expense
                    break
            
            # If not exists, add it
            if not existing_sub_expense:
                subscription_expense = {
                    "user_id": user_id,
                    "amount": subscription["amount"],
                    "description": f"{subscription['service_name']} (subscription)",
                    "category": DEFAULT_SUBSCRIPTION_CATEGORY,
                    "date": month_start.isoformat()
                }
                
                # Add to database
                db.insert_expense(subscription_expense)
                
                # Add to current expense list for summary calculation
                subscription_expenses.append(subscription_expense)
    
    return subscription_expenses

def _format_breakdown_info(income_breakdown, expense_breakdown):
    """Format income/expense breakdown information"""
    return f"""
📊 *Phân tích theo loại:*

🏗️ *CÔNG TRÌNH:*
• Thu nhập: {format_currency(income_breakdown["construction"])}
• Chi tiêu: {format_currency(expense_breakdown["construction"])}
• Lãi/lỗ: {format_currency(income_breakdown["construction"] - expense_breakdown["construction"])}

💰 *KHÁC (salary + random):*
• Thu nhập: {format_currency(income_breakdown["general"])}
• Chi tiêu: {format_currency(expense_breakdown["general"])}
• Lãi/lỗ: {format_currency(income_breakdown["general"] - expense_breakdown["general"])}
    """

def _format_budget_summary(total_budget, total_expenses):
    """Format budget summary information"""
    if total_budget <= 0:
        return ""
    
    remaining_budget = total_budget - total_expenses
    if remaining_budget >= 0:
        return f"\n💰 *Budget tháng này*: {format_currency(total_budget)}\n✅ *Còn lại*: {format_currency(remaining_budget)}"
    else:
        return f"\n💰 *Budget tháng này*: {format_currency(total_budget)}\n⚠️ *Vượt budget*: {format_currency(abs(remaining_budget))}"

def _format_fallback_summary(target_month, target_year, subscription_info, total_income, 
                            total_expenses, expense_data, income_data, breakdown_info, budget_summary):
    """Format fallback summary when AI summary is not available"""
    net_savings = total_income - total_expenses
    
    return f"""
📊 *Báo cáo tháng {target_month}/{target_year}*{subscription_info}

💵 Tổng thu nhập: {format_currency(total_income)}
💰 Tổng chi tiêu: {format_currency(total_expenses)}
📈 Tiết kiệm ròng: {format_currency(net_savings)}

Chi tiêu: {len(expense_data)} lần
Thu nhập: {len(income_data)} lần{breakdown_info}{budget_summary}
    """

def _build_expense_list_response(today, expenses_by_category, remaining_budget, total_month, user_id, month_start):
    """Build the expense list response text"""
    response_text = f"📝 *Chi tiêu tháng {today.month}/{today.year}*\n\n"
    
    # Sort categories by total amount (highest first)
    category_totals = {}
    for category, items in expenses_by_category.items():
        category_totals[category] = sum(item["amount"] for item in items)
    
    sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    
    for category, category_total in sorted_categories:
        # Add category emoji
        category_emoji = get_category_emoji(category)
        
        # Get budget info if available
        budget_info = ""
        if category in remaining_budget:
            budget_data = remaining_budget[category]
            remaining = budget_data["remaining"]
            if remaining >= 0:
                budget_info = f" (còn lại: {format_currency(remaining)})"
            else:
                budget_info = f" (⚠️ vượt: {format_currency(abs(remaining))})"
        
        response_text += f"{category_emoji} *{category.upper()}* - {format_currency(category_total)}{budget_info}\n"
        
        # Sort items in category by date (newest first)
        items = sorted(expenses_by_category[category], key=lambda x: x["date"], reverse=True)
        
        for item in items:
            date_str = item["date"][5:10]  # MM-DD format
            response_text += f"  • {date_str}: {format_currency(item['amount'])} - {item['description']}\n"
        
        response_text += "\n"
    
    response_text += f"💰 *TỔNG CỘNG: {format_currency(total_month)}*"
    
    # Calculate income/expense breakdown for list
    from .income_handlers import calculate_income_by_type, calculate_expenses_by_income_type
    income_breakdown = calculate_income_by_type(user_id, month_start)
    expense_breakdown = calculate_expenses_by_income_type(user_id, month_start)
    
    # Add breakdown info at the end
    breakdown_summary = f"""
📊 *Phân tích thu chi:*

🏗️ *CÔNG TRÌNH:* Thu {format_currency(income_breakdown["construction"])} - Chi {format_currency(expense_breakdown["construction"])} = {format_currency(income_breakdown["construction"] - expense_breakdown["construction"])}

💰 *KHÁC:* Thu {format_currency(income_breakdown["general"])} - Chi {format_currency(expense_breakdown["general"])} = {format_currency(income_breakdown["general"] - expense_breakdown["general"])}
    """
    
    response_text += f"\n{breakdown_summary}"
    
    return response_text