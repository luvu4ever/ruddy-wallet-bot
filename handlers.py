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
from budget_handlers import calculate_remaining_budget, get_total_budget, get_category_emoji

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
• 50k = 50,000đ | 1.5m = 1,500,000đ | 3tr = 3,000,000đ

**Lệnh:**
• /list - Xem chi tiêu tháng này
• /summary - Báo cáo tháng này
• /summary 8/2025 - Báo cáo tháng 8/2025
• /budget ăn uống 1.5m - Đặt budget
• /sublist - Xem subscriptions
• /saving - Xem tiết kiệm
• /wishlist - Xem wishlist
• /help - Hướng dẫn

AI tự động phân loại! 🤖🐱🪑
Subscriptions tự động hàng tháng! 📅
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
        responses.append("🤔 Tôi không hiểu tin nhắn này. Thử:\n• '50k bún bò huế' (chi tiêu ăn uống)\n• '100k cát mèo' (chi phí mèo)\n• '1.5m bàn ghế' hoặc '1.5tr bàn ghế' (nội thất)\n• 'lương 3m' hoặc 'lương 3tr' (lương tháng)\n• 'thu nhập thêm 500k' (tiền thêm)")
    
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
        await update.message.reply_text("💰 **Tiết kiệm hiện tại**: 0đ\n\nDùng /editsaving 500k để đặt số tiền tiết kiệm!")

async def edit_savings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set savings to specific amount: /editsaving 500k"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    
    try:
        # Get amount from command
        args = context.args
        if not args:
            await update.message.reply_text("❌ Cách dùng: /editsaving 500k (để đặt tiết kiệm thành 500k)")
            return
        
        # Parse amount with k/m/tr notation
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
        await update.message.reply_text("❌ Vui lòng nhập số hợp lệ: /editsaving 500k hoặc /editsaving 1.5tr")

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
    category_emoji = get_category_emoji(category)
    
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

**Subscriptions:**
• `/subadd Spotify 33k` - thêm subscription
• `/sublist` - xem subscriptions
• `/subremove 1` - xóa subscription

**Budget:**
• `/budget ăn uống 1.5m` - đặt budget
• `/budgetlist` - xem budget plans

**Lệnh:**
• `/list` - xem chi tiêu tháng này
• `/summary` - báo cáo tháng này
• `/summary 8/2025` - báo cáo tháng 8/2025
• `/saving` - xem tiết kiệm
• `/category` - xem danh mục
• `/wishlist` - xem wishlist

