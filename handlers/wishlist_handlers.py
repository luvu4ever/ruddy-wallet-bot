from telegram import Update
from telegram.ext import ContextTypes
import logging

from database import db
from utils import (
    check_authorization, send_formatted_message,
    safe_parse_amount, format_currency  # REMOVED safe_int_conversion
)
from config import get_priority_emoji, get_priority_name, get_priority_description, get_message

# Import Gemini for fuzzy matching
import google.generativeai as genai
from config import GEMINI_API_KEY
import json

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

async def wishlist_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add item to wishlist: /wishadd iPhone 25m prio:1"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await send_formatted_message(update, "⌘ Cách dùng: /wishadd [tên] [giá] [prio:1-5]")
        return
    
    # Default values
    priority = 5  # Default to lowest priority
    estimated_price = None
    
    # Parse priority if present
    item_args = []
    for arg in args:
        if arg.lower().startswith('prio:'):
            try:
                prio_value = int(arg.split(':')[1])  # Direct int conversion instead of safe_int_conversion
                if 1 <= prio_value <= 5:
                    priority = prio_value
            except (ValueError, IndexError):
                pass
        else:
            item_args.append(arg)
    
    if not item_args:
        await send_formatted_message(update, "⌘ Vui lòng nhập tên sản phẩm")
        return
    
    # Try to parse price from last argument
    if len(item_args) >= 2:
        try:
            success, price, _ = safe_parse_amount(item_args[-1])
            if success:
                estimated_price = price
                item_name = " ".join(item_args[:-1])
            else:
                item_name = " ".join(item_args)
        except Exception:
            item_name = " ".join(item_args)
    else:
        item_name = " ".join(item_args)
    
    # Save to database
    wishlist_data = {
        "user_id": user_id,
        "item_name": item_name,
        "estimated_price": estimated_price,
        "priority": priority,
        "purchased": False
    }
    
    db.insert_wishlist_item(wishlist_data)
    
    # Response
    price_text = format_currency(estimated_price) if estimated_price else "Chưa có giá"
    priority_emoji = get_priority_emoji(priority)
    priority_name = get_priority_name(priority)
    
    message = f"""✅ *ĐÃ THÊM VÀO WISHLIST!*

🛏️ *Tên:* {item_name}
💰 *Giá:* {price_text}
{priority_emoji} *Level {priority}:* {priority_name}"""
    
    await send_formatted_message(update, message)

