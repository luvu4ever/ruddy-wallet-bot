from telegram import Update
from telegram.ext import ContextTypes

from database import db
from utils import check_authorization, send_formatted_message
from config import ACCOUNT_DESCRIPTIONS

async def allocation_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await _show_current_allocations(update, user_id)
        return
    
    if len(args) < 2:
        await send_formatted_message(update, "⚠ Cách dùng: `/allocation need 60` hoặc `/allocation` để xem")
        return
    
    account_type = args[0].lower()
    
    if account_type not in ["need", "fun", "saving", "invest"]:
        await send_formatted_message(update, "⚠ Loại tài khoản không hợp lệ. Chỉ có: need, fun, saving, invest")
        return
    
    try:
        percentage = float(args[1])
        if percentage < 0 or percentage > 100:
            await send_formatted_message(update, "⚠ Phần trăm phải từ 0-100")
            return
    except ValueError:
        await send_formatted_message(update, "⚠ Phần trăm không hợp lệ")
        return
    
    allocation_data = {
        "user_id": user_id,
        "account_type": account_type,
        "percentage": percentage
    }
    
    db.upsert_allocation_setting(allocation_data)
    
    await _show_current_allocations(update, user_id, f"✅ Đã cập nhật {account_type}: {percentage}%\n\n")

async def _show_current_allocations(update: Update, user_id: int, prefix_message: str = ""):
    allocations_data = db.get_allocation_settings(user_id)
    
    if not allocations_data.data:
        message = f"{prefix_message}⚠ *CHƯA CÓ CÀI ĐẶT PHÂN BỔ*\n\n"
        message += "💡 *THIẾT LẬP PHÂN BỔ:*\n"
        message += "• `/allocation need 50` - Thiết yếu 50%\n"
        message += "• `/allocation fun 30` - Giải trí 30%\n"
        message += "• `/allocation saving 0` - Tiết kiệm 0%\n"
        message += "• `/allocation invest 20` - Đầu tư 20%\n\n"
        message += "⚠️ *Tổng phải = 100%*"
        await send_formatted_message(update, message)
        return
    
    current_allocations = {}
    for setting in allocations_data.data:
        account_type = setting["account_type"]
        percentage = float(setting["percentage"])
        current_allocations[account_type] = percentage
    
    total_percentage = sum(current_allocations.values())
    
    message = f"{prefix_message}💰 *CÀI ĐẶT PHÂN BỔ THU NHẬP*\n\n"
    
    for account_type in ["need", "fun", "saving", "invest"]:
        percentage = current_allocations.get(account_type, 0)
        account_info = ACCOUNT_DESCRIPTIONS[account_type]
        
        message += f"{account_info['emoji']} *{account_info['name']}*: {percentage}%\n"
        message += f"   _{account_info['description']}_\n\n"
    
    message += f"📊 *Tổng:* {total_percentage}%"
    
    if total_percentage != 100:
        if total_percentage > 100:
            message += f" ⚠️ *Vượt 100%!*"
        else:
            message += f" ⚠️ *Thiếu {100-total_percentage}%*"
    else:
        message += f" ✅"
    
    message += f"\n\n💡 *CÁCH DÙNG:*\n"
    message += f"• `/allocation need 60` - Đặt thiết yếu 60%\n"
    message += f"• `/allocation saving 10` - Đặt tiết kiệm 10%\n"
    message += f"• Thu nhập mama không bị phân bổ"
    
    await send_formatted_message(update, message)

def get_user_allocations(user_id):
    allocations_data = db.get_allocation_settings(user_id)
    
    if not allocations_data.data:
        return {}
    
    allocations = {}
    for setting in allocations_data.data:
        account_type = setting["account_type"] 
        percentage = float(setting["percentage"])
        allocations[account_type] = percentage
    
    return allocations

def validate_allocations(allocations):
    total = sum(allocations.values())
    return abs(total - 100.0) < 0.01