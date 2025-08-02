import os
import json
import logging
from datetime import datetime, date
from decimal import Decimal
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from supabase import create_client, Client
import google.generativeai as genai
from dotenv import load_dotenv
import schedule
import threading
import time
from collections import defaultdict

# Load environment variables
load_dotenv()

# Configurable categories - edit this list as needed
EXPENSE_CATEGORIES = [
    "ăn uống",      # food & drinks
    "di chuyển",    # transportation  
    "giải trí",     # entertainment
    "mua sắm",      # shopping
    "hóa đơn",      # bills/utilities
    "sức khỏe",     # health/medical
    "giáo dục",     # education
    "gia đình",     # family
    "khác"          # other
]

# Allowed users
ALLOWED_USERS = [int(uid) for uid in os.getenv("ALLOWED_USERS").split(",")]

# Initialize clients
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

# Set up logging
logging.basicConfig(level=logging.INFO)

def is_authorized(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ Sorry, you're not authorized to use this bot.")
        return
    
    # Register user in database
    user_data = {
        "telegram_id": update.effective_user.id,
        "first_name": update.effective_user.first_name,
        "username": update.effective_user.username
    }
    
    supabase.table("users").upsert(user_data).execute()
    
    welcome_text = """
🤖 **Chào mừng đến với Bot Tài chính cá nhân!**

**Cách sử dụng:**
• **Chi tiêu**: "50000 bún bò huế" hoặc "700000 thịt 200000 cà phê"
• **Lương**: "lương 3000000" (thu nhập tháng)
• **Thu nhập thêm**: "thu nhập thêm 500000" (làm thêm, thưởng)

**Lệnh:**
• /summary - Báo cáo tháng
• /saving - Xem tiết kiệm hiện tại
• /editsaving 500000 - Đặt tiết kiệm thành 500k
• /category - Xem danh mục
• /wishadd - Thêm wishlist
• /wishlist - Xem wishlist  
• /help - Hướng dẫn

AI tự động phân loại mọi thứ cho bạn! 🤖
    """
    await update.message.reply_text(welcome_text)

def parse_message_with_gemini(text: str, user_id: int) -> dict:
    """Use Gemini to parse Vietnamese/English messages"""
    
    categories_str = ", ".join(EXPENSE_CATEGORIES)
    
    prompt = f"""
Parse this Vietnamese/English message and identify its type. Return ONLY valid JSON.

Message: "{text}"

Detect these message types and extract data:

1. EXPENSES: "50 bún bò huế", "700 thịt 200 cà phê" or "spent 50 on gas"
2. SALARY: "lương 3000000", "salary 3000" or "got salary 2500"  
3. RANDOM INCOME: "thu nhập thêm 500000", "random income 500" or "side job 200"

Available categories: {categories_str}

Return format:
{{
    "type": "expenses|salary|random_income",
    "expenses": [
        {{"amount": 50000, "description": "bún bò huế", "category": "ăn uống"}},
        {{"amount": 700000, "description": "thịt", "category": "ăn uống"}}
    ],
    "income": {{
        "amount": 3000000,
        "type": "salary|random",
        "description": "monthly salary"
    }}
}}

IMPORTANT: 
- Use the exact categories from the list: {categories_str}
- For Vietnamese food items, always use "ăn uống" category
- For transportation (xe ôm, grab, xăng), use "di chuyển"
- Automatically detect Vietnamese currency amounts (đồng)
- Extract all amount+item pairs from the message

Return empty arrays/objects for unused fields.
"""

    try:
        response = gemini_model.generate_content(prompt)
        result_text = response.text.strip()
        
        # Clean up response if it has markdown formatting
        if result_text.startswith('```json'):
            result_text = result_text.replace('```json', '').replace('```', '').strip()
        
        result = json.loads(result_text)
        return result
        
    except Exception as e:
        logging.error(f"Gemini parsing error: {e}")
        return {"type": "unknown", "expenses": [], "income": {}}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ Not authorized.")
        return
    
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Parse with Gemini
    parsed_data = parse_message_with_gemini(message_text, user_id)
    
    responses = []
    message_type = parsed_data.get("type", "unknown")
    
    # Handle different message types
    if message_type == "expenses":
        # Save expenses
        for expense in parsed_data.get("expenses", []):
            expense_data = {
                "user_id": user_id,
                "amount": expense["amount"],
                "description": expense["description"],
                "category": expense.get("category", "other"),
                "date": date.today().isoformat()
            }
            
            supabase.table("expenses").insert(expense_data).execute()
            responses.append(f"💰 Spent: {expense['amount']:,.0f}đ - {expense['description']} ({expense.get('category', 'other')})")
    
    elif message_type == "salary":
        # Save salary income
        income_data = parsed_data.get("income", {})
        if income_data:
            salary_data = {
                "user_id": user_id,
                "amount": income_data["amount"],
                "income_type": "salary",
                "description": income_data.get("description", "Monthly salary"),
                "date": date.today().isoformat()
            }
            
            supabase.table("income").insert(salary_data).execute()
            responses.append(f"💵 Lương đã thêm: {income_data['amount']:,.0f}đ")
    
    elif message_type == "random_income":
        # Save random income
        income_data = parsed_data.get("income", {})
        if income_data:
            random_income_data = {
                "user_id": user_id,
                "amount": income_data["amount"],
                "income_type": "random",
                "description": income_data.get("description", "Additional income"),
                "date": date.today().isoformat()
            }
            
            supabase.table("income").insert(random_income_data).execute()
            responses.append(f"🎉 Thu nhập thêm: {income_data['amount']:,.0f}đ")
    
    else:
        responses.append("🤔 Tôi không hiểu tin nhắn này. Thử:\n• '50000 bún bò huế' (chi tiêu)\n• 'lương 3000000' (lương tháng)\n• 'thu nhập thêm 500000' (tiền thêm)")
    
    if responses:
        await update.message.reply_text("\n".join(responses))

async def savings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current savings amount"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    
    # Get current savings
    savings_data = supabase.table("savings").select("*").eq("user_id", user_id).execute()
    
    if savings_data.data:
        current_savings = float(savings_data.data[0]["current_amount"])
        last_updated = savings_data.data[0]["last_updated"]
        await update.message.reply_text(f"💰 **Tiết kiệm hiện tại**: {current_savings:,.0f}đ\n📅 Cập nhật: {last_updated[:10]}")
    else:
        await update.message.reply_text("💰 **Tiết kiệm hiện tại**: 0đ\n\nDùng /editsaving 500000 để đặt số tiền tiết kiệm!")

async def edit_savings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set savings to specific amount: /editsaving 500000"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    
    try:
        # Get amount from command
        args = context.args
        if not args:
            await update.message.reply_text("❌ Cách dùng: /editsaving 500000 (để đặt tiết kiệm thành 500k)")
            return
        
        new_amount = float(args[0])
        
        # Update or insert savings record
        savings_data = {
            "user_id": user_id,
            "current_amount": new_amount,
            "last_updated": datetime.now().isoformat()
        }
        
        # Use upsert to update if exists, insert if not
        supabase.table("savings").upsert(savings_data).execute()
        
        await update.message.reply_text(f"✅ Đã cập nhật tiết kiệm!\n💰 **Tiết kiệm hiện tại**: {new_amount:,.0f}đ")
        
    except ValueError:
        await update.message.reply_text("❌ Vui lòng nhập số hợp lệ: /editsaving 500000")

async def category_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show expenses by category: /category ăn uống"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        # Show all categories
        categories_list = "\n".join([f"• {cat}" for cat in EXPENSE_CATEGORIES])
        await update.message.reply_text(f"📂 **Danh mục chi tiêu:**\n\n{categories_list}\n\nDùng: `/category ăn uống` để xem chi tiết")
        return
    
    category = " ".join(args).lower()
    
    # Get this month's expenses for this category
    today = datetime.now()
    month_start = today.replace(day=1).date()
    
    expenses = supabase.table("expenses").select("*").eq("user_id", user_id).eq("category", category).gte("date", month_start).execute()
    
    if not expenses.data:
        await update.message.reply_text(f"📂 Không có chi tiêu nào cho danh mục '{category}' tháng này")
        return
    
    # Group by description and sum amounts
    items_summary = defaultdict(lambda: {"total": 0, "count": 0})
    
    for expense in expenses.data:
        desc = expense["description"]
        amount = float(expense["amount"])
        items_summary[desc]["total"] += amount
        items_summary[desc]["count"] += 1
    
    # Create summary
    total_category = sum(item["total"] for item in items_summary.values())
    
    summary_lines = []
    for desc, data in sorted(items_summary.items(), key=lambda x: x[1]["total"], reverse=True):
        if data["count"] > 1:
            summary_lines.append(f"• {desc}: {data['total']:,.0f}đ ({data['count']} lần)")
        else:
            summary_lines.append(f"• {desc}: {data['total']:,.0f}đ")
    
    summary_text = f"📂 **{category.title()}** - Tháng này\n\n"
    summary_text += "\n".join(summary_lines[:15])  # Limit to 15 items
    summary_text += f"\n\n💰 **Tổng cộng: {total_category:,.0f}đ**"
    
    if len(summary_lines) > 15:
        summary_text += f"\n\n... và {len(summary_lines) - 15} mục khác"
    
    await update.message.reply_text(summary_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show quick help in Vietnamese"""
    if not is_authorized(update.effective_user.id):
        return
    
    help_text = """
💰 **Hướng dẫn nhanh**

**Ghi chi tiêu:**
• `50000 bún bò huế` - chi tiêu
• `lương 3000000` - lương tháng  
• `thu nhập thêm 500000` - tiền thêm

**Lệnh:**
• `/saving` - xem tiết kiệm
• `/editsaving 1500000` - đặt tiết kiệm
• `/summary` - báo cáo tháng
• `/category` - xem danh mục
• `/category ăn uống` - chi tiết danh mục
• `/wishadd iPhone 25000000` - thêm wishlist
• `/wishlist` - xem wishlist
• `/wishbuy 1` - đánh dấu đã mua

AI tự động phân loại! 🤖
    """
    await update.message.reply_text(help_text)

async def monthly_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    
    # Get this month's expenses
    today = datetime.now()
    month_start = today.replace(day=1).date()
    
    expenses = supabase.table("expenses").select("*").eq("user_id", user_id).gte("date", month_start).execute()
    income = supabase.table("income").select("*").eq("user_id", user_id).gte("date", month_start).execute()
    
    # Generate summary with Gemini in Vietnamese
    expense_data = expenses.data
    income_data = income.data
    
    summary_prompt = f"""
Tạo báo cáo tài chính tháng này bằng tiếng Việt cho dữ liệu:

Chi tiêu tháng này: {json.dumps(expense_data, default=str)}
Thu nhập tháng này: {json.dumps(income_data, default=str)}

Bao gồm:
- Tổng thu nhập tháng này (đồng VND)
- Tổng chi tiêu tháng này (đồng VND) 
- Tiết kiệm ròng (thu nhập - chi tiêu)
- Top 5 danh mục chi tiêu nhiều nhất
- Nhận xét và đề xuất

Viết bằng tiếng Việt, thân thiện và có emoji. Dùng định dạng tiền VND (ví dụ: 1.500.000đ).
"""
    
    try:
        response = gemini_model.generate_content(summary_prompt)
        summary = response.text
        await update.message.reply_text(f"📊 **Báo cáo tháng {today.month}/{today.year}**\n\n{summary}")
        
    except Exception as e:
        total_expenses = sum(Decimal(str(exp["amount"])) for exp in expense_data)
        total_income = sum(Decimal(str(inc["amount"])) for inc in income_data)
        net_savings = total_income - total_expenses
        
        fallback_summary = f"""
📊 **Báo cáo tháng {today.month}/{today.year}**

💵 Tổng thu nhập: {total_income:,.0f}đ
💰 Tổng chi tiêu: {total_expenses:,.0f}đ
📈 Tiết kiệm ròng: {net_savings:,.0f}đ

Chi tiêu: {len(expense_data)} lần
Thu nhập: {len(income_data)} lần
        """
        await update.message.reply_text(fallback_summary)

async def wishlist_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add item to wishlist: /wishadd iPhone 15 Pro 25000000"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if len(args) < 2:
        await update.message.reply_text("❌ Cách dùng: /wishadd iPhone 15 Pro 25000000\n(tên sản phẩm và giá dự kiến)")
        return
    
    try:
        # Last argument should be price
        estimated_price = float(args[-1])
        item_name = " ".join(args[:-1])
        
        wishlist_data = {
            "user_id": user_id,
            "item_name": item_name,
            "estimated_price": estimated_price,
            "priority": 1,  # Default priority
            "category": "khác",  # Default category
            "purchased": False
        }
        
        supabase.table("wishlist").insert(wishlist_data).execute()
        await update.message.reply_text(f"✅ Đã thêm vào wishlist!\n🛍️ **{item_name}**: {estimated_price:,.0f}đ")
        
    except ValueError:
        await update.message.reply_text("❌ Giá phải là số. Ví dụ: /wishadd iPhone 15 25000000")

async def wishlist_view_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View wishlist: /wishlist"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    
    # Get all wishlist items (not purchased)
    wishlist_data = supabase.table("wishlist").select("*").eq("user_id", user_id).eq("purchased", False).execute()
    
    if not wishlist_data.data:
        await update.message.reply_text("📝 Wishlist trống!\n\nDùng /wishadd để thêm sản phẩm mong muốn")
        return
    
    # Sort by priority (high to low) then by price
    items = sorted(wishlist_data.data, key=lambda x: (-x.get("priority", 1), -x.get("estimated_price", 0)))
    
    wishlist_text = "🛍️ **Wishlist của bạn:**\n\n"
    total_wishlist = 0
    
    for i, item in enumerate(items[:20], 1):  # Limit to 20 items
        name = item["item_name"]
        price = item.get("estimated_price", 0)
        priority = item.get("priority", 1)
        
        priority_emoji = "🔥" if priority == 3 else "⭐" if priority == 2 else "💭"
        
        wishlist_text += f"{i}. {priority_emoji} **{name}**: {price:,.0f}đ\n"
        total_wishlist += price
    
    wishlist_text += f"\n💰 **Tổng giá trị**: {total_wishlist:,.0f}đ"
    
    if len(items) > 20:
        wishlist_text += f"\n\n... và {len(items) - 20} sản phẩm khác"
    
    wishlist_text += "\n\n**Lệnh:**\n• /wishbuy [số] - đánh dấu đã mua\n• /wishpriority [số] [1-3] - đặt độ ưu tiên"
    
    await update.message.reply_text(wishlist_text)

async def wishlist_buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mark item as purchased: /wishbuy 1"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await update.message.reply_text("❌ Cách dùng: /wishbuy 1 (số thứ tự từ wishlist)")
        return
    
    try:
        item_index = int(args[0]) - 1  # Convert to 0-based index
        
        # Get wishlist items
        wishlist_data = supabase.table("wishlist").select("*").eq("user_id", user_id).eq("purchased", False).execute()
        
        if not wishlist_data.data or item_index >= len(wishlist_data.data):
            await update.message.reply_text("❌ Số thứ tự không hợp lệ. Kiểm tra lại /wishlist")
            return
        
        # Sort same as in view function
        items = sorted(wishlist_data.data, key=lambda x: (-x.get("priority", 1), -x.get("estimated_price", 0)))
        selected_item = items[item_index]
        
        # Mark as purchased
        supabase.table("wishlist").update({"purchased": True}).eq("id", selected_item["id"]).execute()
        
        item_name = selected_item["item_name"]
        item_price = selected_item.get("estimated_price", 0)
        
        await update.message.reply_text(f"🎉 Chúc mừng! Đã mua **{item_name}**!\n💰 Giá: {item_price:,.0f}đ")
        
    except ValueError:
        await update.message.reply_text("❌ Vui lòng nhập số hợp lệ: /wishbuy 1")

async def wishlist_priority_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set item priority: /wishpriority 1 3"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if len(args) != 2:
        await update.message.reply_text("❌ Cách dùng: /wishpriority 1 3\n(số thứ tự và độ ưu tiên 1-3)\n\n1 = thấp 💭\n2 = trung bình ⭐\n3 = cao 🔥")
        return
    
    try:
        item_index = int(args[0]) - 1
        priority = int(args[1])
        
        if priority not in [1, 2, 3]:
            await update.message.reply_text("❌ Độ ưu tiên phải là 1, 2, hoặc 3")
            return
        
        # Get wishlist items
        wishlist_data = supabase.table("wishlist").select("*").eq("user_id", user_id).eq("purchased", False).execute()
        
        if not wishlist_data.data or item_index >= len(wishlist_data.data):
            await update.message.reply_text("❌ Số thứ tự không hợp lệ. Kiểm tra lại /wishlist")
            return
        
        items = sorted(wishlist_data.data, key=lambda x: (-x.get("priority", 1), -x.get("estimated_price", 0)))
        selected_item = items[item_index]
        
        # Update priority
        supabase.table("wishlist").update({"priority": priority}).eq("id", selected_item["id"]).execute()
        
        priority_text = "cao 🔥" if priority == 3 else "trung bình ⭐" if priority == 2 else "thấp 💭"
        
        await update.message.reply_text(f"✅ Đã cập nhật độ ưu tiên!\n🛍️ **{selected_item['item_name']}**: {priority_text}")
        
    except ValueError:
        await update.message.reply_text("❌ Vui lòng nhập số hợp lệ: /wishpriority 1 3")

async def wishlist_bought_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View purchased items: /wishbought"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    
    # Get purchased items
    bought_data = supabase.table("wishlist").select("*").eq("user_id", user_id).eq("purchased", True).execute()
    
    if not bought_data.data:
        await update.message.reply_text("🛍️ Chưa mua sản phẩm nào từ wishlist!")
        return
    
    bought_text = "🎉 **Đã mua từ wishlist:**\n\n"
    total_spent = 0
    
    for i, item in enumerate(bought_data.data, 1):
        name = item["item_name"]
        price = item.get("estimated_price", 0)
        bought_text += f"{i}. ✅ **{name}**: {price:,.0f}đ\n"
        total_spent += price
    
    bought_text += f"\n💰 **Tổng đã chi**: {total_spent:,.0f}đ"
    
    await update.message.reply_text(bought_text)

def main():
    # Create application
    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("summary", monthly_summary))
    application.add_handler(CommandHandler("month", monthly_summary))
    application.add_handler(CommandHandler("saving", savings_command))
    application.add_handler(CommandHandler("editsaving", edit_savings_command))
    application.add_handler(CommandHandler("category", category_command))
    application.add_handler(CommandHandler("wishadd", wishlist_add_command))
    application.add_handler(CommandHandler("wishlist", wishlist_view_command))
    application.add_handler(CommandHandler("wishbuy", wishlist_buy_command))
    application.add_handler(CommandHandler("wishpriority", wishlist_priority_command))
    application.add_handler(CommandHandler("wishbought", wishlist_bought_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start the bot
    print("🤖 Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()