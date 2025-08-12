from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, date
import logging

from database import db
from utils import (
    check_authorization, send_formatted_message, format_currency,
    get_current_salary_month, get_month_date_range, get_salary_month_display  # NEW: salary cycle functions
)
from config import ACCOUNT_DESCRIPTIONS

async def endmonth_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual month-end processing: /endmonth - now uses salary cycle"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    
    # Get current salary month instead of calendar month
    current_salary_month, current_salary_year = get_current_salary_month()
    
    # Check if salary month is already closed
    existing_closure = db.check_monthly_closure(user_id, current_salary_year, current_salary_month)
    if existing_closure.data:
        closure_date = existing_closure.data[0]["created_at"][:10]
        date_range = get_salary_month_display(current_salary_year, current_salary_month)
        await send_formatted_message(update, 
            f"❌ *THÁNG LƯƠNG {current_salary_month}/{current_salary_year} ĐÃ ĐÓNG!*\n\n"
            f"📅 *Khoảng thời gian*: {date_range}\n"
            f"📅 *Ngày đóng*: {closure_date}\n"
            f"💡 *Xem lịch sử*: `/monthhistory`")
        return
    
    # Get current account balances
    accounts_data = db.get_accounts(user_id)
    if not accounts_data.data:
        await send_formatted_message(update, "❌ Không tìm thấy tài khoản. Vui lòng thử lại.")
        return
    
    # Build accounts dict
    accounts_dict = {acc["account_type"]: acc for acc in accounts_data.data}
    
    # Calculate month-end summary
    need_balance = float(accounts_dict.get("need", {}).get("current_balance", 0))
    fun_balance = float(accounts_dict.get("fun", {}).get("current_balance", 0))
    saving_balance = float(accounts_dict.get("saving", {}).get("current_balance", 0))
    invest_balance = float(accounts_dict.get("invest", {}).get("current_balance", 0))
    construction_balance = float(accounts_dict.get("construction", {}).get("current_balance", 0))
    
    # Calculate transfer amounts
    excess_need = max(0, need_balance)  # All remaining need money goes to savings
    excess_fun = max(0, fun_balance)    # All remaining fun money goes to savings
    total_transfer = excess_need + excess_fun
    new_saving_balance = saving_balance + total_transfer
    
    # Get monthly financial summary for salary month
    month_start, month_end = get_month_date_range(current_salary_year, current_salary_month)
    monthly_expenses = db.get_monthly_expenses(user_id, month_start)
    monthly_income = db.get_monthly_income(user_id, month_start)
    
    total_expenses = sum(float(exp["amount"]) for exp in monthly_expenses.data) if monthly_expenses.data else 0
    total_income = sum(float(inc["amount"]) for inc in monthly_income.data) if monthly_income.data else 0
    net_savings = total_income - total_expenses
    
    # Show pre-processing summary and ask for confirmation
    date_range = get_salary_month_display(current_salary_year, current_salary_month)
    
    summary_message = f"""📊 *TỔNG KẾT THÁNG LƯƠNG {current_salary_month}/{current_salary_year}*
📅 *({date_range})*

💰 *THU CHI THÁNG:*
💵 Thu nhập: `{format_currency(total_income)}`
💸 Chi tiêu: `{format_currency(total_expenses)}`
📈 Tiết kiệm ròng: `{format_currency(net_savings)}`

💳 *TÀI KHOẢN HIỆN TẠI:*
🍚 Thiết yếu: `{format_currency(need_balance)}`
🎮 Giải trí: `{format_currency(fun_balance)}`
💰 Tiết kiệm: `{format_currency(saving_balance)}`
📈 Đầu tư: `{format_currency(invest_balance)}`
🏗️ Xây dựng: `{format_currency(construction_balance)}`

🔄 *SẼ THỰC HIỆN:*
• Chuyển số dư Thiết yếu → Tiết kiệm: `{format_currency(excess_need)}`
• Chuyển số dư Giải trí → Tiết kiệm: `{format_currency(excess_fun)}`
• Đặt lại Thiết yếu và Giải trí về 0đ
• Tiết kiệm mới: `{format_currency(new_saving_balance)}`

⚠️ *CẢNH BÁO: Không thể hoàn tác!*

💡 *Xác nhận đóng tháng lương*: Trả lời `CONFIRM` để xác nhận"""
    
    await send_formatted_message(update, summary_message)
    
    # Store pending closure data in context for confirmation
    context.user_data['pending_month_end'] = {
        'month': current_salary_month,
        'year': current_salary_year,
        'need_balance': need_balance,
        'fun_balance': fun_balance,
        'saving_balance': saving_balance,
        'invest_balance': invest_balance,
        'construction_balance': construction_balance,
        'total_transfer': total_transfer,
        'total_expenses': total_expenses,
        'total_income': total_income,
        'net_savings': net_savings
    }

