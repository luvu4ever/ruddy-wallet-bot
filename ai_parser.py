import json
import logging
import google.generativeai as genai
from config import GEMINI_API_KEY, EXPENSE_CATEGORIES

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

def parse_message_with_gemini(text: str, user_id: int) -> dict:
    """Simple Gemini parsing for Vietnamese/English messages"""
    
    categories_str = ", ".join(EXPENSE_CATEGORIES)
    
    prompt = f"""
Parse this Vietnamese/English message and identify expenses only.

Message: "{text}"

Available categories: {categories_str}

SIMPLE RULES:
- "ăn uống" for food/drinks (bún, phở, cơm, cà phê)
- "mèo" for cat items (cát mèo, thức ăn mèo)
- "mama" for anything related to mama (both furniture and things that involve mama)              
- "linh tinh" for small items (đèn nhỏ, ly, dao)
- "cá nhân" for clothes/entertainment (áo, phim, game)
- "di chuyển" for transport (xăng, taxi, grab)
- "hóa đơn" for bills (điện, nước, internet)
- "khác" for other things

CURRENCY CONVERSION:
- k = thousand (50k = 50000)
- m = million (1.5m = 1500000)  
- tr = million (3tr = 3000000)

Return ONLY JSON:
{{
    "type": "expenses",
    "expenses": [
        {{"amount": 50000, "description": "bún bò huế", "category": "ăn uống"}}
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