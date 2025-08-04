from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.error import Conflict
from config import TELEGRAM_BOT_TOKEN
from handlers import (
    start,
    handle_message,
    savings_command,
    edit_savings_command,
    category_command,
    help_command,
    monthly_summary,
    list_expenses_command
)
from wishlist_handlers import (
    wishlist_add_command,
    wishlist_view_command,
    wishlist_remove_command
)
from subscription_handlers import (
    subscription_add_command,
    subscription_list_command,
    subscription_remove_command
)
from budget_handlers import (
    budget_command,
    budget_list_command
)
import time
import sys

def main():
    """Main function to run the bot"""
    try:
        # Create application
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("list", list_expenses_command))
        application.add_handler(CommandHandler("summary", monthly_summary))
        application.add_handler(CommandHandler("saving", savings_command))
        application.add_handler(CommandHandler("editsaving", edit_savings_command))
        application.add_handler(CommandHandler("category", category_command))
        
        # Simple wishlist handlers
        application.add_handler(CommandHandler("wishadd", wishlist_add_command))
        application.add_handler(CommandHandler("wishlist", wishlist_view_command))
        application.add_handler(CommandHandler("wishremove", wishlist_remove_command))
        
        # Subscription handlers
        application.add_handler(CommandHandler("subadd", subscription_add_command))
        application.add_handler(CommandHandler("sublist", subscription_list_command))
        application.add_handler(CommandHandler("subremove", subscription_remove_command))
        
        # Budget handlers
        application.add_handler(CommandHandler("budget", budget_command))
        application.add_handler(CommandHandler("budgetlist", budget_list_command))
        
        # Message handler (should be last)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Start the bot
        print("🤖 Simplified Personal Finance Bot is starting...")
        print("📂 Categories:", ", ".join([
            "ăn uống", "di chuyển", "giải trí", "mua sắm", 
            "hóa đơn", "sức khỏe", "giáo dục", "gia đình", "mèo", "nội thất", "khác"
        ]))
        print("💰 K/M/TR notation: 50k=50,000đ, 1.5m=1,500,000đ, 3tr=3,000,000đ")
        print("📝 Simple wishlist: add, view, remove")
        print("📅 Subscription feature: auto-added when calculating summary")
        print("💰 Budget planning: set spending limits per category")
        print("📊 Summary with date: /summary or /summary 8/2025")
        print("📝 New feature: /list command to view all monthly expenses by category")
        
        application.run_polling()
        
    except Conflict as e:
        print("❌ Bot conflict error: Another bot instance is running!")
        print("🔧 Solutions:")
        print("1. Stop other bot instances")
        print("2. Wait 30 seconds and try again")
        print("3. Check if bot is running elsewhere")
        print(f"Error details: {e}")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print("🔧 Restarting in 30 seconds...")
        time.sleep(30)
        main()  # Restart

if __name__ == "__main__":
    main()