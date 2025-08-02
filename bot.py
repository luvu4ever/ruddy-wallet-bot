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
- **Expenses**: "700 meat 200 coffee" or "spent 50 on gas"
- **Salary**: "salary 3000" (monthly income)
- **Random Income**: "random income 500" (side jobs, bonuses)

**Commands:**
- /summary - Monthly overview
- /saving - Current savings amount
- /editsaving 500 - Set savings to $500

I'll automatically categorize everything for you!
    """
    await update.message.reply_text(welcome_text)

def parse_message_with_gemini(text: str, user_id: int) -> dict:
    """Use Gemini to parse different message types"""
    
    prompt = f"""
Parse this message and identify its type. Return ONLY valid JSON.

Message: "{text}"

Detect these message types and extract data:

1. EXPENSES: "700 meat 200 coffee" or "spent 50 on gas"
2. SALARY: "salary 3000" or "got salary 2500"  
3. RANDOM INCOME: "random income 500" or "side job 200"

Return format:
{{
    "type": "expenses|salary|random_income",
    "expenses": [
        {{"amount": 700, "description": "meat", "category": "food"}},
        {{"amount": 200, "description": "coffee", "category": "food"}}
    ],
    "income": {{
        "amount": 3000,
        "type": "salary|random",
        "description": "monthly salary"
    }}
}}

Categories for expenses: food, transport, entertainment, shopping, bills, health, other

For expenses: extract all amount+item pairs
For salary: look for "salary" keyword
For random income: look for "random income", "side job", "bonus", etc.

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
        responses.append("🤔 I couldn't understand that message. Try:\n• '700 meat 200 coffee' (expenses)\n• 'salary 3000' (monthly salary)\n• 'random income 500' (extra money)")
    
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
    subscriptions = supabase.table("subscriptions").select("*").eq("user_id", user_id).execute()
    
    # Generate summary with Gemini
    expense_data = expenses.data
    subscription_data = subscriptions.data
    
    summary_prompt = f"""
Create a friendly monthly expense summary for this data:

Expenses this month: {json.dumps(expense_data, default=str)}
Active subscriptions: {json.dumps(subscription_data, default=str)}

Make it conversational and include:
- Total spent this month
- Top categories
- Subscription costs
- Any insights or patterns

Keep it concise but helpful. Use emojis to make it friendly.
"""
    
    try:
        response = gemini_model.generate_content(summary_prompt)
        summary = response.text
        await update.message.reply_text(f"📊 **Monthly Summary**\n\n{summary}")
        
    except Exception as e:
        total_expenses = sum(Decimal(str(exp["amount"])) for exp in expense_data)
        total_subscriptions = sum(Decimal(str(sub["amount"])) for sub in subscription_data)
        
        fallback_summary = f"""
📊 **Monthly Summary**

💰 Total Expenses: ${total_expenses:.2f}
🔄 Monthly Subscriptions: ${total_subscriptions:.2f}
📈 Total Monthly Spending: ${total_expenses + total_subscriptions:.2f}

Expenses this month: {len(expense_data)} entries
Active subscriptions: {len(subscription_data)} services
        """
        await update.message.reply_text(fallback_summary)

def main():
    # Create application
    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("summary", monthly_summary))
    application.add_handler(CommandHandler("month", monthly_summary))
    application.add_handler(CommandHandler("saving", savings_command))
    application.add_handler(CommandHandler("editsaving", edit_savings_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start the bot
    print("🤖 Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()