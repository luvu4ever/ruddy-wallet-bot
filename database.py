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
    
    def insert_subscription(self, subscription_data):
        """Insert subscription"""
        return self.supabase.table("subscriptions").insert(subscription_data).execute()
    
    def get_subscriptions(self, user_id):
        """Get all subscriptions for user"""
        return self.supabase.table("subscriptions").select("*").eq("user_id", user_id).execute()
    
    def delete_subscription(self, subscription_id):
        """Delete subscription"""
        return self.supabase.table("subscriptions").delete().eq("id", subscription_id).execute()
    
    def get_all_active_subscriptions(self):
        """Get all subscriptions for monthly processing"""
        return self.supabase.table("subscriptions").select("*").execute()
    
    def insert_budget_plan(self, budget_data):
        """Insert or update budget plan"""
        return self.supabase.table("budget_plans").upsert(budget_data).execute()
    
    def get_budget_plans(self, user_id):
        """Get all budget plans for user"""
        return self.supabase.table("budget_plans").select("*").eq("user_id", user_id).execute()
    
    def get_budget_plan_by_category(self, user_id, category):
        """Get budget plan for specific category"""
        return self.supabase.table("budget_plans").select("*").eq("user_id", user_id).eq("category", category).execute()

    def get_budget_plan_by_category(self, user_id, category):
        """Get budget plan for specific category"""
        return self.supabase.table("budget_plans").select("*").eq("user_id", user_id).eq("category", category).execute()
    
    def get_accounts(self, user_id):
        """Get all accounts for user"""
        return self.supabase.table("accounts").select("*").eq("user_id", user_id).execute()
    
    def upsert_account(self, account_data):
        """Insert or update account record with proper conflict resolution"""
        try:
            # Use on_conflict parameter to specify which columns to use for conflict resolution
            return self.supabase.table("accounts").upsert(
                account_data, 
                on_conflict="user_id,account_type"
            ).execute()
        except Exception as e:
            # Fallback: try update first, then insert if update fails
            user_id = account_data["user_id"]
            account_type = account_data["account_type"]
            
            try:
                # Try to update existing record
                result = self.supabase.table("accounts").update({
                    "current_balance": account_data["current_balance"],
                    "last_updated": account_data["last_updated"]
                }).eq("user_id", user_id).eq("account_type", account_type).execute()
                
                # If no rows were updated, insert new record
                if not result.data:
                    result = self.supabase.table("accounts").insert(account_data).execute()
                
                return result
                
            except Exception as fallback_error:
                print(f"Account upsert fallback failed: {fallback_error}")
                raise fallback_error


    def update_account_balance(self, user_id, account_type, amount_change, transaction_type, description, reference_id=None):
        """Update account balance and log transaction with better error handling"""
        from datetime import datetime
        
        try:
            # Get current balance
            account_data = self.get_account_by_type(user_id, account_type)
            current_balance = 0
            
            if account_data.data:
                current_balance = float(account_data.data[0].get("current_balance", 0))
            
            # Calculate new balance
            new_balance = current_balance + amount_change  # Negative amount_change for expenses
            
            # Update account with safer upsert
            account_update = {
                "user_id": user_id,
                "account_type": account_type,
                "current_balance": new_balance,
                "last_updated": datetime.now().isoformat()
            }
            
            # Use the improved upsert method
            result = self.upsert_account(account_update)
            
            # Log transaction
            transaction_data = {
                "user_id": user_id,
                "account_type": account_type,
                "transaction_type": transaction_type,
                "amount": amount_change,
                "description": description,
                "reference_id": reference_id
            }
            
            self.insert_account_transaction(transaction_data)
            
            return result, new_balance
            
        except Exception as e:
            print(f"Update account balance error: {e}")
            raise e
    
    def get_account_by_type(self, user_id, account_type):
        """Get specific account by type"""
        return self.supabase.table("accounts").select("*").eq("user_id", user_id).eq("account_type", account_type).execute()

    def get_allocation_settings(self, user_id):
        """Get user's allocation percentages"""
        return self.supabase.table("allocation_settings").select("*").eq("user_id", user_id).execute()

    def upsert_allocation_setting(self, allocation_data):
        """Insert or update allocation setting"""
        return self.supabase.table("allocation_settings").upsert(allocation_data).execute()

    def insert_account_transaction(self, transaction_data):
        """Insert account transaction log"""
        return self.supabase.table("account_transactions").insert(transaction_data).execute()

    def get_account_transactions(self, user_id, account_type=None, limit=50):
        """Get account transaction history"""
        query = self.supabase.table("account_transactions").select("*").eq("user_id", user_id)
        if account_type:
            query = query.eq("account_type", account_type)
        return query.order("created_at", desc=True).limit(limit).execute()

    def get_monthly_closure(self, user_id, year, month):
        """Check if month is already closed"""
        return self.supabase.table("monthly_closures").select("*").eq("user_id", user_id).eq("year", year)

    def update_account_balance(self, user_id, account_type, amount_change, transaction_type, description, reference_id=None):
        """Update account balance and log transaction"""
        from datetime import datetime
        
        # Get current balance
        account_data = self.get_account_by_type(user_id, account_type)
        current_balance = 0
        
        if account_data.data:
            current_balance = float(account_data.data[0].get("current_balance", 0))
        
        # Calculate new balance
        new_balance = current_balance + amount_change  # Negative amount_change for expenses
        
        # Update account
        account_update = {
            "user_id": user_id,
            "account_type": account_type,
            "current_balance": new_balance,
            "last_updated": datetime.now().isoformat()
        }
        
        result = self.upsert_account(account_update)
        
        # Log transaction
        transaction_data = {
            "user_id": user_id,
            "account_type": account_type,
            "transaction_type": transaction_type,
            "amount": amount_change,
            "description": description,
            "reference_id": reference_id
        }
        
        self.insert_account_transaction(transaction_data)
        
        return result, new_balance

    def get_account_balance(self, user_id, account_type):
        """Get current balance for specific account"""
        account_data = self.get_account_by_type(user_id, account_type)
        if account_data.data:
            return float(account_data.data[0].get("current_balance", 0))
        return 0

# Global database instance
db = DatabaseManager()