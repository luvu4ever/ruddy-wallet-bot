from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, date

from database import db
from utils import (
    check_authorization, send_formatted_message, safe_parse_amount,
    format_currency, validate_args
)
from config import INCOME_TYPES, get_income_types_list, get_income_emoji, get_message

async def income_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add income: /income construction 2m xây nhà or /income salary 3m lương tháng"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    # Show income types if no arguments
    if not args:
        income_types_text = get_income_types_list()
        message = get_message("income_types", income_types=income_types_text)
        await send_formatted_message(update, message)
        return
    
    if not validate_args(args, 2):
        await send_formatted_message(update, get_message("format_errors")["income_usage"])
        return
    
    # Parse arguments: type amount [description]
    income_type = args[0].lower()
    success, amount, error_msg = safe_parse_amount(args[1])
    
    if not success:
        await send_formatted_message(update, get_message("format_errors")["invalid_amount"])
        return
    
    description = " ".join(args[2:]) if len(args) > 2 else f"{income_type} income"
    
    # Validate income type
    if income_type not in INCOME_TYPES:
        message = get_message("format_errors")["invalid_income_type"].format(type=income_type)
        await send_formatted_message(update, message)
        return
    
    # Create income record
    income_data = {
        "user_id": user_id,
        "amount": amount,
        "income_type": income_type,
        "description": description,
        "date": date.today().isoformat()
    }
    
    db.insert_income(income_data)
    
    # Get emoji and send confirmation
    emoji = get_income_emoji(income_type)
    message = get_message("income_added", 
        emoji=emoji, 
        type=income_type, 
        amount=format_currency(amount), 
        description=description)
    await send_formatted_message(update, message)

def calculate_income_by_type(user_id, month_start):
    """Calculate income separated by construction vs general"""
    try:
        # Get all income for the month
        income_data = db.get_monthly_income(user_id, month_start)
        
        construction_income = 0
        general_income = 0
        
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
        
    except Exception as e:
        print(f"Error calculating income by type: {e}")
        return {"construction": 0, "general": 0, "total": 0}

def calculate_expenses_by_income_type(user_id, month_start):
    """Calculate expenses separated by construction vs general categories"""
    try:
        # Get all expenses for the month
        expenses_data = db.get_monthly_expenses(user_id, month_start)
        
        construction_expenses = 0
        general_expenses = 0
        
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
        
    except Exception as e:
        print(f"Error calculating expenses by income type: {e}")
        return {"construction": 0, "general": 0, "total": 0}