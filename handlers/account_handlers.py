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
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if args:
        account_type = args[0].lower()
        await _show_account_details(update, user_id, account_type)
        return
    
    await _show_all_accounts_enhanced(update, user_id)

async def _show_all_accounts_enhanced(update: Update, user_id: int):
    accounts_data = db.get_accounts(user_id)
    
    if not accounts_data.data:
        await _initialize_all_accounts(user_id)
        accounts_data = db.get_accounts(user_id)
    
    from .allocation_handlers import get_user_allocations
    allocations = get_user_allocations(user_id)
    
    accounts_dict = {acc["account_type"]: acc for acc in accounts_data.data}
    
    message = "💳 *TÀI KHOẢN CỦA BẠN*\n\n"
    
    account_balances = {}
    total_balance = 0
    
    for account_type in ["need", "fun", "saving", "invest", "mama"]:
        account_info = ACCOUNT_DESCRIPTIONS[account_type]
        
        balance = 0
        if account_type in accounts_dict:
            balance = float(accounts_dict[account_type].get("current_balance", 0))
        
        account_balances[account_type] = balance
        total_balance += balance
        
        allocation_text = ""
        if account_type in allocations:
            percentage = allocations[account_type]
            allocation_text = f" ({percentage}%)"
        
        message += f"{account_info['emoji']} *{account_info['name']}*{allocation_text}: `{format_currency(balance)}`\n"
    
    spending_accounts_total = account_balances["need"] + account_balances["fun"]
    
    message += f"\n📊 *TỔNG KẾT*\n"
    message += f"🛒 *Tiêu dùng* (Thiết yếu + Giải trí): `{format_currency(spending_accounts_total)}`\n"
    message += f"💰 *Tiết kiệm*: `{format_currency(account_balances['saving'])}`\n"
    message += f"📈 *Đầu tư*: `{format_currency(account_balances['invest'])}`\n"
    message += f"✅ *Mama*: `{format_currency(account_balances['mama'])}`\n"
    message += f"💎 *Tổng tài sản*: `{format_currency(total_balance)}`\n"
    
    message += f"\n💡 *XEM CHI TIẾT*: `/account need` hoặc `/account mama`"
    
    await send_formatted_message(update, message)

async def _show_account_details(update: Update, user_id: int, account_type: str):
    valid_types = ["need", "fun", "saving", "invest", "mama"]
    if account_type not in valid_types:
        await send_formatted_message(update, f"⚠ Loại tài khoản không hợp lệ. Có sẵn: {', '.join(valid_types)}")
        return
    
    account_data = db.get_account_by_type(user_id, account_type)
    balance = 0
    if account_data.data:
        balance = float(account_data.data[0].get("current_balance", 0))
    
    transactions_data = db.get_account_transactions(user_id, account_type, limit=10)
    
    account_info = ACCOUNT_DESCRIPTIONS.get(account_type, {"emoji": "💳", "name": account_type.title(), "description": ""})
    
    message = f"{account_info['emoji']} *CHI TIẾT TÀI KHOẢN {account_info['name'].upper()}*\n\n"
    message += f"💰 *Số dư hiện tại*: `{format_currency(balance)}`\n"
    message += f"📝 *Mô tả*: {account_info['description']}\n\n"
    
    if transactions_data.data:
        message += "📊 *10 GIAO DỊCH GẦN NHẤT*\n\n"
        
        for trans in transactions_data.data:
            amount = float(trans["amount"])
            trans_type = trans["transaction_type"]
            description = trans.get("description", "")
            date = trans["created_at"][:10]
            
            type_emoji = {
                "income_allocation": "⬇️",
                "expense": "⬆️", 
                "month_end_transfer": "🔄",
                "manual_adjustment": "✏️"
            }.get(trans_type, "📋")
            
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
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if len(args) < 2:
        valid_types = ["need", "fun", "saving", "invest", "mama"]
        await send_formatted_message(update, f"⚠ Cách dùng: `/accountedit [tên tài khoản] [số tiền]`\n\n📋 *Tài khoản có sẵn:* {', '.join(valid_types)}")
        return
    
    account_input = args[0].lower().strip()
    matched_account = None
    
    valid_types = ["need", "fun", "saving", "invest", "mama"]
    for account_type in valid_types:
        if account_input == account_type or account_input in account_type:
            matched_account = account_type
            break
    
    if not matched_account:
        await send_formatted_message(update, f"⚠ Không tìm thấy tài khoản '{account_input}'\n\n📋 *Có sẵn:* {', '.join(valid_types)}")
        return
    
    success, new_balance, _ = safe_parse_amount(args[1])
    if not success:
        await send_formatted_message(update, "⚠ Số tiền không hợp lệ. VD: `/accountedit need 500k`")
        return
    
    current_balance = db.get_account_balance(user_id, matched_account)
    balance_change = new_balance - current_balance
    
    try:
        result, final_balance = db.update_account_balance(
            user_id, matched_account, balance_change, "manual_adjustment",
            f"Manual adjustment to {format_currency(new_balance)}"
        )
        
        account_info = ACCOUNT_DESCRIPTIONS.get(matched_account, {"emoji": "💳", "name": matched_account.title()})
        
        message = f"""✅ *ĐÃ CẬP NHẬT TÀI KHOẢN!*

{account_info['emoji']} *{account_info['name']}*
💰 *Số dư cũ:* `{format_currency(current_balance)}`
💰 *Số dư mới:* `{format_currency(final_balance)}`
📊 *Thay đổi:* `{format_currency(balance_change)}`
📅 *Cập nhật:* {datetime.now().strftime('%d/%m/%Y %H:%M')}"""
        
        await send_formatted_message(update, message)
        
    except Exception as e:
        import logging
        logging.error(f"Account edit error: {e}")
        await send_formatted_message(update, "⚠ Lỗi khi cập nhật tài khoản. Vui lòng thử lại.")

async def _initialize_all_accounts(user_id):
    all_account_types = ["need", "fun", "saving", "invest", "mama"]
    
    for account_type in all_account_types:
        existing_account = db.get_account_by_type(user_id, account_type)
        
        if not existing_account.data:
            account_data = {
                "user_id": user_id,
                "account_type": account_type,
                "current_balance": 0,
                "last_updated": datetime.now().isoformat()
            }
            try:
                db.supabase.table("accounts").insert(account_data).execute()
            except Exception as e:
                import logging
                logging.error(f"Error initializing account {account_type} for user {user_id}: {e}")