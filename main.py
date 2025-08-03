from telegram.ext import Application, CommandHandler, MessageHandler, filters
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

def main():
    """Main function to run the bot"""
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
    
    # Message handler (should be last)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start the bot
    print("🤖 Simplified Personal Finance Bot is starting...")
    print("📂 Categories:", ", ".join([
        "ăn uống", "di chuyển", "giải trí", "mua sắm", 
        "hóa đơn", "sức khỏe", "giáo dục", "gia đình", "mèo", "nội thất", "khác"
    ]))
    print("💰 K/M notation: 50k=50,000đ, 1.5m=1,500,000đ")
    print("📝 Simple wishlist: add, view, remove")
    print("📝 New feature: /list command to view all monthly expenses by category")
    application.run_polling()

if __name__ == "__main__":
    main()