from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, date

from database import db
from utils import is_authorized, format_currency, parse_amount

async def subscription_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add monthly subscription: /subadd Spotify 33k"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if len(args) < 2:
        await update.message.reply_text("❌ Cách dùng: /subadd Spotify 33k\nhoặc /subadd Netflix 150k\nhoặc /subadd Premium 1.5tr")
        return
    
    try:
        # Parse arguments: service_name amount
        service_name = args[0]
        amount = parse_amount(args[1])
        
        subscription_data = {
            "user_id": user_id,
            "service_name": service_name,
            "amount": amount,
            "billing_cycle": "monthly"
        }
        
        db.insert_subscription(subscription_data)
        await update.message.reply_text(f"✅ Đã thêm subscription!\n📅 **{service_name}**: {format_currency(amount)}/tháng\n\n💡 Subscription sẽ tự động được thêm khi tính /summary")
        
    except ValueError:
        await update.message.reply_text("❌ Số tiền không hợp lệ. Ví dụ: /subadd Spotify 33k hoặc /subadd Premium 1.5tr")

async def subscription_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all subscriptions: /sublist"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    
    # Get all subscriptions
    subscriptions_data = db.get_subscriptions(user_id)
    
    if not subscriptions_data.data:
        await update.message.reply_text("📅 Không có subscription nào!\n\nDùng /subadd để thêm subscription\nSubscription sẽ tự động được thêm khi tính /summary")
        return
    
    # Sort by amount (high to low)
    subscriptions = sorted(subscriptions_data.data, key=lambda x: x.get("amount", 0), reverse=True)
    
    subscription_text = "📅 **Subscriptions hàng tháng:**\n\n"
    total_monthly = 0
    
    for i, sub in enumerate(subscriptions, 1):
        service_name = sub["service_name"]
        amount = sub.get("amount", 0)
        billing_cycle = sub.get("billing_cycle", "monthly")
        
        subscription_text += f"{i}. 📅 **{service_name}**: {format_currency(amount)}/{billing_cycle}\n"
        total_monthly += amount
    
    subscription_text += f"\n💰 **Tổng/tháng**: {format_currency(total_monthly)}"
    subscription_text += f"\n📊 **Tổng/năm**: {format_currency(total_monthly * 12)}"
    subscription_text += f"\n\n💡 **Tự động thêm khi tính /summary**"
    
    await update.message.reply_text(subscription_text)

async def subscription_remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove subscription: /subremove 1"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await update.message.reply_text("❌ Cách dùng: /subremove 1 (số thứ tự)")
        return
    
    try:
        item_index = int(args[0]) - 1  # Convert to 0-based index
        
        # Get subscriptions
        subscriptions_data = db.get_subscriptions(user_id)
        
        if not subscriptions_data.data or item_index >= len(subscriptions_data.data):
            await update.message.reply_text("❌ Số thứ tự không hợp lệ. Kiểm tra /sublist")
            return
        
        # Sort same as in list function
        subscriptions = sorted(subscriptions_data.data, key=lambda x: x.get("amount", 0), reverse=True)
        selected_sub = subscriptions[item_index]
        
        # Remove subscription
        db.delete_subscription(selected_sub["id"])
        
        service_name = selected_sub["service_name"]
        
        await update.message.reply_text(f"✅ Đã xóa subscription **{service_name}**!")
        
    except ValueError:
        await update.message.reply_text("❌ Vui lòng nhập số hợp lệ: /subremove 1")