import logging
from datetime import datetime, date
from decimal import Decimal
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes

from config import EXPENSE_CATEGORIES
from database import db
from ai_parser import parse_message_with_gemini, generate_monthly_summary
from utils import is_authorized, format_currency, parse_amount

# Set up logging
logging.basicConfig(level=logging.INFO)

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
    
    db.register_user(user_data)
    
    welcome_text = """
🤖 **Chào mừng đến với Bot Tài chính cá nhân!**

**Cách sử dụng:**
• **Chi tiêu**: "50k bún bò huế", "100k cát mèo", "1.5m bàn ghế"
• **Lương**: "lương 3m" 
• **Thu nhập thêm**: "thu nhập thêm 500k"

**Định dạng tiền:**
• 50k = 50,000đ | 1.5m = 1,500,000đ

**Lệnh:**
• /list - Xem chi tiêu tháng này
• /summary - Báo cáo tháng
• /saving - Xem tiết kiệm
• /category - Xem danh mục
• /wishlist - Xem wishlist
• /help - Hướng dẫn

AI tự động phân loại! 🤖🐱🪑
    """
    await update.message.reply_text(welcome_text)

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
                "category": expense.get("category", "khác"),
                "date": date.today().isoformat()
            }
            
            db.insert_expense(expense_data)
            responses.append(f"💰 Spent: {format_currency(expense['amount'])} - {expense['description']} ({expense.get('category', 'khác')})")
    
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
            
            db.insert_income(salary_data)
            responses.append(f"💵 Lương đã thêm: {format_currency(income_data['amount'])}")
    
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
            
            db.insert_income(random_income_data)
            responses.append(f"🎉 Thu nhập thêm: {format_currency(income_data['amount'])}")
    
    else:
        responses.append("🤔 Tôi không hiểu tin nhắn này. Thử:\n• '50k bún bò huế' (chi tiêu ăn uống)\n• '100k cát mèo' (chi phí mèo)\n• '1.5m bàn ghế' (nội thất)\n• 'lương 3m' (lương tháng)\n• 'thu nhập thêm 500k' (tiền thêm)")
    
    if responses:
        await update.message.reply_text("\n".join(responses))

async def savings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current savings amount"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    
    # Get current savings
    savings_data = db.get_savings(user_id)
    
    if savings_data.data:
        current_savings = float(savings_data.data[0]["current_amount"])
        last_updated = savings_data.data[0]["last_updated"]
        await update.message.reply_text(f"💰 **Tiết kiệm hiện tại**: {format_currency(current_savings)}\n📅 Cập nhật: {last_updated[:10]}")
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
            await update.message.reply_text("❌ Cách dùng: /editsaving 500k (để đặt tiết kiệm thành 500k)")
            return
        
        # Parse amount with k/m notation
        new_amount = parse_amount(args[0])
        
        # Update savings record
        savings_data = {
            "user_id": user_id,
            "current_amount": new_amount,
            "last_updated": datetime.now().isoformat()
        }
        
        db.upsert_savings(savings_data)
        
        await update.message.reply_text(f"✅ Đã cập nhật tiết kiệm!\n💰 **Tiết kiệm hiện tại**: {format_currency(new_amount)}")
        
    except ValueError:
        await update.message.reply_text("❌ Vui lòng nhập số hợp lệ: /editsaving 500k hoặc /editsaving 500000")

async def category_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show expenses by category: /category ăn uống"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        # Show all categories
        categories_list = "\n".join([f"• {cat}" for cat in EXPENSE_CATEGORIES])
        await update.message.reply_text(f"📂 **Danh mục chi tiêu:**\n\n{categories_list}\n\nDùng: `/category ăn uống`, `/category mèo`, hoặc `/category nội thất` để xem chi tiết")
        return
    
    category = " ".join(args).lower()
    
    # Get this month's expenses for this category
    today = datetime.now()
    month_start = today.replace(day=1).date()
    
    expenses = db.get_expenses_by_category(user_id, category, month_start)
    
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
            summary_lines.append(f"• {desc}: {format_currency(data['total'])} ({data['count']} lần)")
        else:
            summary_lines.append(f"• {desc}: {format_currency(data['total'])}")
    
    # Add special emoji for different categories
    if category == "mèo":
        category_emoji = "🐱"
    elif category == "nội thất":
        category_emoji = "🪑"
    else:
        category_emoji = "📂"
    
    summary_text = f"{category_emoji} **{category.title()}** - Tháng này\n\n"
    summary_text += "\n".join(summary_lines[:15])  # Limit to 15 items
    summary_text += f"\n\n💰 **Tổng cộng: {format_currency(total_category)}**"
    
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
• `50k bún bò huế` - ăn uống
• `100k cát mèo` - mèo cưng 🐱
• `1.5m bàn ghế` - nội thất 🪑
• `lương 3m` - lương tháng  