async def wishlist_view_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View wishlist: /wishlist"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    
    # Get wishlist items
    wishlist_data = db.get_wishlist(user_id)
    
    if not wishlist_data.data:
        await send_formatted_message(update, "🛏️ Wishlist trống! Dùng /wishadd để thêm sản phẩm")
        return
    
    # Filter active items
    active_items = [item for item in wishlist_data.data if not item.get("purchased", False)]
    
    if not active_items:
        await send_formatted_message(update, "🛏️ Wishlist trống! Dùng /wishadd để thêm sản phẩm")
        return
    
    # Group by priority
    levels = {1: [], 2: [], 3: [], 4: [], 5: []}
    
    for item in active_items:
        priority = item.get("priority")
        if priority is None:
            priority = 5
        try:
            priority = int(priority)
            if priority < 1 or priority > 5:
                priority = 5
        except (ValueError, TypeError):
            priority = 5
        
        levels[priority].append(item)
    
    # Calculate sums
    level_sums = {}
    for level in [1, 2, 3, 4, 5]:
        total = 0
        for item in levels[level]:
            price = item.get("estimated_price")
            if price:
                try:
                    total += float(price)
                except (ValueError, TypeError):
                    pass
        level_sums[level] = total
    
    # Get financial data
    financial_data = get_simple_financial_data(user_id)
    
    # Build message
    message = "🛏️ *WISHLIST 5 LEVELS*\n\n"
    
    # Financial summary
    message += "💰 *PHÂN TÍCH TÀI CHÍNH*\n"
    if level_sums[1] > 0:
        message += f"🔒 *Level 1:* `{format_currency(level_sums[1])}`\n"
    if level_sums[2] > 0:
        message += f"🚨 *Level 2:* `{format_currency(level_sums[2])}`\n"
    
    # Money analysis
    net_savings = financial_data["income"] - financial_data["expenses"]
    after_level1 = net_savings - level_sums[1]
    after_level12 = net_savings - level_sums[1] - level_sums[2]
    
    if after_level1 >= 0:
        message += f"✅ *Sau Level 1:* `{format_currency(after_level1)}`\n"
    else:
        message += f"⚠️ *Thiếu Level 1:* `{format_currency(abs(after_level1))}`\n"
    
    if after_level12 >= 0:
        message += f"✅ *Sau Level 1+2:* `{format_currency(after_level12)}`\n"
    else:
        message += f"⚠️ *Thiếu Level 1+2:* `{format_currency(abs(after_level12))}`\n"
    
    message += "\n"
    
    # Show items by level
    item_count = 0
    total_value = 0
    
    for level in [1, 2, 3, 4, 5]:
        items = levels[level]
        if not items:
            continue
        
        emoji = get_priority_emoji(level)
        name = get_priority_name(level)
        
        message += f"{emoji} *Level {level} - {name}*\n"
        if level_sums[level] > 0:
            message += f"💰 *Tổng:* `{format_currency(level_sums[level])}`\n"
        
        for item in items:
            item_count += 1
            item_name = item.get("item_name", "Unknown")
            price = item.get("estimated_price")
            
            if price and price > 0:
                message += f"• *{item_name}*: {format_currency(price)}\n"
                total_value += float(price)
            else:
                message += f"• *{item_name}*: Chưa có giá\n"
        
        message += "\n"
    
    # Summary
    if total_value > 0:
        message += f"💰 *TỔNG GIÁ TRỊ:* `{format_currency(total_value)}`\n"
    message += f"📝 *TỔNG SỐ MÓN:* {item_count} sản phẩm\n\n"
    message += f"💡 _Dùng `/wishremove [tên sản phẩm]` để xóa_"
    
    await send_formatted_message(update, message)

async def wishlist_remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove item from wishlist using fuzzy name matching: /wishremove iPhone"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await send_formatted_message(update, "⌘ Cách dùng: `/wishremove [tên sản phẩm]`\n💡 Ví dụ: `/wishremove iPhone` hoặc `/wishremove iphone`")
        return
    
    # Join all arguments as the item name to search
    search_term = " ".join(args).strip()
    
    # Get wishlist
    wishlist_data = db.get_wishlist(user_id)
    if not wishlist_data.data:
        await send_formatted_message(update, "⌘ Wishlist trống")
        return
    
    active_items = [item for item in wishlist_data.data if not item.get("purchased", False)]
    
    if not active_items:
        await send_formatted_message(update, "⌘ Wishlist trống")
        return
    
    # Use Gemini to find the best matching item
    matched_item = find_matching_wishlist_item(search_term, active_items)
    
    if not matched_item:
        # Show available items for reference
        item_names = [item["item_name"] for item in active_items]
        items_text = "\n".join([f"• {name}" for name in item_names[:10]])  # Show max 10 items
        
        message = f"""⌘ *KHÔNG TÌM THẤY SẢN PHẨM*

🔍 *Tìm kiếm:* `{search_term}`

📝 *CÁC SẢN PHẨM HIỆN CÓ:*
{items_text}"""
        
        if len(active_items) > 10:
            message += f"\n_... và {len(active_items) - 10} sản phẩm khác_"
        
        await send_formatted_message(update, message)
        return
    
    # Remove the matched item
    db.delete_wishlist_item(matched_item["id"])
    
    # Response with item details
    item_name = matched_item["item_name"]
    price = matched_item.get("estimated_price")
    priority = matched_item.get("priority", 5)
    
    price_text = format_currency(price) if price else "Không có giá"
    priority_emoji = get_priority_emoji(priority)
    
    message = f"""✅ *ĐÃ XÓA KHỎI WISHLIST!*

🛏️ *Tên:* {item_name}
💰 *Giá:* {price_text}
{priority_emoji} *Level:* {priority}"""
    
    await send_formatted_message(update, message)

