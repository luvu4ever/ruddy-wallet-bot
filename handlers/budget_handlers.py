from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, date
from difflib import get_close_matches

from database import db
from utils import (
    check_authorization, send_formatted_message, safe_parse_amount,
    format_currency, validate_args
)
from config import EXPENSE_CATEGORIES, get_category_emoji

async def budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set budget for category: /budget ăn uống 1.5m"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not validate_args(args, 2):
        await send_formatted_message(update, "❌ Cách dùng: /budget ăn uống 1.5m\nhoặc /budget mèo 500k\nhoặc /budget an uong 1tr (gần giống cũng được)")
        return
    
    # Parse amount (last argument)
    success, budget_amount, error_msg = safe_parse_amount(args[-1])
    if not success:
        await send_formatted_message(update, "❌ Số tiền không hợp lệ. Ví dụ: /budget ăn uống 1.5m")
        return
    
    # Parse category (all arguments except last)
    category_input = " ".join(args[:-1]).lower().strip()
    
    # Find matching category
    matched_category = _find_matching_category(category_input)
    if not matched_category:
        categories_list = ", ".join(EXPENSE_CATEGORIES)
        message = f"❌ Không tìm thấy category '{category_input}'\n\n📂 *Categories có sẵn:*\n{categories_list}"
        await send_formatted_message(update, message)
        return
    
    # Insert or update budget plan
    budget_data = {
        "user_id": user_id,
        "category": matched_category,
        "budget_amount": budget_amount
    }
    
    db.insert_budget_plan(budget_data)
    
    # Show category emoji
    category_emoji = get_category_emoji(matched_category)
    
    message = f"✅ Đã đặt budget!\n{category_emoji} *{matched_category}*: {format_currency(budget_amount)}/tháng"
    await send_formatted_message(update, message)

async def budget_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all budget plans: /budgetlist"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    
    # Get budget plans
    budget_data = db.get_budget_plans(user_id)
    
    if not budget_data.data:
        await send_formatted_message(update, "💰 Chưa có budget plan nào!\n\nDùng /budget [category] [amount] để đặt budget\nVí dụ: /budget ăn uống 1.5m")
        return
    
    # Sort by budget amount (high to low)
    budgets = sorted(budget_data.data, key=lambda x: x.get("budget_amount", 0), reverse=True)
    
    budget_text = _format_budget_list(budgets)
    await send_formatted_message(update, budget_text)

def calculate_remaining_budget(user_id, month_start):
    """Calculate remaining budget for all categories"""
    try:
        # Get budget plans
        budget_data = db.get_budget_plans(user_id)
        if not budget_data.data:
            return {}
        
        # Get this month's expenses
        expenses_data = db.get_monthly_expenses(user_id, month_start)
        
        # Calculate spent amount by category
        spent_by_category = _calculate_spent_by_category(expenses_data.data)
        
        # Calculate remaining budget
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
        
    except Exception as e:
        print(f"Error calculating remaining budget: {e}")
        return {}

def get_total_budget(user_id):
    """Get total monthly budget for user"""
    try:
        budget_data = db.get_budget_plans(user_id)
        if not budget_data.data:
            return 0
        
        total = sum(float(budget["budget_amount"]) for budget in budget_data.data)
        return total
        
    except Exception as e:
        print(f"Error getting total budget: {e}")
        return 0

# Helper functions
def _find_matching_category(category_input: str) -> str:
    """Find matching category (exact match first, then close match)"""
    # Try exact match
    if category_input in EXPENSE_CATEGORIES:
        return category_input
    
    # Try close match
    close_matches = get_close_matches(category_input, EXPENSE_CATEGORIES, n=1, cutoff=0.6)
    if close_matches:
        return close_matches[0]
    
    return None

def _format_budget_list(budgets: list) -> str:
    """Format budget list for display"""
    budget_text = "💰 *Budget Plans:*\n\n"
    total_budget = 0
    
    for budget in budgets:
        category = budget["category"]
        amount = budget.get("budget_amount", 0)
        category_emoji = get_category_emoji(category)
        
        budget_text += f"{category_emoji} *{category}*: {format_currency(amount)}/tháng\n"
        total_budget += amount
    
    budget_text += f"\n💰 *Tổng budget*: {format_currency(total_budget)}/tháng"
    budget_text += f"\n📊 *Tổng budget*: {format_currency(total_budget * 12)}/năm"
    
    return budget_text

def _calculate_spent_by_category(expenses_data: list) -> dict:
    """Calculate spent amount by category"""
    spent_by_category = {}
    for expense in expenses_data:
        category = expense["category"]
        amount = float(expense["amount"])
        spent_by_category[category] = spent_by_category.get(category, 0) + amount
    
    return spent_by_category