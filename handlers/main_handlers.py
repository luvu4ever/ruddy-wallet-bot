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
    parse_amount, safe_parse_amount, parse_date_argument, get_month_date_range
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
    
    message = get_template("savings_update", amount=format_currency(new_amount))
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
        message = f"""📂 *DANH MỤC CHI TIÊU*

*📂 TẤT CẢ DANH MỤC*

{category_info}

💡 Dùng: `/category [tên category]` để xem chi tiết"""
        await send_formatted_message(update, message)
        return
    
    category = " ".join(args).lower()
    
    # Get this month's expenses for this category
    today = datetime.now()
    month_start = today.replace(day=1).date()
    
    expenses = db.get_expenses_by_category(user_id, category, month_start)
    
    if not expenses.data:
        message = f"""📂 *KHÔNG CÓ CHI TIÊU*

📊 *DANH MỤC: {category.upper()}*

Không có chi tiêu nào cho danh mục này trong tháng {today.month}/{today.year}"""
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
            summary_lines.append(f"• {desc}: `{format_currency(data['total'])}` _{data['count']} lần_")
        else:
            summary_lines.append(f"• {desc}: `{format_currency(data['total'])}`")
    
    # Format using template
    category_emoji = get_category_emoji(category)
    
    message = get_template("category_summary",
        emoji=category_emoji,
        category=category.upper(),
        month=today.month,
        year=today.year,
        summary_lines="\n".join(summary_lines[:15]),
        total=format_currency(total_category)
    )
    
    if len(summary_lines) > 15:
        message += f"\n\n... và {len(summary_lines) - 15} mục khác"
    
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
        # Use current month
        today = datetime.now()
        target_month = today.month
        target_year = today.year
    
    # Get data for the target month
    month_start, month_end = get_month_date_range(target_year, target_month)
    expenses = db.get_monthly_expenses(user_id, month_start)
    income = db.get_monthly_income(user_id, month_start)
    
    # Auto-add subscriptions
    subscription_expenses = await _add_monthly_subscriptions(user_id, target_year, target_month, month_start, expenses)
    if subscription_expenses:
        expenses = db.get_monthly_expenses(user_id, month_start)
    
    # Calculate breakdown
    from .budget_handlers import get_total_budget
    from .income_handlers import calculate_income_by_type, calculate_expenses_by_income_type
    
    total_budget = get_total_budget(user_id)
    income_breakdown = calculate_income_by_type(user_id, month_start)
    expense_breakdown = calculate_expenses_by_income_type(user_id, month_start)
    
    total_expenses = expense_breakdown["total"]
    total_income = income_breakdown["total"]
    net_savings = total_income - total_expenses
    
    # Format subscription info
    subscription_info = ""
    if subscription_expenses:
        sub_names = [sub["description"].replace(" (subscription)", "") for sub in subscription_expenses]
        subscription_info = f"\n🔄 _Đã thêm subscriptions: {', '.join(sub_names)}_"
    
    # Format budget info
    budget_info = ""
    if total_budget > 0:
        remaining_budget = total_budget - total_expenses
        if remaining_budget >= 0:
            budget_info = get_template("budget_section",
                budget_total=format_currency(total_budget),
                budget_status="✅",
                status_text="Còn lại",
                amount=format_currency(remaining_budget)
            )
        else:
            budget_info = get_template("budget_section",
                budget_total=format_currency(total_budget),
                budget_status="⚠️",
                status_text="Vượt budget",
                amount=format_currency(abs(remaining_budget))
            )
    
    # Create summary using template
    message = get_template("summary_report",
        month=target_month,
        year=target_year,
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
    """Enhanced /list command with clean formatting"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    # Parse arguments
    if not args:
        # Default: show all categories with top 8 items each
        await _show_all_categories_expenses(update, user_id)
        return
    
    # Check if we have category name
    category_input = args[0].lower()
    matched_category = _find_matching_category(category_input)
    
    if not matched_category:
        await _show_all_categories_expenses(update, user_id)
        return
    
    # Parse date if provided
    if len(args) >= 2:
        success, target_month, target_year, error_msg = parse_date_argument(args[1])
        if not success:
            await send_formatted_message(update, error_msg)
            return
    else:
        today = datetime.now()
        target_month = today.month
        target_year = today.year
    
    # Show ALL expenses for specific category
    await _show_category_all_expenses(update, user_id, matched_category, target_month, target_year)

# Helper functions
async def _show_all_categories_expenses(update: Update, user_id: int):
    """Show all categories with top 8 items each + budget info"""
    today = datetime.now()
    month_start = today.replace(day=1).date()
    
    expenses = db.get_monthly_expenses(user_id, month_start)
    
    if not expenses.data:
        message = get_message("no_expenses_this_month", month=today.month, year=today.year)
        await send_formatted_message(update, message)
        return
    
    # Calculate remaining budget and group expenses
    from .budget_handlers import calculate_remaining_budget
    remaining_budget = calculate_remaining_budget(user_id, month_start)
    
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
        
        # Category header
        header = get_template("category_header",
            emoji=category_emoji,
            category=category.upper(),
            total=format_currency(category_total),
            budget_info=budget_info
        )
        
        # Top 8 items
        items = sorted(expenses_by_category[category], key=lambda x: x["date"], reverse=True)[:8]
        expense_items = [format_expense_item(item) for item in items]
        
        # More items info
        if len(expenses_by_category[category]) > 8:
            remaining_count = len(expenses_by_category[category]) - 8
            more_info = get_template("more_items", count=remaining_count)
            expense_items.append(more_info)
        
        categories_content.append(header + "\n" + "\n".join(expense_items))
    
    # Calculate breakdown
    from .income_handlers import calculate_income_by_type, calculate_expenses_by_income_type
    income_breakdown = calculate_income_by_type(user_id, month_start)
    expense_breakdown = calculate_expenses_by_income_type(user_id, month_start)
    
    # Create final message using template
    message = get_template("list_overview",
        month=today.month,
        year=today.year,
        categories_content="\n\n".join(categories_content),
        total=format_currency(total_month),
        construction_income=format_currency(income_breakdown["construction"]),
        construction_expense=format_currency(expense_breakdown["construction"]),
        construction_net=format_currency(income_breakdown["construction"] - expense_breakdown["construction"]),
        general_income=format_currency(income_breakdown["general"]),
        general_expense=format_currency(expense_breakdown["general"]),
        general_net=format_currency(income_breakdown["general"] - expense_breakdown["general"])
    )
    
    await send_long_message(update, message)

async def _show_category_all_expenses(update: Update, user_id: int, category: str, target_month: int, target_year: int):
    """Show ALL expenses for a specific category and month"""
    month_start, month_end = get_month_date_range(target_year, target_month)
    
    expenses = db.get_expenses_by_category(user_id, category, month_start)
    
    if not expenses.data:
        category_emoji = get_category_emoji(category)
        message = get_template("category_empty",
            emoji=category_emoji,
            category=category.upper(),
            month=target_month,
            year=target_year
        )
        await send_formatted_message(update, message)
        return
    
    # Sort by date (newest first) and format all expenses
    sorted_expenses = sorted(expenses.data, key=lambda x: x["date"], reverse=True)
    expense_lines = [format_expense_item(expense) for expense in sorted_expenses]
    total_category = sum(float(expense["amount"]) for expense in sorted_expenses)
    
    category_emoji = get_category_emoji(category)
    
    message = get_template("category_full",
        emoji=category_emoji,
        category=category.upper(),
        month=target_month,
        year=target_year,
        expenses_list="\n".join(expense_lines),
        total=format_currency(total_category),
        count=len(sorted_expenses)
    )
    
    await send_long_message(update, message)

def _find_matching_category(category_input: str) -> str:
    """Find matching category (exact match first, then close match)"""
    if category_input in EXPENSE_CATEGORIES:
        return category_input
    
    close_matches = get_close_matches(category_input, EXPENSE_CATEGORIES, n=1, cutoff=0.6)
    if close_matches:
        return close_matches[0]
    
    return None

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
                
                db.insert_expense(subscription_expense)
                subscription_expenses.append(subscription_expense)
    
    return subscription_expenses