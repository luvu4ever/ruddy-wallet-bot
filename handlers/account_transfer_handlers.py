from telegram import Update
from telegram.ext import ContextTypes

from database import db
from utils import check_authorization, send_formatted_message, safe_parse_amount, format_currency
from config import ACCOUNT_DESCRIPTIONS, get_account_emoji_enhanced, get_account_name_enhanced

async def transfer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Transfer money between accounts: /transfer need fun 100k"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if len(args) < 3:
        valid_accounts = ["need", "fun", "saving", "invest", "construction"]
        await send_formatted_message(update, 
            f"❌ Cách dùng: `/transfer [từ] [đến] [số tiền]`\n\n"
            f"📋 *Tài khoản*: {', '.join(valid_accounts)}\n"
            f"💡 *Ví dụ*: `/transfer saving need 500k`")
        return
    
    from_account = args[0].lower()
    to_account = args[1].lower()
    
    # Validate account types
    valid_accounts = ["need", "fun", "saving", "invest", "construction"]
    if from_account not in valid_accounts or to_account not in valid_accounts:
        await send_formatted_message(update, f"❌ Tài khoản không hợp lệ. Có sẵn: {', '.join(valid_accounts)}")
        return
    
    if from_account == to_account:
        await send_formatted_message(update, "❌ Không thể chuyển trong cùng một tài khoản")
        return
    
    # Parse amount
    success, amount, _ = safe_parse_amount(args[2])
    if not success:
        await send_formatted_message(update, "❌ Số tiền không hợp lệ")
        return
    
    # Check source account balance
    from_balance = db.get_account_balance(user_id, from_account)
    if from_balance < amount:
        from_info = ACCOUNT_DESCRIPTIONS[from_account]
        await send_formatted_message(update, 
            f"❌ *KHÔNG ĐỦ TIỀN ĐỂ CHUYỂN!*\n\n"
            f"{from_info['emoji']} *{from_info['name']}*: {format_currency(from_balance)}\n"
            f"💰 *Cần chuyển*: {format_currency(amount)}\n"
            f"⚠️ *Thiếu*: {format_currency(amount - from_balance)}")
        return
    
    # Perform transfer
    try:
        # Deduct from source account
        db.update_account_balance(
            user_id, from_account, -amount, "transfer_out",
            f"Transfer to {to_account}: {format_currency(amount)}"
        )
        
        # Add to destination account
        result, new_to_balance = db.update_account_balance(
            user_id, to_account, amount, "transfer_in", 
            f"Transfer from {from_account}: {format_currency(amount)}"
        )
        
        new_from_balance = from_balance - amount
        
        # Success message
        from_info = ACCOUNT_DESCRIPTIONS[from_account]
        to_info = ACCOUNT_DESCRIPTIONS[to_account]
        
        message = f"""✅ *CHUYỂN TIỀN THÀNH CÔNG!*

💰 *Số tiền*: {format_currency(amount)}
{from_info['emoji']} *Từ {from_info['name']}*: {format_currency(new_from_balance)}
{to_info['emoji']} *Đến {to_info['name']}*: {format_currency(new_to_balance)}"""
        
        await send_formatted_message(update, message)
        
    except Exception as e:
        logging.error(f"Transfer error: {e}")
        await send_formatted_message(update, "❌ Lỗi khi chuyển tiền")