**Lệnh:**
• `/list` - xem chi tiêu tháng này
• `/summary` - báo cáo tháng
• `/saving` - xem tiết kiệm
• `/category` - xem danh mục
• `/wishlist` - xem wishlist

AI tự động phân loại! 🤖
    """
    await update.message.reply_text(help_text)

async def monthly_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    
    # Get this month's expenses and income
    today = datetime.now()
    month_start = today.replace(day=1).date()
    
    expenses = db.get_monthly_expenses(user_id, month_start)
    income = db.get_monthly_income(user_id, month_start)
    
    # Generate summary with Gemini
    expense_data = expenses.data
    income_data = income.data
    
    summary = generate_monthly_summary(expense_data, income_data, today.month, today.year)
    
    if summary:
        await update.message.reply_text(f"📊 **Báo cáo tháng {today.month}/{today.year}**\n\n{summary}")
    else:
        # Fallback summary
        total_expenses = sum(Decimal(str(exp["amount"])) for exp in expense_data)
        total_income = sum(Decimal(str(inc["amount"])) for inc in income_data)
        net_savings = total_income - total_expenses
        
        fallback_summary = f"""
📊 **Báo cáo tháng {today.month}/{today.year}**

💵 Tổng thu nhập: {format_currency(float(total_income))}
💰 Tổng chi tiêu: {format_currency(float(total_expenses))}
📈 Tiết kiệm ròng: {format_currency(float(net_savings))}

Chi tiêu: {len(expense_data)} lần
Thu nhập: {len(income_data)} lần
        """
        await update.message.reply_text(fallback_summary)

async def list_expenses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all expenses this month organized by category: /list"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    
    # Get this month's expenses
    today = datetime.now()
    month_start = today.replace(day=1).date()
    
    expenses = db.get_monthly_expenses(user_id, month_start)
    
    if not expenses.data:
        await update.message.reply_text(f"📝 Không có chi tiêu nào trong tháng {today.month}/{today.year}")
        return
    
    # Group expenses by category
    expenses_by_category = defaultdict(list)
    total_month = 0
    
    for expense in expenses.data:
        category = expense["category"]
        amount = float(expense["amount"])
        description = expense["description"]
        date = expense["date"]
        
        expenses_by_category[category].append({
            "amount": amount,
            "description": description,
            "date": date
        })
        total_month += amount
    
    # Build response
    response_text = f"📝 **Chi tiêu tháng {today.month}/{today.year}**\n\n"
    
    # Sort categories by total amount (highest first)
    category_totals = {}
    for category, items in expenses_by_category.items():
        category_totals[category] = sum(item["amount"] for item in items)
    
    sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    
    for category, category_total in sorted_categories:
        # Add category emoji
        if category == "mèo":
            category_emoji = "🐱"
        elif category == "nội thất":
            category_emoji = "🪑"
        elif category == "ăn uống":
            category_emoji = "🍜"
        elif category == "di chuyển":
            category_emoji = "🚗"
        elif category == "giải trí":
            category_emoji = "🎮"
        else:
            category_emoji = "📂"
        
        response_text += f"{category_emoji} **{category.upper()}** - {format_currency(category_total)}\n"
        
        # Sort items in category by date (newest first)
        items = sorted(expenses_by_category[category], key=lambda x: x["date"], reverse=True)
        
        for item in items:
            date_str = item["date"][5:10]  # MM-DD format
            response_text += f"  • {date_str}: {format_currency(item['amount'])} - {item['description']}\n"
        
        response_text += "\n"
    
    response_text += f"💰 **TỔNG CỘNG: {format_currency(total_month)}**"
    
    # Split long messages
    if len(response_text) > 4000:
        # Send in chunks
        chunks = []
        current_chunk = f"📝 **Chi tiêu tháng {today.month}/{today.year}**\n\n"
        
        for category, category_total in sorted_categories:
            category_text = f"{category_emoji} **{category.upper()}** - {format_currency(category_total)}\n"
            items = sorted(expenses_by_category[category], key=lambda x: x["date"], reverse=True)
            
            for item in items:
                date_str = item["date"][5:10]
                item_text = f"  • {date_str}: {format_currency(item['amount'])} - {item['description']}\n"
                
                if len(current_chunk + category_text + item_text) > 3500:
                    chunks.append(current_chunk.strip())
                    current_chunk = category_text + item_text
                else:
                    if category_text not in current_chunk:
                        current_chunk += category_text
                    current_chunk += item_text
            
            current_chunk += "\n"
        
        current_chunk += f"💰 **TỔNG CỘNG: {format_currency(total_month)}**"
        chunks.append(current_chunk.strip())
        
        # Send all chunks
        for i, chunk in enumerate(chunks):
            if i == 0:
                await update.message.reply_text(chunk)
            else:
                await update.message.reply_text(f"📝 **Tiếp tục...**\n\n{chunk}")
    else:
        await update.message.reply_text(response_text)