AI tự động phân loại! 🤖
    """
    await update.message.reply_text(help_text)

async def monthly_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate monthly summary: /summary or /summary 8/2025"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    args = context.args
    
    # Parse date argument
    if args:
        try:
            # Parse format: 8/2025 or 08/2025
            date_str = args[0]
            if '/' in date_str:
                month_str, year_str = date_str.split('/')
                target_month = int(month_str)
                target_year = int(year_str)
            else:
                await update.message.reply_text("❌ Format: /summary 8/2025 hoặc /summary (tháng này)")
                return
                
            if target_month < 1 or target_month > 12:
                await update.message.reply_text("❌ Tháng phải từ 1-12")
                return
                
        except ValueError:
            await update.message.reply_text("❌ Format: /summary 8/2025 hoặc /summary (tháng này)")
            return
    else:
        # Use current month
        today = datetime.now()
        target_month = today.month
        target_year = today.year
    
    # Calculate month boundaries
    month_start = date(target_year, target_month, 1)
    if target_month == 12:
        month_end = date(target_year + 1, 1, 1)
    else:
        month_end = date(target_year, target_month + 1, 1)
    
    # Get expenses and income for the target month
    expenses = db.get_monthly_expenses(user_id, month_start)
    income = db.get_monthly_income(user_id, month_start)
    
    # Auto-add subscriptions to expenses for this month
    subscriptions = db.get_subscriptions(user_id)
    subscription_expenses = []
    
    if subscriptions.data:
        for subscription in subscriptions.data:
            # Check if subscription expense already exists for this month
            existing_sub_expense = None
            for expense in expenses.data:
                if (expense["description"] == f"{subscription['service_name']} (subscription)" and
                    expense["date"][:7] == f"{target_year}-{target_month:02d}"):
                    existing_sub_expense = expense
                    break
            
            # If not exists, add it
            if not existing_sub_expense:
                subscription_expense = {
                    "user_id": user_id,
                    "amount": subscription["amount"],
                    "description": f"{subscription['service_name']} (subscription)",
                    "category": "khác",
                    "date": month_start.isoformat()
                }
                
                # Add to database
                db.insert_expense(subscription_expense)
                
                # Add to current expense list for summary calculation
                subscription_expenses.append(subscription_expense)
    
    # Refresh expenses data after adding subscriptions
    if subscription_expenses:
        expenses = db.get_monthly_expenses(user_id, month_start)
    
    # Get total budget
    total_budget = get_total_budget(user_id)
    
    # Generate enhanced summary data
    expense_data = expenses.data
    income_data = income.data
    
    # Calculate totals
    total_expenses = sum(float(exp["amount"]) for exp in expense_data)
    total_income = sum(float(inc["amount"]) for inc in income_data)
    
    # Show added subscriptions
    subscription_info = ""
    if subscription_expenses:
        sub_names = [sub["description"].replace(" (subscription)", "") for sub in subscription_expenses]
        subscription_info = f"\n🔄 **Đã thêm subscriptions**: {', '.join(sub_names)}"
    
    summary = generate_monthly_summary(expense_data, income_data, target_month, target_year)
    
    # Add budget information to summary
    budget_summary = ""
    if total_budget > 0:
        remaining_budget = total_budget - total_expenses
        if remaining_budget >= 0:
            budget_summary = f"\n💰 **Budget tháng này**: {format_currency(total_budget)}\n✅ **Còn lại**: {format_currency(remaining_budget)}"
        else:
            budget_summary = f"\n💰 **Budget tháng này**: {format_currency(total_budget)}\n⚠️ **Vượt budget**: {format_currency(abs(remaining_budget))}"
    
    if summary:
        full_summary = f"📊 **Báo cáo tháng {target_month}/{target_year}**{subscription_info}\n\n{summary}{budget_summary}"
        await update.message.reply_text(full_summary)
    else:
        # Fallback summary with budget
        net_savings = total_income - total_expenses
        
        fallback_summary = f"""
📊 **Báo cáo tháng {target_month}/{target_year}**{subscription_info}

💵 Tổng thu nhập: {format_currency(total_income)}
💰 Tổng chi tiêu: {format_currency(total_expenses)}
📈 Tiết kiệm ròng: {format_currency(net_savings)}

Chi tiêu: {len(expense_data)} lần
Thu nhập: {len(income_data)} lần{budget_summary}
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
    
    # Calculate remaining budget
    remaining_budget = calculate_remaining_budget(user_id, month_start)
    
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
        category_emoji = get_category_emoji(category)
        
        # Get budget info if available
        budget_info = ""
        if category in remaining_budget:
            budget_data = remaining_budget[category]
            remaining = budget_data["remaining"]
            if remaining >= 0:
                budget_info = f" (còn lại: {format_currency(remaining)})"
            else:
                budget_info = f" (⚠️ vượt: {format_currency(abs(remaining))})"
        
        response_text += f"{category_emoji} **{category.upper()}** - {format_currency(category_total)}{budget_info}\n"
        
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
            # Split long messages with budget info
            category_emoji = get_category_emoji(category)
            budget_info = ""
            if category in remaining_budget:
                budget_data = remaining_budget[category]
                remaining = budget_data["remaining"] 
                if remaining >= 0:
                    budget_info = f" (còn lại: {format_currency(remaining)})"
                else:
                    budget_info = f" (⚠️ vượt: {format_currency(abs(remaining))})"
            
            category_text = f"{category_emoji} **{category.upper()}** - {format_currency(category_total)}{budget_info}\n"
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