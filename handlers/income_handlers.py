from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, date

from database import db
from utils import check_authorization, send_formatted_message, safe_parse_amount, format_currency
from config import INCOME_TYPES, get_income_emoji, get_message

async def income_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add income: /income salary 3m lương tháng"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    # Show income types if no arguments
    if not args:
        await send_formatted_message(update, get_message("income_types"))
        return
    
    if len(args) < 2:
        await send_formatted_message(update, get_message("format_errors")["income_usage"])
        return
    
    # Parse arguments
    income_type = args[0].lower()
    success, amount, _ = safe_parse_amount(args[1])
    
    if not success:
        await send_formatted_message(update, "❌ Số tiền không hợp lệ")
        return
    
    description = " ".join(args[2:]) if len(args) > 2 else f"{income_type} income"
    
    # Validate income type
    if income_type not in INCOME_TYPES:
        message = get_message("format_errors")["invalid_income_type"].format(type=income_type)
        await send_formatted_message(update, message)
        return
    
    # Save income
    income_data = {
        "user_id": user_id,
        "amount": amount,
        "income_type": income_type,
        "description": description,
        "date": date.today().isoformat()
    }
    
    db.insert_income(income_data)
    
    # Response
    emoji = get_income_emoji(income_type)
    message = get_message("income_added", 
        emoji=emoji, 
        type=income_type, 
        amount=format_currency(amount), 
        description=description)
    await send_formatted_message(update, message)

def calculate_income_by_type(user_id, month_start):
    """Calculate income by construction vs general - simplified"""
    try:
        income_data = db.get_monthly_income(user_id, month_start)
        
        construction_income = 0
        general_income = 0
        
        if income_data.data:
            for income in income_data.data:
                amount = float(income["amount"])
                income_type = income.get("income_type", "random")
                
                if income_type == "construction":
                    construction_income += amount
                else:  # salary or random
                    general_income += amount
        
        return {
            "construction": construction_income,
            "general": general_income,
            "total": construction_income + general_income
        }
    except Exception:
        return {"construction": 0, "general": 0, "total": 0}

def calculate_expenses_by_income_type(user_id, month_start):
    """Calculate expenses by construction vs general categories - simplified"""
    try:
        expenses_data = db.get_monthly_expenses(user_id, month_start)
        
        construction_expenses = 0
        general_expenses = 0
        
        if expenses_data.data:
            for expense in expenses_data.data:
                amount = float(expense["amount"])
                category = expense["category"]
                
                if category == "công trình":
                    construction_expenses += amount
                else:  # all other categories
                    general_expenses += amount
        
        return {
            "construction": construction_expenses,
            "general": general_expenses,
            "total": construction_expenses + general_expenses
        }
    except Exception:
        return {"construction": 0, "general": 0, "total": 0}