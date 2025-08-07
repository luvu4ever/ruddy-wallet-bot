from telegram import Update
from telegram.ext import ContextTypes

from database import db
from utils import (
    check_authorization, send_formatted_message, safe_int_conversion,
    safe_parse_amount, format_currency, MessageFormatter
)
from config import get_priority_emoji, get_priority_name, get_message

async def wishlist_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add item to wishlist: /wishadd iPhone 25m prio:1 or /wishadd iPhone prio:2"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await send_formatted_message(update, get_message("format_errors")["wishlist_usage"])
        return
    
    try:
        # Parse arguments
        priority = 3  # Default priority (lowest)
        estimated_price = None  # Default no price
        
        # Check for priority in arguments
        filtered_args = []
        for arg in args:
            if arg.lower().startswith('prio:'):
                success, prio_value, error_msg = _parse_priority(arg)
                if not success:
                    await send_formatted_message(update, error_msg)
                    return
                priority = prio_value
            else:
                filtered_args.append(arg)
        
        if not filtered_args:
            await send_formatted_message(update, get_message("format_errors")["wishlist_usage"])
            return
        
        # Try to parse price from last argument
        item_name = _parse_item_name_and_price(filtered_args)
        if len(filtered_args) >= 2:
            # Check if last argument looks like a price
            last_arg = filtered_args[-1]
            success, estimated_price, _ = safe_parse_amount(last_arg)
            if success:
                item_name = " ".join(filtered_args[:-1])
            else:
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
        
        message = get_message("wishlist_added", 
            name=item_name, 
            price_text=price_text, 
            priority_text=priority_text)
        await send_formatted_message(update, message)
        
    except Exception as e:
        await send_formatted_message(update, f"❌ Lỗi: {str(e)}")

async def wishlist_view_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View wishlist: /wishlist"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    
    # Get all wishlist items that are not purchased
    wishlist_data = db.get_wishlist(user_id)
    
    if not wishlist_data.data:
        await send_formatted_message(update, get_message("no_wishlist"))
        return
    
    # Filter out purchased items
    active_items = [item for item in wishlist_data.data if not item.get("purchased", False)]
    
    if not active_items:
        await send_formatted_message(update, get_message("no_wishlist"))
        return
    
    # Group by priority and sort by price within each priority
    items_by_priority = _group_items_by_priority(active_items)
    
    # Calculate priority 1 sum for planned purchases
    prio1_sum = sum(item.get("estimated_price", 0) or 0 for item in items_by_priority[1])
    
    wishlist_text = _format_wishlist_display(items_by_priority, prio1_sum)
    
    await send_formatted_message(update, wishlist_text)

async def wishlist_remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove item from wishlist: /wishremove 1"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await send_formatted_message(update, "❌ Cách dùng: /wishremove 1 (số thứ tự)")
        return
    
    success, item_index, error_msg = safe_int_conversion(args[0])
    if not success:
        await send_formatted_message(update, "❌ Vui lòng nhập số hợp lệ: /wishremove 1")
        return
    
    item_index -= 1  # Convert to 0-based index
    
    # Get wishlist items
    wishlist_data = db.get_wishlist(user_id)
    
    if not wishlist_data.data:
        await send_formatted_message(update, "❌ Wishlist trống")
        return
    
    # Filter out purchased items  
    active_items = [item for item in wishlist_data.data if not item.get("purchased", False)]
    
    if not active_items:
        await send_formatted_message(update, "❌ Wishlist trống")
        return
    
    # Sort same as in view function
    items_by_priority = _group_items_by_priority(active_items)
    
    # Create flat list in display order
    all_items = []
    for priority in [1, 2, 3]:
        all_items.extend(items_by_priority[priority])
    
    if item_index >= len(all_items):
        await send_formatted_message(update, "❌ Số thứ tự không hợp lệ. Kiểm tra /wishlist")
        return
    
    selected_item = all_items[item_index]
    
    # Remove item
    db.delete_wishlist_item(selected_item["id"])
    
    item_name = selected_item["item_name"]
    
    await send_formatted_message(update, f"✅ Đã xóa *{item_name}* khỏi wishlist!")

