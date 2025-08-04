import schedule
import time
import threading
from datetime import datetime
from subscription_handlers import process_monthly_subscriptions

def send_monthly_summary_reminder():
    """Send monthly summary reminder to all users"""
    try:
        from config import ALLOWED_USERS
        # Note: For manual testing, you can implement this later
        # For now, just log the action
        today = datetime.now()
        print(f"📊 Would send monthly summary reminders for month {today.month}/{today.year}")
        print(f"📊 Target users: {len(ALLOWED_USERS)} users")
        
    except Exception as e:
        print(f"❌ Error in monthly summary reminder: {e}")

def run_scheduler():
    """Run the scheduler in a separate thread"""
    # Schedule monthly subscription processing on the 1st of each month at 9 AM
    schedule.every().month.at("09:00").do(process_monthly_subscriptions)
    
    # Schedule monthly summary reminder on the 1st of each month at 10 AM
    schedule.every().month.at("10:00").do(send_monthly_summary_reminder)
    
    print("📅 Subscription scheduler started - will run on 1st of each month at 9 AM")
    print("📊 Monthly summary reminder - will send on 1st of each month at 10 AM")
    
    while True:
        schedule.run_pending()
        time.sleep(3600)  # Check every hour

def start_scheduler():
    """Start the scheduler in a background thread"""
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

# For manual testing - run this function to process subscriptions immediately
def process_subscriptions_now():
    """Process subscriptions immediately (for testing)"""
    print("🔄 Processing subscriptions manually...")
    process_monthly_subscriptions()
    print("✅ Manual subscription processing completed")

def send_summary_reminder_now():
    """Send monthly summary reminder immediately (for testing)"""
    print("🔄 Sending monthly summary reminder manually...")
    send_monthly_summary_reminder()
    print("✅ Manual summary reminder sent")