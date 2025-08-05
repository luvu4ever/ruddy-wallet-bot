from telegram import Update
from telegram.ext import ContextTypes

from database import db
from utils import is_authorized, format_currency, parse_amount
from config import get_priority_emoji, get_priority_name, get_message

async def wishlist_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add item to wishlist: /wishadd iPhone 25m prio:1 or /wishadd iPhone prio:2"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await update.message.reply_text(get_message("format_errors")["wishlist_usage"])
        return
    
    try:
        # Parse arguments
        priority = 3  # Default priority (lowest)
        estimated_price = None  # Default no price
        
        # Check for priority in arguments
        filtered_args = []
        for arg in args:
            if arg.lower().startswith('prio:'):
                try:
                    prio_value = int(arg.split(':')[1])
                    if 1 <= prio_value <= 3:
                        priority = prio_value
                    else:
                        await update.message.reply_text("❌ Priority phải từ 1-3 (1=cao🚨, 2=trung bình⚠️, 3=thấp🌿)")
                        return
                except (ValueError, IndexError):
                    await update.message.reply_text("❌ Format priority: prio:1, prio:2, hoặc prio:3")
                    return
            else:
                filtered_args.append(arg)
        
        if not filtered_args:
            await update.message.reply_text(get_message("format_errors")["wishlist_usage"])
            return
        
        # Try to parse price from last argument
        item_name = ""
        if len(filtered_args) >= 2:
            # Check if last argument looks like a price
            last_arg = filtered_args[-1]
            try:
                estimated_price = parse_amount(last_arg)
                item_name = " ".join(filtered_args[:-1])
            except ValueError:
                # Last argument is not a price, treat all as item name
                item_name = " ".join(filtered_args)
        else:
            # Only one argument, treat as item name
            item_name = " ".join(filtered_args)
        
        # Create wishlist record
        wishlist_data = {
            "user_id": user_id,
            "item_name": item_name,
            "estimated_price": estimated_price,
            "priority": priority,
            "purchased": False
        }
        
        db.insert_wishlist_item(wishlist_data)
        
        # Format response
        priority_emoji = get_priority_emoji(priority)
        priority_name = get_priority_name(priority)
        price_text = format_currency(estimated_price) if estimated_price else "Chưa có giá"
        priority_text = f"\n{priority_emoji} Priority: {priority_name}"
        
        await update.message.reply_text(get_message("wishlist_added", 
            name=item_name, 
            price_text=price_text, 
            priority_text=priority_text))
        
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {str(e)}")

async def wishlist_view_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View wishlist: /wishlist"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    
    # Get all wishlist items that are not purchased
    wishlist_data = db.get_wishlist(user_id)
    
    if not wishlist_data.data:
        await update.message.reply_text(get_message("no_wishlist"))
        return
    
    # Filter out purchased items
    active_items = [item for item in wishlist_data.data if not item.get("purchased", False)]
    
    if not active_items:
        await update.message.reply_text(get_message("no_wishlist"))
        return
    
    # Group by priority and sort by price within each priority
    items_by_priority = {1: [], 2: [], 3: []}
    
    for item in active_items:
        priority = item.get("priority", 3)
        items_by_priority[priority].append(item)
    
    # Sort each priority group by price (highest first), then by name
    for priority in items_by_priority:
        items_by_priority[priority].sort(key=lambda x: (-(x.get("estimated_price") or 0), x["item_name"]))
    
    wishlist_text = "🛍️ **Wishlist của bạn:**\n\n"
    total_wishlist = 0
    item_count = 0
    
    # Display by priority order (1=high, 2=medium, 3=low)
    for priority in [1, 2, 3]:
        items = items_by_priority[priority]
        if not items:
            continue
        
        priority_emoji = get_priority_emoji(priority)
        priority_name = get_priority_name(priority)
        
        wishlist_text += f"{priority_emoji} **Priority {priority} - {priority_name}:**\n"
        
        for item in items:
            item_count += 1
            name = item["item_name"]
            price = item.get("estimated_price")
            
            if price and price > 0:
                wishlist_text += f"{item_count}. **{name}**: {format_currency(price)}\n"
                total_wishlist += price
            else:
                wishlist_text += f"{item_count}. **{name}**: Chưa có giá\n"
        
        wishlist_text += "\n"
    
    if total_wishlist > 0:
        wishlist_text += f"💰 **Tổng giá trị**: {format_currency(total_wishlist)}"
    
    wishlist_text += f"\n📝 **Tổng số món**: {item_count} sản phẩm"
    
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
        
        if not wishlist_data.data:
            await update.message.reply_text("❌ Wishlist trống")
            return
        
        # Filter out purchased items  
        active_items = [item for item in wishlist_data.data if not item.get("purchased", False)]
        
        if not active_items:
            await update.message.reply_text("❌ Wishlist trống")
            return
        
        # Sort same as in view function
        items_by_priority = {1: [], 2: [], 3: []}
        
        for item in active_items:
            priority = item.get("priority", 3)
            items_by_priority[priority].append(item)
        
        # Sort each priority group by price (highest first), then by name
        for priority in items_by_priority:
            items_by_priority[priority].sort(key=lambda x: (-(x.get("estimated_price") or 0), x["item_name"]))
        
        # Create flat list in display order
        all_items = []
        for priority in [1, 2, 3]:
            all_items.extend(items_by_priority[priority])
        
        if item_index >= len(all_items):
            await update.message.reply_text("❌ Số thứ tự không hợp lệ. Kiểm tra /wishlist")
            return
        
        selected_item = all_items[item_index]
        
        # Remove item
        db.delete_wishlist_item(selected_item["id"])
        
        item_name = selected_item["item_name"]
        
        await update.message.reply_text(f"✅ Đã xóa **{item_name}** khỏi wishlist!")
        
    except ValueError:
        await update.message.reply_text("❌ Vui lòng nhập số hợp lệ: /wishremove 1")