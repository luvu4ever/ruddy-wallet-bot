import json
import logging
import google.generativeai as genai
from config import GEMINI_API_KEY, EXPENSE_CATEGORIES

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

def parse_message_with_gemini(text: str, user_id: int) -> dict:
    """Enhanced Gemini parsing for Vietnamese/English messages with explicit category support"""
    
    categories_str = ", ".join(EXPENSE_CATEGORIES)
    
    prompt = f"""
Parse this Vietnamese/English message and identify expenses only.

Message: "{text}"

Available categories: {categories_str}

ENHANCED RULES:
1. EXPLICIT CATEGORY IN PARENTHESES - HIGHEST PRIORITY:
   - If text contains (category_name) at the end, USE THAT CATEGORY EXACTLY
   - Examples: "50k đồng hồ (mama)" → category: "mama"
   - Examples: "100k cà phê (ăn uống)" → category: "ăn uống"
   - Examples: "200k áo (cá nhân)" → category: "cá nhân"
   - IGNORE automatic categorization if explicit category is provided

2. AUTOMATIC CATEGORIZATION (only if no explicit category):
   - "ăn uống" for food/drinks (bún, phở, cơm, cà phê)
   - "mèo" for cat items (cát mèo, thức ăn mèo)
   - "mama" for anything related to mama (both furniture and things that involve mama)              
   - "linh tinh" for small items (đèn nhỏ, ly, dao)
   - "cá nhân" for clothes/entertainment (áo, phim, game)
   - "di chuyển" for transport (xăng, taxi, grab)
   - "hóa đơn" for bills (điện, nước, internet)
   - "khác" for other things

3. CURRENCY CONVERSION:
   - k = thousand (50k = 50000)
   - m = million (1.5m = 1500000)  
   - tr = million (3tr = 3000000)

4. DESCRIPTION CLEANING:
   - Remove the (category) part from description
   - Example: "đồng hồ (mama)" → description: "đồng hồ"

Return ONLY JSON:
{{
    "type": "expenses",
    "expenses": [
        {{"amount": 50000, "description": "đồng hồ", "category": "mama"}}
    ]
}}

If not expense, return: {{"type": "unknown", "expenses": []}}
"""

    try:
        response = gemini_model.generate_content(prompt)
        result_text = response.text.strip()
        
        # Clean markdown formatting
        if result_text.startswith('```json'):
            result_text = result_text.replace('```json', '').replace('```', '').strip()
        
        result = json.loads(result_text)
        
        # Validate categories in the result
        if result.get("type") == "expenses" and result.get("expenses"):
            for expense in result["expenses"]:
                category = expense.get("category", "").lower()
                # Ensure the category exists in our available categories
                if category not in [cat.lower() for cat in EXPENSE_CATEGORIES]:
                    expense["category"] = "khác"  # Default fallback
        
        return result
        
    except Exception as e:
        logging.error(f"Gemini parsing error: {e}")
        return {"type": "unknown", "expenses": []}

def generate_monthly_summary(expense_data, income_data, month, year):
    """Simple monthly summary generation"""
    summary_prompt = f"""
Create a short financial summary in Vietnamese for:
- Expenses: {json.dumps(expense_data, default=str)}
- Income: {json.dumps(income_data, default=str)}
- Month: {month}/{year}

Include:
- Total income and expenses in VND
- Net savings (income - expenses)
- Top spending categories
- Simple advice

Keep it short and friendly with emojis.
"""
    
    try:
        response = gemini_model.generate_content(summary_prompt)
        return response.text
    except Exception as e:
        logging.error(f"Summary generation error: {e}")
        return None