async def handle_month_end_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
    """Handle month-end confirmation when user types 'CONFIRM'"""
    if not await check_authorization(update):
        return False
    
    user_id = update.effective_user.id
    
    # Check if there's a pending month-end
    pending_data = context.user_data.get('pending_month_end')
    if not pending_data:
        return False
    
    # Check if user confirmed
    if message_text.upper().strip() == "CONFIRM":
        # Process confirmation - continue with existing logic
        pass
    else:
        # Any other input cancels the month-end
        context.user_data.pop('pending_month_end', None)
        await send_formatted_message(update, 
            "❌ *ĐÃ HỦY ĐÓNG THÁNG LƯƠNG*\n\n"
            "💡 Dùng `/endmonth` khi bạn sẵn sàng đóng tháng lương")
        return True
    
    try:
        # Execute month-end processing
        result = await _execute_month_end_processing(user_id, pending_data)
        
        if result['success']:
            # Clear pending data
            context.user_data.pop('pending_month_end', None)
            
            # Send success message
            await send_formatted_message(update, result['message'])
        else:
            await send_formatted_message(update, f"❌ Lỗi khi đóng tháng lương: {result['error']}")
        
        return True
        
    except Exception as e:
        logging.error(f"Month-end processing error: {e}")
        await send_formatted_message(update, "❌ Lỗi hệ thống khi đóng tháng lương. Vui lòng thử lại.")
        return True