def find_matching_wishlist_item(search_term, wishlist_items):
    """Use Gemini to find the best matching wishlist item"""
    
    # Create a list of items with their names
    item_list = []
    for i, item in enumerate(wishlist_items):
        item_name = item.get("item_name", "Unknown")
        price = item.get("estimated_price")
        priority = item.get("priority", 5)
        
        item_info = {
            "index": i,
            "name": item_name,
            "price": price,
            "priority": priority
        }
        item_list.append(item_info)
    
    # Create prompt for Gemini
    prompt = f"""
Find the best matching item from this wishlist based on the search term.

Search term: "{search_term}"

Wishlist items:
{json.dumps(item_list, ensure_ascii=False, indent=2)}

RULES:
- Find the item that best matches the search term
- Consider partial matches, case-insensitive matching
- Look for similar words or abbreviations
- If no good match found, return null

Return ONLY JSON:
{{
    "matched_index": <index_number_or_null>,
    "confidence": <high/medium/low>,
    "reason": "<brief_explanation>"
}}

Examples:
- Search "iphone" should match "iPhone 15 Pro"
- Search "laptop" should match "MacBook Pro" 
- Search "sofa" should match "Sofa gỗ cao cấp"
- Search "xyz123" with no similar items should return null
"""

    try:
        response = gemini_model.generate_content(prompt)
        result_text = response.text.strip()
        
        # Clean markdown formatting
        if result_text.startswith('```json'):
            result_text = result_text.replace('```json', '').replace('```', '').strip()
        
        result = json.loads(result_text)
        
        matched_index = result.get("matched_index")
        confidence = result.get("confidence", "low")
        
        # Only return match if confidence is reasonable and index is valid
        if (matched_index is not None and 
            confidence in ["high", "medium"] and 
            0 <= matched_index < len(wishlist_items)):
            return wishlist_items[matched_index]
        
        return None
        
    except Exception as e:
        logging.error(f"Gemini wishlist matching error: {e}")
        
        # Fallback to simple string matching
        search_lower = search_term.lower()
        for item in wishlist_items:
            item_name_lower = item.get("item_name", "").lower()
            if search_lower in item_name_lower or item_name_lower in search_lower:
                return item
        
        return None

def get_wishlist_priority_sums(user_id):
    """Get sums for wishlist levels - simple version"""
    try:
        wishlist_data = db.get_wishlist(user_id)
        if not wishlist_data.data:
            return {"level1": 0, "level2": 0, "level1_and_2": 0}
        
        active_items = [item for item in wishlist_data.data if not item.get("purchased", False)]
        
        level1_sum = 0
        level2_sum = 0
        
        for item in active_items:
            price = item.get("estimated_price")
            if not price:
                continue
            
            try:
                price = float(price)
            except (ValueError, TypeError):
                continue
            
            priority = item.get("priority", 5)
            try:
                priority = int(priority)
            except (ValueError, TypeError):
                priority = 5
            
            if priority == 1:
                level1_sum += price
            elif priority == 2:
                level2_sum += price
        
        return {
            "level1": level1_sum,
            "level2": level2_sum,
            "level1_and_2": level1_sum + level2_sum
        }
    except Exception:
        return {"level1": 0, "level2": 0, "level1_and_2": 0}

def get_simple_financial_data(user_id):
    """Get simple financial data without complex imports"""
    try:
        from datetime import datetime
        
        today = datetime.now()
        month_start = today.replace(day=1).date()
        
        # Get expenses
        expenses_data = db.get_monthly_expenses(user_id, month_start)
        total_expenses = 0
        if expenses_data.data:
            for expense in expenses_data.data:
                try:
                    total_expenses += float(expense["amount"])
                except (ValueError, TypeError):
                    pass
        
        # Get income
        income_data = db.get_monthly_income(user_id, month_start)
        total_income = 0
        if income_data.data:
            for income in income_data.data:
                try:
                    total_income += float(income["amount"])
                except (ValueError, TypeError):
                    pass
        
        return {
            "income": total_income,
            "expenses": total_expenses
        }
    except Exception:
        return {
            "income": 0,
            "expenses": 0
        }

# Backward compatibility
def get_wishlist_priority1_sum(user_id):
    """Backward compatibility function"""
    sums = get_wishlist_priority_sums(user_id)
    return sums["level1"]