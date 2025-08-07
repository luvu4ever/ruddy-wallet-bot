from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime

from database import db
from utils import check_authorization, send_formatted_message, safe_parse_amount, format_currency
from config import ACCOUNT_TYPES, get_account_emoji, get_account_description

async def account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all account balances: /account"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    
    # Get all accounts for user
    accounts_data = db.get_accounts(user_id)
    
    # Initialize with default accounts if none exist
    if not accounts_data.data:
        # Create default accounts with 0 balance
        for account_type in ACCOUNT_TYPES.keys():
            default_account = {
                "user_id": user_id,
                "account_type": account_type,
                "current_balance": 0,
                "last_updated": datetime.now().isoformat()
            }
            db.upsert_account(default_account)
        
        # Get accounts again after initialization
        accounts_data = db.get_accounts(user_id)
    
    # Build message
    message = "💳 *TÀI KHOẢN CỦA BẠN*\n\n"
    
    total_balance = 0
    account_lines = []
    
    # Sort accounts by predefined order
    account_order = list(ACCOUNT_TYPES.keys())
    accounts_dict = {acc["account_type"]: acc for acc in accounts_data.data}
    
    for account_type in account_order:
        if account_type in accounts_dict:
            account = accounts_dict[account_type]
            balance = float(account.get("current_balance", 0))
            last_updated = account.get("last_updated", "")[:10]
        else:
            # Create missing account
            default_account = {
                "user_id": user_id,
                "account_type": account_type,
                "current_balance": 0,
                "last_updated": datetime.now().isoformat()
            }
            db.upsert_account(default_account)
            balance = 0
            last_updated = datetime.now().date().isoformat()
        
        emoji = get_account_emoji(account_type)
        description = get_account_description(account_type)
        
        account_lines.append(f"{emoji} *{description}*: `{format_currency(balance)}`")
        total_balance += balance
    
    message += "\n".join(account_lines)
    message += f"\n\n💰 *TỔNG TÀI SẢN:* `{format_currency(total_balance)}`"
    message += f"\n📅 _Cập nhật gần nhất: {last_updated}_"
    message += f"\n\n💡 _Dùng `/accountedit [tên] [số tiền]` để cập nhật_"
    
    await send_formatted_message(update, message)

async def account_edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit account balance: /accountedit expense 500k"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if len(args) < 2:
        account_list = ", ".join(ACCOUNT_TYPES.keys())
        await send_formatted_message(update, f"❌ Cách dùng: `/accountedit [tên tài khoản] [số tiền]`\n\n📋 *Tài khoản có sẵn:* {account_list}")
        return
    
    # Parse account type
    account_input = args[0].lower().strip()
    matched_account = None
    
    # Find matching account type
    for account_type in ACCOUNT_TYPES.keys():
        if account_input == account_type or account_input in account_type:
            matched_account = account_type
            break
    
    if not matched_account:
        account_list = ", ".join(ACCOUNT_TYPES.keys())
        await send_formatted_message(update, f"❌ Không tìm thấy tài khoản '{account_input}'\n\n📋 *Có sẵn:* {account_list}")
        return
    
    # Parse amount
    success, new_balance, _ = safe_parse_amount(args[1])
    if not success:
        await send_formatted_message(update, "❌ Số tiền không hợp lệ. VD: `/accountedit expense 500k`")
        return
    
    # Update account
    account_data = {
        "user_id": user_id,
        "account_type": matched_account,
        "current_balance": new_balance,
        "last_updated": datetime.now().isoformat()
    }
    
    db.upsert_account(account_data)
    
    # Response
    emoji = get_account_emoji(matched_account)
    description = get_account_description(matched_account)
    
    message = f"""✅ *ĐÃ CẬP NHẬT TÀI KHOẢN!*

{emoji} *{description}*
💰 *Số dư mới:* `{format_currency(new_balance)}`
📅 *Cập nhật:* {datetime.now().strftime('%d/%m/%Y %H:%M')}"""
    
    await send_formatted_message(update, message)