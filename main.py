from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.error import Conflict
from config import TELEGRAM_BOT_TOKEN, get_category_list_display, get_startup_message, get_error_message

# Import all handlers from the handlers package
from handlers import (
    start,
    handle_message,
    savings_command,
    edit_savings_command,
    category_command,
    help_command,
    monthly_summary,
    list_expenses_command,
    wishlist_add_command,
    wishlist_view_command,
    wishlist_remove_command,
    subscription_add_command,
    subscription_list_command,
    subscription_remove_command,
    budget_command,
    budget_list_command,
    income_command
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
        
        # Income handlers
        application.add_handler(CommandHandler("income", income_command))
        
        # Message handler (should be last)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Start the bot
        print(get_startup_message("starting"))
        print(get_startup_message("categories", categories=get_category_list_display()))
        print(get_startup_message("notation"))
        print(get_startup_message("wishlist"))
        print(get_startup_message("subscriptions"))
        print(get_startup_message("budget"))
        print(get_startup_message("summary"))
        print(get_startup_message("list_feature"))
        
        application.run_polling()
        
    except Conflict as e:
        print(get_error_message("bot_conflict"))
        print(get_error_message("solutions"))
        print("Error details:", str(e))
        sys.exit(1)
        
    except Exception as e:
        print(get_error_message("unexpected", error=str(e)))
        print(get_error_message("restarting"))
        time.sleep(30)
        main()  # Restart

if __name__ == "__main__":
    main()