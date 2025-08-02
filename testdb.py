from dotenv import load_dotenv
import os
from supabase import create_client

load_dotenv()

try:
    supabase = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_KEY")
    )
    
    # Test connection
    result = supabase.table("users").select("*").limit(1).execute()
    print("✅ Database connection successful!")
    print(f"Data: {result.data}")
    
except Exception as e:
    print(f"❌ Database error: {e}")
    print(f"URL: {os.getenv('SUPABASE_URL')}")
    print(f"Key: {os.getenv('SUPABASE_KEY')[:20]}...")