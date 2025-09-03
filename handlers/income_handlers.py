from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, date

from database import db
from utils import check_authorization, send_formatted_message, safe_parse_amount, format_currency
from config import INCOME_TYPES, get_income_emoji, get_message

async def income_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await send_formatted_message(update, get_message("income_types"))
        return
    
    if len(args) < 2:
        await send_formatted_message(update, get_message("format_errors")["income_usage"])
        return
    
    income_type = args[0].lower()
    success, amount, _ = safe_parse_amount(args[1])
    
    if not success:
        await send_formatted_message(update, "⚠ Số tiền không hợp lệ")
        return
    
    description = " ".join(args[2:]) if len(args) > 2 else f"{income_type} income"
    
    if income_type not in INCOME_TYPES:
        message = get_message("format_errors")["invalid_income_type"].format(type=income_type)
        await send_formatted_message(update, message)
        return
    
    income_data = {
        "user_id": user_id,
        "amount": amount,
        "income_type": income_type,
        "description": description,
        "date": date.today().isoformat()
    }
    
    income_result = db.insert_income(income_data)
    income_id = income_result.data[0]["id"] if income_result.data else None
    
    allocation_message = await _process_income_allocation(user_id, income_type, amount, description, income_id)
    
    emoji = get_income_emoji(income_type)
    message = f"""✅ *ĐÃ THÊM THU NHẬP!*

{emoji} *{income_type}*: {format_currency(amount)}
📝 *{description}*

{allocation_message}"""
    
    await send_formatted_message(update, message)

async def _process_income_allocation(user_id, income_type, amount, description, income_id):
    if income_type == "mama":
        db.update_account_balance(
            user_id, "mama", amount, "income_allocation", 
            f"Mama income: {description}", income_id
        )
        
        return f"✅ *Đã thêm vào tài khoản mama*: {format_currency(amount)}"
    
    else:
        from .allocation_handlers import get_user_allocations, validate_allocations
        from config import ACCOUNT_DESCRIPTIONS
        
        allocations = get_user_allocations(user_id)
        
        if not allocations:
            return f"⚠️ *Chưa thiết lập phân bổ!*\nDùng `/allocation` để thiết lập phân bổ thu nhập"
        
        if not validate_allocations(allocations):
            total_pct = sum(allocations.values())
            return f"⚠️ *Cảnh báo*: Tổng phân bổ = {total_pct}% (không phải 100%)\n*Vui lòng kiểm tra `/allocation`*"
        
        allocation_details = []
        
        for account_type in ["need", "fun", "saving", "invest"]:
            percentage = allocations[account_type]
            if percentage > 0:
                allocated_amount = amount * (percentage / 100)
                
                db.update_account_balance(
                    user_id, account_type, allocated_amount, "income_allocation",
                    f"{description} ({percentage}%)", income_id
                )
                
                account_info = ACCOUNT_DESCRIPTIONS[account_type]
                allocation_details.append(f"{account_info['emoji']} *{account_info['name']}* ({percentage}%): {format_currency(allocated_amount)}")
        
        return "💰 *PHÂN BỔ TÀI KHOẢN*:\n" + "\n".join(allocation_details)

def calculate_income_by_type(user_id, month_start):
    try:
        income_data = db.get_monthly_income(user_id, month_start)
        
        mama_income = 0
        general_income = 0
        
        if income_data.data:
            for income in income_data.data:
                amount = float(income["amount"])
                income_type = income.get("income_type", "random")
                
                if income_type == "mama":
                    mama_income += amount
                else:
                    general_income += amount
        
        return {
            "mama": mama_income,
            "general": general_income,
            "total": mama_income + general_income
        }
    except Exception:
        return {"mama": 0, "general": 0, "total": 0}

def calculate_expenses_by_income_type(user_id, month_start):
    try:
        expenses_data = db.get_monthly_expenses(user_id, month_start)
        
        mama_expenses = 0
        general_expenses = 0
        
        if expenses_data.data:
            for expense in expenses_data.data:
                amount = float(expense["amount"])
                category = expense["category"]
                
                if category == "mama":
                    mama_expenses += amount
                else:
                    general_expenses += amount
        
        return {
            "mama": mama_expenses,
            "general": general_expenses,
            "total": mama_expenses + general_expenses
        }
    except Exception:
        return {"mama": 0, "general": 0, "total": 0}