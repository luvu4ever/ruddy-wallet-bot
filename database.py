from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class DatabaseManager:
    def __init__(self):
        self.supabase = supabase
    
    def register_user(self, user_data):
        """Register or update user in database"""
        return self.supabase.table("users").upsert(user_data).execute()
    
    def insert_expense(self, expense_data):
        """Insert expense record"""
        return self.supabase.table("expenses").insert(expense_data).execute()
    
    def insert_income(self, income_data):
        """Insert income record"""
        return self.supabase.table("income").insert(income_data).execute()
    
    def get_savings(self, user_id):
        """Get user's current savings"""
        return self.supabase.table("savings").select("*").eq("user_id", user_id).execute()
    
    def upsert_savings(self, savings_data):
        """Update or insert savings record"""
        return self.supabase.table("savings").upsert(savings_data).execute()
    
    def get_expenses_by_category(self, user_id, category, month_start):
        """Get expenses by category for current month"""
        return self.supabase.table("expenses").select("*").eq("user_id", user_id).eq("category", category).gte("date", month_start).execute()
    
    def get_monthly_expenses(self, user_id, month_start):
        """Get all expenses for current month"""
        return self.supabase.table("expenses").select("*").eq("user_id", user_id).gte("date", month_start).execute()
    
    def get_monthly_income(self, user_id, month_start):
        """Get all income for current month"""
        return self.supabase.table("income").select("*").eq("user_id", user_id).gte("date", month_start).execute()
    
    def insert_wishlist_item(self, wishlist_data):
        """Insert wishlist item"""
        return self.supabase.table("wishlist").insert(wishlist_data).execute()
    
    def get_wishlist(self, user_id):
        """Get all wishlist items"""
        return self.supabase.table("wishlist").select("*").eq("user_id", user_id).execute()
    
    def delete_wishlist_item(self, item_id):
        """Delete wishlist item"""
        return self.supabase.table("wishlist").delete().eq("id", item_id).execute()

# Global database instance
db = DatabaseManager()