from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, date

from database import db
from utils import check_authorization, send_formatted_message, safe_parse_amount, format_currency
from config import INCOME_TYPES, get_income_emoji, get_message

async def income_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced income command with automatic allocation: /income salary 3m lương tháng"""
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
    
    # Save income record
    income_data = {
        "user_id": user_id,
        "amount": amount,
        "income_type": income_type,
        "description": description,
        "date": date.today().isoformat()
    }
    
    income_result = db.insert_income(income_data)
    income_id = income_result.data[0]["id"] if income_result.data else None
    
    # Process allocation
    allocation_message = await _process_income_allocation(user_id, income_type, amount, description, income_id)
    
    # Response
    emoji = get_income_emoji(income_type)
    message = f"""✅ *ĐÃ THÊM THU NHẬP!*

{emoji} *{income_type}*: {format_currency(amount)}
📝 *{description}*

{allocation_message}"""
    
    await send_formatted_message(update, message)

# Add this helper function to income_handlers.py:

async def _process_income_allocation(user_id, income_type, amount, description, income_id):
    """Process income allocation to accounts"""
    
    if income_type == "construction":
        # Construction income goes directly to construction account
        await _add_to_account(user_id, "construction", amount, "income_allocation", 
                             f"Construction income: {description}", income_id)
        
        return f"🏗️ *Đã thêm vào tài khoản xây dựng*: {format_currency(amount)}"
    
    else:
        # Salary/random income gets allocated by percentages
        from .allocation_handlers import get_user_allocations, validate_allocations
        from config import ACCOUNT_DESCRIPTIONS
        
        allocations = get_user_allocations(user_id)
        
        # Check if user has allocations set up
        if not allocations:
            return f"⚠️ *Chưa thiết lập phân bổ!*\nDùng `/allocation` để thiết lập phân bổ thu nhập"
        
        # Validate allocations
        if not validate_allocations(allocations):
            total_pct = sum(allocations.values())
            return f"⚠️ *Cảnh báo*: Tổng phân bổ = {total_pct}% (không phải 100%)\n*Vui lòng kiểm tra `/allocation`*"
        
        # Allocate to accounts
        allocation_details = []
        
        for account_type in ["need", "fun", "saving", "invest"]:
            percentage = allocations[account_type]
            if percentage > 0:
                allocated_amount = amount * (percentage / 100)
                
                await _add_to_account(user_id, account_type, allocated_amount, "income_allocation",
                                     f"{description} ({percentage}%)", income_id)
                
                account_info = ACCOUNT_DESCRIPTIONS[account_type]
                allocation_details.append(f"{account_info['emoji']} *{account_info['name']}* ({percentage}%): {format_currency(allocated_amount)}")
        
        return "💰 *PHÂN BỔ TÀI KHOẢN*:\n" + "\n".join(allocation_details)

async def _add_to_account(user_id, account_type, amount, transaction_type, description, reference_id):
    """Add money to specific account with transaction logging"""
    
    # Get current balance
    account_data = db.get_account_by_type(user_id, account_type)
    current_balance = 0
    
    if account_data.data:
        current_balance = float(account_data.data[0].get("current_balance", 0))
    
    # Update balance
    new_balance = current_balance + amount
    
    account_update = {
        "user_id": user_id,
        "account_type": account_type,
        "current_balance": new_balance,
        "last_updated": datetime.now().isoformat()
    }
    
    db.upsert_account(account_update)
    
    # Log transaction
    transaction_data = {
        "user_id": user_id,
        "account_type": account_type,
        "transaction_type": transaction_type,
        "amount": amount,
        "description": description,
        "reference_id": reference_id
    }
    
    db.insert_account_transaction(transaction_data)
    
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