async def _execute_month_end_processing(user_id: int, pending_data: dict):
    """Execute the actual month-end processing"""
    try:
        month = pending_data['month']
        year = pending_data['year']
        need_balance = pending_data['need_balance']
        fun_balance = pending_data['fun_balance']
        total_transfer = pending_data['total_transfer']
        
        # 1. Create monthly closure record
        closure_data = {
            "user_id": user_id,
            "year": year,
            "month": month,
            "total_income": pending_data['total_income'],
            "total_expenses": pending_data['total_expenses'],
            "net_savings": pending_data['net_savings'],
            "need_balance_before": need_balance,
            "fun_balance_before": fun_balance,
            "saving_balance_before": pending_data['saving_balance'],
            "invest_balance_before": pending_data['invest_balance'],
            "construction_balance_before": pending_data['construction_balance'],
            "transferred_to_savings": total_transfer
        }
        
        closure_result = db.insert_monthly_closure(closure_data)
        closure_id = closure_result.data[0]["id"] if closure_result.data else None
        
        # 2. Transfer money from need/fun to savings (if any)
        if total_transfer > 0:
            # Transfer from need account
            if need_balance > 0:
                db.update_account_balance(
                    user_id, "need", -need_balance, "month_end_transfer",
                    f"Month-end transfer to savings: {format_currency(need_balance)}", closure_id
                )
            
            # Transfer from fun account  
            if fun_balance > 0:
                db.update_account_balance(
                    user_id, "fun", -fun_balance, "month_end_transfer",
                    f"Month-end transfer to savings: {format_currency(fun_balance)}", closure_id
                )
            
            # Add to savings account
            db.update_account_balance(
                user_id, "saving", total_transfer, "month_end_transfer",
                f"Month-end transfer from need+fun: {format_currency(total_transfer)}", closure_id
            )
        
        # 3. Get final balances
        final_saving_balance = db.get_account_balance(user_id, "saving")
        final_invest_balance = db.get_account_balance(user_id, "invest")
        final_construction_balance = db.get_account_balance(user_id, "construction")
        
        # 4. Build success message with salary month info
        date_range = get_salary_month_display(year, month)
        
        success_message = f"""✅ *ĐÃ ĐÓNG THÁNG LƯƠNG {month}/{year} THÀNH CÔNG!*
📅 *({date_range})*

🔄 *CÁC THAO TÁC ĐÃ THỰC HIỆN:*
• Chuyển từ Thiết yếu: `{format_currency(need_balance)}` → Tiết kiệm
• Chuyển từ Giải trí: `{format_currency(fun_balance)}` → Tiết kiệm
• Đặt lại Thiết yếu và Giải trí về `0đ`

💳 *TÀI KHOẢN SAU KHI ĐÓNG:*
🍚 Thiết yếu: `0đ`
🎮 Giải trí: `0đ`
💰 Tiết kiệm: `{format_currency(final_saving_balance)}`
📈 Đầu tư: `{format_currency(final_invest_balance)}`
🏗️ Xây dựng: `{format_currency(final_construction_balance)}`

📊 *TỔNG KẾT THÁNG LƯƠNG:*
💵 Thu nhập: `{format_currency(pending_data['total_income'])}`
💸 Chi tiêu: `{format_currency(pending_data['total_expenses'])}`
📈 Tiết kiệm ròng: `{format_currency(pending_data['net_savings'])}`
💰 Chuyển vào tiết kiệm: `{format_currency(total_transfer)}`

🎉 *Tháng lương mới bắt đầu! Chúc bạn quản lý tài chính tốt!*

💡 *Xem lịch sử*: `/monthhistory`"""
        
        return {'success': True, 'message': success_message}
        
    except Exception as e:
        logging.error(f"Month-end execution error: {e}")
        return {'success': False, 'error': str(e)}

async def monthhistory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View past month closures: /monthhistory - now shows salary months"""
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    
    # Get past 6 month closures
    closures_data = db.get_monthly_closures_history(user_id, limit=6)
    
    if not closures_data.data:
        await send_formatted_message(update, 
            "📅 *CHƯA CÓ LỊCH SỬ ĐÓNG THÁNG LƯƠNG*\n\n"
            "💡 Dùng `/endmonth` để đóng tháng lương hiện tại")
        return
    
    # Build history message
    message = "📅 *LỊCH SỬ TIẾT KIỆM THÁNG LƯƠNG*\n\n"
    
    for closure in closures_data.data:
        month = closure["month"]
        year = closure["year"]
        created_date = closure["created_at"][:10]
        
        total_income = float(closure["total_income"])
        total_expenses = float(closure["total_expenses"])
        net_savings = float(closure["net_savings"])
        transferred = float(closure.get("transferred_to_savings", 0))
        
        # Calculate final saving balance after this closure
        saving_before = float(closure.get("saving_balance_before", 0))
        saving_after = saving_before + transferred
        
        # Get salary month display range
        date_range = get_salary_month_display(year, month)
        
        message += f"📊 *THÁNG LƯƠNG {month}/{year}* _(đóng {created_date})_\n"
        message += f"📅 _{date_range}_\n"
        message += f"💵 Thu: `{format_currency(total_income)}` | Chi: `{format_currency(total_expenses)}`\n"
        message += f"📈 Tiết kiệm ròng: `{format_currency(net_savings)}`\n"
        if transferred > 0:
            message += f"💰 Chuyển vào tiết kiệm: `{format_currency(transferred)}`\n"
        message += f"💳 Tiết kiệm cuối tháng: `{format_currency(saving_after)}`\n\n"
    
    message += "💡 _Chỉ hiển thị 6 tháng lương gần nhất_"
    
    await send_formatted_message(update, message)