def get_wishlist_priority1_sum(user_id):
    """Get sum of priority 1 wishlist items for display in other commands"""
    try:
        wishlist_data = db.get_wishlist(user_id)
        if not wishlist_data.data:
            return 0
        
        # Filter for priority 1 items that are not purchased and have prices
        prio1_items = [
            item for item in wishlist_data.data 
            if (item.get("priority", 3) == 1 and 
                not item.get("purchased", False) and 
                item.get("estimated_price") is not None)
        ]
        
        total = sum(float(item["estimated_price"]) for item in prio1_items)
        return total
        
    except Exception as e:
        print(f"Error calculating wishlist priority 1 sum: {e}")
        return 0

# Helper functions
def _parse_priority(arg: str) -> tuple[bool, int, str]:
    """Parse priority argument"""
    try:
        prio_value = int(arg.split(':')[1])
        if 1 <= prio_value <= 3:
            return True, prio_value, ""
        else:
            return False, 0, "❌ Priority phải từ 1-3 (1=cao🚨, 2=trung bình⚠️, 3=thấp🌿)"
    except (ValueError, IndexError):
        return False, 0, "❌ Format priority: prio:1, prio:2, hoặc prio:3"

def _parse_item_name_and_price(filtered_args: list) -> str:
    """Parse item name and price from filtered arguments"""
    if len(filtered_args) >= 2:
        # Check if last argument looks like a price
        last_arg = filtered_args[-1]
        success, estimated_price, _ = safe_parse_amount(last_arg)
        if success:
            return " ".join(filtered_args[:-1])
        else:
            # Last argument is not a price, treat all as item name
            return " ".join(filtered_args)
    else:
        # Only one argument, treat as item name
        return " ".join(filtered_args)

def _group_items_by_priority(active_items: list) -> dict:
    """Group wishlist items by priority"""
    items_by_priority = {1: [], 2: [], 3: []}
    
    for item in active_items:
        priority = item.get("priority", 3)
        items_by_priority[priority].append(item)
    
    # Sort each priority group by price (highest first), then by name
    for priority in items_by_priority:
        items_by_priority[priority].sort(key=lambda x: (-(x.get("estimated_price") or 0), x["item_name"]))
    
    return items_by_priority

def _format_wishlist_display(items_by_priority: dict, prio1_sum: float = 0) -> str:
    """Format wishlist for display with priority 1 sum"""
    wishlist_text = "🛍️ *Wishlist của bạn:*\n\n"
    
    # Add priority 1 planned purchases summary at the top if there are any
    if prio1_sum > 0:
        wishlist_text += f"💰 *CẦN TIỀN CHO KẾ HOẠCH:* `{format_currency(prio1_sum)}`\n"
        wishlist_text += "🚨 _Priority 1 - Đã lên kế hoạch mua_\n\n"
    
    total_wishlist = 0
    item_count = 0
    
    # Display by priority order (1=high, 2=medium, 3=low)
    for priority in [1, 2, 3]:
        items = items_by_priority[priority]
        if not items:
            continue
        
        priority_emoji = get_priority_emoji(priority)
        priority_name = get_priority_name(priority)
        
        # Special header for priority 1
        if priority == 1:
            wishlist_text += f"{priority_emoji} *Priority {priority} - {priority_name} (ĐÃ LÊN KẾ HOẠCH):*\n"
        else:
            wishlist_text += f"{priority_emoji} *Priority {priority} - {priority_name}:*\n"
        
        for item in items:
            item_count += 1
            name = item["item_name"]
            price = item.get("estimated_price")
            
            if price and price > 0:
                wishlist_text += f"{item_count}. *{name}*: {format_currency(price)}\n"
                total_wishlist += price
            else:
                wishlist_text += f"{item_count}. *{name}*: Chưa có giá\n"
        
        wishlist_text += "\n"
    
    # Summary section
    if total_wishlist > 0:
        wishlist_text += f"💰 *Tổng giá trị*: {format_currency(total_wishlist)}"
        if prio1_sum > 0 and prio1_sum != total_wishlist:
            remaining_wishlist = total_wishlist - prio1_sum
            wishlist_text += f"\n🎯 *Cần cho kế hoạch*: {format_currency(prio1_sum)}"
            wishlist_text += f"\n💭 *Mong muốn khác*: {format_currency(remaining_wishlist)}"
    
    wishlist_text += f"\n📝 *Tổng số món*: {item_count} sản phẩm"
    
    return wishlist_text