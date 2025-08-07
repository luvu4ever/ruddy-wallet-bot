from telegram import Update
from telegram.ext import ContextTypes

from database import db
from utils import check_authorization, send_formatted_message, safe_int_conversion, safe_parse_amount, format_currency

async def subscription_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add subscription: /subadd Spotify 33k"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if len(args) < 2:
        await send_formatted_message(update, "❌ Cách dùng: `/subadd Spotify 33k`")
        return
    
    service_name = args[0]
    success, amount, _ = safe_parse_amount(args[1])
    
    if not success:
        await send_formatted_message(update, "❌ Số tiền không hợp lệ")
        return
    
    # Save subscription
    subscription_data = {
        "user_id": user_id,
        "service_name": service_name,
        "amount": amount,
        "billing_cycle": "monthly"
    }
    
    db.insert_subscription(subscription_data)
    
    message = f"✅ Đã thêm subscription!\n📅 *{service_name}*: {format_currency(amount)}/tháng"
    await send_formatted_message(update, message)

async def subscription_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List subscriptions: /sublist"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    subscriptions_data = db.get_subscriptions(user_id)
    
    if not subscriptions_data.data:
        await send_formatted_message(update, "📅 Không có subscription!\nDùng `/subadd Spotify 33k` để thêm")
        return
    
    # Sort by amount
    subscriptions = sorted(subscriptions_data.data, key=lambda x: x.get("amount", 0), reverse=True)
    
    subscription_text = "📅 *SUBSCRIPTIONS*\n\n"
    total_monthly = 0
    
    for i, sub in enumerate(subscriptions, 1):
        service_name = sub["service_name"]
        amount = sub.get("amount", 0)
        
        subscription_text += f"{i}. 📅 *{service_name}*: {format_currency(amount)}/tháng\n"
        total_monthly += amount
    
    subscription_text += f"\n💰 *Tổng/tháng*: {format_currency(total_monthly)}"
    subscription_text += f"\n📊 *Tổng/năm*: {format_currency(total_monthly * 12)}"
    
    await send_formatted_message(update, subscription_text)

async def subscription_remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove subscription: /subremove 1"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await send_formatted_message(update, "❌ Cách dùng: `/subremove 1`")
        return
    
    try:
        item_index = int(args[0]) - 1
    except:
        await send_formatted_message(update, "❌ Vui lòng nhập số hợp lệ")
        return
    
    # Get subscriptions
    subscriptions_data = db.get_subscriptions(user_id)
    
    if not subscriptions_data.data or item_index < 0 or item_index >= len(subscriptions_data.data):
        await send_formatted_message(update, "❌ Số thứ tự không hợp lệ")
        return
    
    # Sort same as in list
    subscriptions = sorted(subscriptions_data.data, key=lambda x: x.get("amount", 0), reverse=True)
    selected_sub = subscriptions[item_index]
    
    # Remove
    db.delete_subscription(selected_sub["id"])
    
    service_name = selected_sub["service_name"]
    await send_formatted_message(update, f"✅ Đã xóa subscription *{service_name}*!")