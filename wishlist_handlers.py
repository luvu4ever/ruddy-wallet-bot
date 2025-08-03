from telegram import Update
from telegram.ext import ContextTypes

from database import db
from utils import is_authorized, format_currency, parse_amount

async def wishlist_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add item to wishlist: /wishadd iPhone 15 Pro 25m"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if len(args) < 2:
        await update.message.reply_text("❌ Cách dùng: /wishadd iPhone 15 Pro 25m")
        return
    
    try:
        # Last argument should be price
        estimated_price = parse_amount(args[-1])
        item_name = " ".join(args[:-1])
        
        wishlist_data = {
            "user_id": user_id,
            "item_name": item_name,
            "estimated_price": estimated_price
        }
        
        db.insert_wishlist_item(wishlist_data)
        await update.message.reply_text(f"✅ Đã thêm vào wishlist!\n🛍️ **{item_name}**: {format_currency(estimated_price)}")
        
    except ValueError:
        await update.message.reply_text("❌ Giá phải là số. Ví dụ: /wishadd iPhone 15 25m")

async def wishlist_view_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View wishlist: /wishlist"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    
    # Get all wishlist items
    wishlist_data = db.get_wishlist(user_id)
    
    if not wishlist_data.data:
        await update.message.reply_text("📝 Wishlist trống!\n\nDùng /wishadd [tên] [giá] để thêm")
        return
    
    # Sort by price (high to low)
    items = sorted(wishlist_data.data, key=lambda x: x.get("estimated_price", 0), reverse=True)
    
    wishlist_text = "🛍️ **Wishlist của bạn:**\n\n"
    total_wishlist = 0
    
    for i, item in enumerate(items, 1):
        name = item["item_name"]
        price = item.get("estimated_price", 0)
        
        wishlist_text += f"{i}. **{name}**: {format_currency(price)}\n"
        total_wishlist += price
    
    wishlist_text += f"\n💰 **Tổng giá trị**: {format_currency(total_wishlist)}"
    wishlist_text += f"\n📝 **Số lượng**: {len(items)} sản phẩm"
    
    await update.message.reply_text(wishlist_text)

async def wishlist_remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove item from wishlist: /wishremove 1"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await update.message.reply_text("❌ Cách dùng: /wishremove 1 (số thứ tự)")
        return
    
    try:
        item_index = int(args[0]) - 1  # Convert to 0-based index
        
        # Get wishlist items
        wishlist_data = db.get_wishlist(user_id)
        
        if not wishlist_data.data or item_index >= len(wishlist_data.data):
            await update.message.reply_text("❌ Số thứ tự không hợp lệ. Kiểm tra /wishlist")
            return
        
        # Sort same as in view function
        items = sorted(wishlist_data.data, key=lambda x: x.get("estimated_price", 0), reverse=True)
        selected_item = items[item_index]
        
        # Remove item
        db.delete_wishlist_item(selected_item["id"])
        
        item_name = selected_item["item_name"]
        
        await update.message.reply_text(f"✅ Đã xóa **{item_name}** khỏi wishlist!")
        
    except ValueError:
        await update.message.reply_text("❌ Vui lòng nhập số hợp lệ: /wishremove 1")
    bought_data = db.get_wishlist(user_id, purchased=True)
    
    if not bought_data.data:
        await update.message.reply_text("🛍️ Chưa mua sản phẩm nào từ wishlist!")
        return
    
    bought_text = "🎉 **Đã mua từ wishlist:**\n\n"
    total_spent = 0
    
    for i, item in enumerate(bought_data.data, 1):
        name = item["item_name"]
        price = item.get("estimated_price", 0)
        bought_text += f"{i}. ✅ **{name}**: {format_currency(price)}\n"
        total_spent += price
    
    bought_text += f"\n💰 **Tổng đã chi**: {format_currency(total_spent)}"
    
    await update.message.reply_text(bought_text)