from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime

from database import db
from utils import check_authorization, send_formatted_message, safe_parse_amount, format_currency
from config import (
    ACCOUNT_DESCRIPTIONS, get_account_emoji_enhanced, 
    get_account_description_enhanced, get_account_name_enhanced
)

async def account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced accounts view with allocation info: /account [account_type]"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    # If specific account requested, show details
    if args:
        account_type = args[0].lower()
        await _show_account_details(update, user_id, account_type)
        return
    
    # Show all accounts overview
    await _show_all_accounts_enhanced(update, user_id)

async def _show_all_accounts_enhanced(update: Update, user_id: int):
    """Show enhanced view of all 5 accounts with allocation info"""
    
    # Get account balances
    accounts_data = db.get_accounts(user_id)
    
    # Initialize accounts if needed
    if not accounts_data.data:
        await _initialize_all_accounts(user_id)
        accounts_data = db.get_accounts(user_id)
    
    # Get allocation settings
    from .allocation_handlers import get_user_allocations
    allocations = get_user_allocations(user_id)
    
    # Build accounts dict
    accounts_dict = {acc["account_type"]: acc for acc in accounts_data.data}
    
    # Build message
    message = "💳 *TÀI KHOẢN CỦA BẠN*\n\n"
    
    # Show all 5 accounts
    account_balances = {}
    total_balance = 0
    
    for account_type in ["need", "fun", "saving", "invest", "construction"]:
        account_info = ACCOUNT_DESCRIPTIONS[account_type]
        
        balance = 0
        if account_type in accounts_dict:
            balance = float(accounts_dict[account_type].get("current_balance", 0))
        
        account_balances[account_type] = balance
        total_balance += balance
        
        # Show allocation percentage for income-allocated accounts
        allocation_text = ""
        if account_type in allocations:
            percentage = allocations[account_type]
            allocation_text = f" ({percentage}%)"
        
        message += f"{account_info['emoji']} *{account_info['name']}*{allocation_text}: `{format_currency(balance)}`\n"
    
    # Summary section
    spending_accounts_total = account_balances["need"] + account_balances["fun"]
    
    message += f"\n📊 *TỔNG KẾT*\n"
    message += f"🛒 *Tiêu dùng* (Thiết yếu + Giải trí): `{format_currency(spending_accounts_total)}`\n"
    message += f"💰 *Tiết kiệm*: `{format_currency(account_balances['saving'])}`\n"
    message += f"📈 *Đầu tư*: `{format_currency(account_balances['invest'])}`\n"
    message += f"🏗️ *Xây dựng*: `{format_currency(account_balances['construction'])}`\n"
    message += f"💎 *Tổng tài sản*: `{format_currency(total_balance)}`\n"
    
    message += f"\n💡 *XEM CHI TIẾT*: `/account need` hoặc `/account construction`"
    
    await send_formatted_message(update, message)

async def _show_account_details(update: Update, user_id: int, account_type: str):
    """Show detailed view of specific account with recent transactions"""
    
    # Validate account type
    valid_types = ["need", "fun", "saving", "invest", "construction"]
    if account_type not in valid_types:
        await send_formatted_message(update, f"❌ Loại tài khoản không hợp lệ. Có sẵn: {', '.join(valid_types)}")
        return
    
    # Get account balance
    account_data = db.get_account_by_type(user_id, account_type)
    balance = 0
    if account_data.data:
        balance = float(account_data.data[0].get("current_balance", 0))
    
    # Get recent transactions
    transactions_data = db.get_account_transactions(user_id, account_type, limit=10)
    
    # Get account info
    account_info = ACCOUNT_DESCRIPTIONS.get(account_type, {"emoji": "💳", "name": account_type.title(), "description": ""})
    
    # Build message
    message = f"{account_info['emoji']} *CHI TIẾT TÀI KHOẢN {account_info['name'].upper()}*\n\n"
    message += f"💰 *Số dư hiện tại*: `{format_currency(balance)}`\n"
    message += f"📝 *Mô tả*: {account_info['description']}\n\n"
    
    # Show recent transactions
    if transactions_data.data:
        message += "📊 *10 GIAO DỊCH GẦN NHẤT*\n\n"
        
        for trans in transactions_data.data:
            amount = float(trans["amount"])
            trans_type = trans["transaction_type"]
            description = trans.get("description", "")
            date = trans["created_at"][:10]
            
            # Format transaction type
            type_emoji = {
                "income_allocation": "⬇️",
                "expense": "⬆️", 
                "month_end_transfer": "🔄",
                "manual_adjustment": "✏️"
            }.get(trans_type, "📝")
            
            if amount > 0:
                amount_str = f"+{format_currency(amount)}"
            else:
                amount_str = f"{format_currency(amount)}"
            
            message += f"{type_emoji} {date} - {amount_str}\n"
            if description:
                message += f"   _{description}_\n"
        
        message += f"\n💡 _Chỉ hiển thị 10 giao dịch gần nhất_"
    else:
        message += "📝 *Chưa có giao dịch nào*"
    
    await send_formatted_message(update, message)

async def account_edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit account balance: /accountedit expense 500k"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if len(args) < 2:
        valid_types = ["need", "fun", "saving", "invest", "construction"]
        await send_formatted_message(update, f"❌ Cách dùng: `/accountedit [tên tài khoản] [số tiền]`\n\n📋 *Tài khoản có sẵn:* {', '.join(valid_types)}")
        return
    
    # Parse account type
    account_input = args[0].lower().strip()
    matched_account = None
    
    # Find matching account type
    valid_types = ["need", "fun", "saving", "invest", "construction"]
    for account_type in valid_types:
        if account_input == account_type or account_input in account_type:
            matched_account = account_type
            break
    
    if not matched_account:
        await send_formatted_message(update, f"❌ Không tìm thấy tài khoản '{account_input}'\n\n📋 *Có sẵn:* {', '.join(valid_types)}")
        return
    
    # Parse amount
    success, new_balance, _ = safe_parse_amount(args[1])
    if not success:
        await send_formatted_message(update, "❌ Số tiền không hợp lệ. VD: `/accountedit need 500k`")
        return
    
    # Update account
    account_data = {
        "user_id": user_id,
        "account_type": matched_account,
        "current_balance": new_balance,
        "last_updated": datetime.now().isoformat()
    }
    
    db.upsert_account(account_data)
    
    # Log transaction
    transaction_data = {
        "user_id": user_id,
        "account_type": matched_account,
        "transaction_type": "manual_adjustment",
        "amount": new_balance,  # Log the new balance, not the change
        "description": f"Manual adjustment to {format_currency(new_balance)}"
    }
    
    db.insert_account_transaction(transaction_data)
    
    # Response
    account_info = ACCOUNT_DESCRIPTIONS.get(matched_account, {"emoji": "💳", "name": matched_account.title()})
    
    message = f"""✅ *ĐÃ CẬP NHẬT TÀI KHOẢN!*

{account_info['emoji']} *{account_info['name']}*
💰 *Số dư mới:* `{format_currency(new_balance)}`
📅 *Cập nhật:* {datetime.now().strftime('%d/%m/%Y %H:%M')}"""
    
    await send_formatted_message(update, message)

async def _initialize_all_accounts(user_id):
    """Initialize all account types with 0 balance"""
    all_account_types = ["need", "fun", "saving", "invest", "construction"]
    
    for account_type in all_account_types:
        account_data = {
            "user_id": user_id,
            "account_type": account_type,
            "current_balance": 0,
            "last_updated": datetime.now().isoformat()
        }
        db.upsert_account(account_data)