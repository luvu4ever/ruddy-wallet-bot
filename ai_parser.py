import json
import logging
import google.generativeai as genai
from config import GEMINI_API_KEY, EXPENSE_CATEGORIES, get_ai_categorization_rules

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

def parse_message_with_gemini(text: str, user_id: int) -> dict:
    """Use Gemini to parse Vietnamese/English messages"""
    
    categories_str = ", ".join(EXPENSE_CATEGORIES)
    ai_rules = get_ai_categorization_rules()
    
    prompt = f"""
Parse this Vietnamese/English message and identify its type. Return ONLY valid JSON.

Message: "{text}"

Detect these message types and extract data:

1. EXPENSES: "50k bún bò huế", "700k thịt 200k cà phê", "100k cát mèo", "1.5m sofa", "3tr renovation" or "spent 50k on gas"
2. Note: Income should now be handled by /income command, not through message parsing

Available categories: {categories_str}

IMPORTANT CURRENCY PARSING:
- "k" = thousand (50k = 50000)
- "m" = million (3m = 3000000)
- "tr" = million (3tr = 3000000, triệu in Vietnamese)
- Plain numbers are also VND (50000 = 50000)
- Convert ALL amounts to full VND numbers

Return format:
{{
    "type": "expenses",
    "expenses": [
        {{"amount": 50000, "description": "bún bò huế", "category": "ăn uống"}},
        {{"amount": 100000, "description": "cát mèo", "category": "mèo"}},
        {{"amount": 1500000, "description": "sofa da", "category": "công trình"}}
    ]
}}

CATEGORIZATION RULES:
{ai_rules}
- Convert k/m/tr notation: 50k=50000, 1.5m=1500000, 3tr=3000000, 2.5k=2500
- Extract all amount+item pairs from the message

Return empty arrays/objects for unused fields. Income should use /income command instead.
"""

    try:
        response = gemini_model.generate_content(prompt)
        result_text = response.text.strip()
        
        # Clean up response if it has markdown formatting
        if result_text.startswith('```json'):
            result_text = result_text.replace('```json', '').replace('```', '').strip()
        
        result = json.loads(result_text)
        return result
        
    except Exception as e:
        logging.error(f"Gemini parsing error: {e}")
        return {"type": "unknown", "expenses": [], "income": {}}

def generate_monthly_summary(expense_data, income_data, month, year):
    """Generate monthly summary using Gemini"""
    summary_prompt = f"""
Tạo báo cáo tài chính tháng này bằng tiếng Việt cho dữ liệu:

Chi tiêu tháng này: {json.dumps(expense_data, default=str)}
Thu nhập tháng này: {json.dumps(income_data, default=str)}

Bao gồm:
- Tổng thu nhập tháng này (đồng VND)
- Tổng chi tiêu tháng này (đồng VND) 
- Tiết kiệm ròng (thu nhập - chi tiêu)
- Top 5 danh mục chi tiêu nhiều nhất
- Đặc biệt chú ý danh mục "mèo" và "nội thất" nếu có
- Nhận xét và đề xuất

Viết bằng tiếng Việt, thân thiện và có emoji. Dùng định dạng tiền VND (ví dụ: 1.500.000đ).
"""
    
    try:
        response = gemini_model.generate_content(summary_prompt)
        return response.text
    except Exception as e:
        logging.error(f"Gemini summary generation error: {e}")
        return None