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

# Load environment variables
load_dotenv()

# Initialize clients
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

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
🤖 **Welcome to your Personal Finance Bot!**

**Message Types:**
• **Expenses**: "700 meat 200 coffee" or "spent 50 on gas"
• **Salary**: "salary 3000" (monthly income)
• **Random Income**: "random income 500" (side jobs, bonuses)

**Commands:**
• /summary - Monthly overview
• /saving - Current savings amount
• /editsaving 500 - Set savings to $500
• /help - Show this help

I'll automatically categorize everything for you!
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
            responses.append(f"💰 Spent: ${expense['amount']:.2f} - {expense['description']} ({expense.get('category', 'other')})")
    
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
            responses.append(f"💵 Salary added: ${income_data['amount']:.2f}")
    
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
            responses.append(f"🎉 Extra income added: ${income_data['amount']:.2f}")
    
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
        await update.message.reply_text(f"💰 **Current Savings**: ${current_savings:.2f}\n📅 Last updated: {last_updated[:10]}")
    else:
        await update.message.reply_text("💰 **Current Savings**: $0.00\n\nUse /editsaving 500 to set your savings amount!")

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
    from collections import defaultdict
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
    """Show quick help"""
    if not is_authorized(update.effective_user.id):
        return
    
    help_text = """
💰 **Quick Help**

**Track Money:**
• `700 meat 200 coffee` - expenses
• `salary 3000` - monthly income  
• `random income 500` - extra money

**Commands:**
• `/saving` - check savings
• `/editsaving 1500` - set savings to $1500
• `/summary` - monthly report

Just type naturally - AI handles the rest! 🤖
    """
    await update.message.reply_text(help_text)

async def edit_savings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set savings to specific amount: /editsaving 500"""
    if not is_authorized(update.effective_user.id):
        return
    
    user_id = update.effective_user.id
    
    try:
        # Get amount from command
        args = context.args
        if not args:
            await update.message.reply_text("❌ Usage: /editsaving 500 (to set savings to $500)")
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
        
        await update.message.reply_text(f"✅ Savings updated!\n💰 **Current savings**: ${new_amount:.2f}")
        
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number: /editsaving 500")

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

import schedule
import threading
import time

def send_automatic_monthly_summary():
    """Send monthly summary to all users automatically"""
    for user_id in ALLOWED_USERS:
        try:
            # This would need to be called by a scheduler
            # Implementation depends on your deployment setup
            pass
        except Exception as e:
            logging.error(f"Failed to send auto summary to {user_id}: {e}")

def setup_monthly_scheduler():
    """Set up automatic monthly reports"""
    # Schedule for 1st day of month at 9 AM
    schedule.every().month.at("09:00").do(send_automatic_monthly_summary)
    
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(3600)  # Check every hour
    
    # Run scheduler in background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start the bot
    print("🤖 Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()