from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.error import Conflict
from config import TELEGRAM_BOT_TOKEN

# Import all handlers - REMOVED category_command
from handlers import (
    start, handle_message, savings_command, edit_savings_command,
    help_command, monthly_summary, list_expenses_command,
    wishlist_add_command, wishlist_view_command, wishlist_remove_command,
    subscription_add_command, subscription_list_command, subscription_remove_command,
    budget_command, budget_list_command, income_command,
    account_command, account_edit_command,
    allocation_command,
    endmonth_command, monthhistory_command  # Month-end handlers
)

import time
import sys

def main():
    """Main function - simplified"""
    try:
        # Create application
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        
        # Expense & Income
        application.add_handler(CommandHandler("list", list_expenses_command))  # Enhanced list command
        application.add_handler(CommandHandler("summary", monthly_summary))
        application.add_handler(CommandHandler("saving", savings_command))
        application.add_handler(CommandHandler("editsaving", edit_savings_command))
        # REMOVED: category_command - functionality moved to list_expenses_command
        application.add_handler(CommandHandler("income", income_command))
        
        # Wishlist (5 levels)
        application.add_handler(CommandHandler("wishadd", wishlist_add_command))
        application.add_handler(CommandHandler("wishlist", wishlist_view_command))
        application.add_handler(CommandHandler("wishremove", wishlist_remove_command))
        
        # Subscriptions
        application.add_handler(CommandHandler("subadd", subscription_add_command))
        application.add_handler(CommandHandler("sublist", subscription_list_command))
        application.add_handler(CommandHandler("subremove", subscription_remove_command))
        
        # Budget
        application.add_handler(CommandHandler("budget", budget_command))
        application.add_handler(CommandHandler("budgetlist", budget_list_command))

        # Account
        application.add_handler(CommandHandler("account", account_command))
        application.add_handler(CommandHandler("accountedit", account_edit_command))
        
        # Allocation
        application.add_handler(CommandHandler("allocation", allocation_command))
        
        # Month-end processing
        application.add_handler(CommandHandler("endmonth", endmonth_command))
        application.add_handler(CommandHandler("monthhistory", monthhistory_command))
        
        # Message handler (must be last)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Simple startup message
        print("🤖 Starting Personal Finance Bot...")
        print("🔄 Enhanced /list command with date support enabled!")
        print("🚀 Bot is running!")
        
        application.run_polling()
        
    except Conflict:
        print("❌ Bot conflict: Another instance is running!")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        time.sleep(30)
        main()

if __name__ == "__main__":
    main()