from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, date

from database import db
from utils import check_authorization, send_formatted_message, safe_parse_amount, format_currency
from config import EXPENSE_CATEGORIES, get_category_emoji

async def budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set budget for category: /budget ăn uống 1.5m"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if len(args) < 2:
        await send_formatted_message(update, "❌ Cách dùng: `/budget ăn uống 1.5m`")
        return
    
    # Parse amount (last argument)
    success, budget_amount, _ = safe_parse_amount(args[-1])
    if not success:
        await send_formatted_message(update, "❌ Số tiền không hợp lệ")
        return
    
    # Parse category (all arguments except last)
    category_input = " ".join(args[:-1]).lower().strip()
    
    # Find matching category
    matched_category = None
    for category in EXPENSE_CATEGORIES:
        if category_input == category or category_input in category:
            matched_category = category
            break
    
    if not matched_category:
        categories_list = ", ".join(EXPENSE_CATEGORIES)
        await send_formatted_message(update, f"❌ Không tìm thấy category '{category_input}'\n\n📂 *Có sẵn:* {categories_list}")
        return
    
    # Save budget
    budget_data = {
        "user_id": user_id,
        "category": matched_category,
        "budget_amount": budget_amount
    }
    
    db.insert_budget_plan(budget_data)
    
    category_emoji = get_category_emoji(matched_category)
    message = f"✅ Đã đặt budget!\n{category_emoji} *{matched_category}*: {format_currency(budget_amount)}/tháng"
    await send_formatted_message(update, message)

async def budget_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all budget plans: /budgetlist"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    budget_data = db.get_budget_plans(user_id)
    
    if not budget_data.data:
        await send_formatted_message(update, "💰 Chưa có budget!\nDùng `/budget ăn uống 1.5m` để đặt budget")
        return
    
    # Sort by amount
    budgets = sorted(budget_data.data, key=lambda x: x.get("budget_amount", 0), reverse=True)
    
    budget_text = "💰 *BUDGET PLANS*\n\n"
    total_budget = 0
    
    for budget in budgets:
        category = budget["category"]
        amount = budget.get("budget_amount", 0)
        category_emoji = get_category_emoji(category)
        
        budget_text += f"{category_emoji} *{category}*: {format_currency(amount)}/tháng\n"
        total_budget += amount
    
    budget_text += f"\n💰 *Tổng budget*: {format_currency(total_budget)}/tháng"
    
    await send_formatted_message(update, budget_text)

def calculate_remaining_budget(user_id, month_start):
    """Calculate remaining budget for all categories - simplified"""
    try:
        # Get budget plans
        budget_data = db.get_budget_plans(user_id)
        if not budget_data.data:
            return {}
        
        # Get expenses
        expenses_data = db.get_monthly_expenses(user_id, month_start)
        
        # Calculate spent by category
        spent_by_category = {}
        if expenses_data.data:
            for expense in expenses_data.data:
                category = expense["category"]
                amount = float(expense["amount"])
                spent_by_category[category] = spent_by_category.get(category, 0) + amount
        
        # Calculate remaining
        remaining_budget = {}
        for budget in budget_data.data:
            category = budget["category"]
            budget_amount = float(budget["budget_amount"])
            spent_amount = spent_by_category.get(category, 0)
            remaining = budget_amount - spent_amount
            
            remaining_budget[category] = {
                "budget": budget_amount,
                "spent": spent_amount,
                "remaining": remaining
            }
        
        return remaining_budget
        
    except Exception:
        return {}

def get_total_budget(user_id):
    """Get total monthly budget for user - simplified"""
    try:
        budget_data = db.get_budget_plans(user_id)
        if not budget_data.data:
            return 0
        
        total = sum(float(budget["budget_amount"]) for budget in budget_data.data)
        return total
    except Exception:
        return 0