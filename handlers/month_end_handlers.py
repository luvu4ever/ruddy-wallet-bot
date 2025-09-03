from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, date
import logging

from database import db
from utils import (
    check_authorization, send_formatted_message, format_currency,
    get_current_month, get_month_date_range, get_month_display
)
from config import ACCOUNT_DESCRIPTIONS

async def endmonth_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    
    current_month, current_year = get_current_month()
    
    existing_closure = db.check_monthly_closure(user_id, current_year, current_month)
    if existing_closure.data:
        closure_date = existing_closure.data[0]["created_at"][:10]
        date_range = get_month_display(current_year, current_month)
        await send_formatted_message(update, 
            f"⛔ *THÁNG {current_month}/{current_year} ĐÃ ĐÓNG!*\n\n"
            f"📅 *Khoảng thời gian*: {date_range}\n"
            f"📅 *Ngày đóng*: {closure_date}\n"
            f"💡 *Xem lịch sử*: `/monthhistory`")
        return
    
    accounts_data = db.get_accounts(user_id)
    if not accounts_data.data:
        await send_formatted_message(update, "⛔ Không tìm thấy tài khoản. Vui lòng thử lại.")
        return
    
    accounts_dict = {acc["account_type"]: acc for acc in accounts_data.data}
    
    need_balance = float(accounts_dict.get("need", {}).get("current_balance", 0))
    fun_balance = float(accounts_dict.get("fun", {}).get("current_balance", 0))
    saving_balance = float(accounts_dict.get("saving", {}).get("current_balance", 0))
    invest_balance = float(accounts_dict.get("invest", {}).get("current_balance", 0))
    mama_balance = float(accounts_dict.get("mama", {}).get("current_balance", 0))
    
    excess_need = max(0, need_balance)
    excess_fun = max(0, fun_balance)
    total_transfer = excess_need + excess_fun
    new_saving_balance = saving_balance + total_transfer
    
    month_start, month_end = get_month_date_range(current_year, current_month)
    monthly_expenses = db.get_monthly_expenses(user_id, month_start)
    monthly_income = db.get_monthly_income(user_id, month_start)
    
    total_expenses = sum(float(exp["amount"]) for exp in monthly_expenses.data) if monthly_expenses.data else 0
    total_income = sum(float(inc["amount"]) for inc in monthly_income.data) if monthly_income.data else 0
    net_savings = total_income - total_expenses
    
    date_range = get_month_display(current_year, current_month)
    
    summary_message = f"""📊 *TỔNG KẾT THÁNG {current_month}/{current_year}*
📅 *({date_range})*

💰 *THU CHI THÁNG:*
💵 Thu nhập: `{format_currency(total_income)}`
💸 Chi tiêu: `{format_currency(total_expenses)}`
📈 Tiết kiệm ròng: `{format_currency(net_savings)}`

💳 *TÀI KHOẢN HIỆN TẠI:*
🏠 Thiết yếu: `{format_currency(need_balance)}`
🎮 Giải trí: `{format_currency(fun_balance)}`
💰 Tiết kiệm: `{format_currency(saving_balance)}`
📈 Đầu tư: `{format_currency(invest_balance)}`
✅ Mama: `{format_currency(mama_balance)}`

🔄 *SẼ THỰC HIỆN:*
• Chuyển số dư Thiết yếu → Tiết kiệm: `{format_currency(excess_need)}`
• Chuyển số dư Giải trí → Tiết kiệm: `{format_currency(excess_fun)}`
• Đặt lại Thiết yếu và Giải trí về 0₫
• Tiết kiệm mới: `{format_currency(new_saving_balance)}`

⚠️ *CẢNH BÁO: Không thể hoàn tác!*

💡 *Xác nhận đóng tháng*: Trả lời `CONFIRM` để xác nhận"""
    
    await send_formatted_message(update, summary_message)
    
    context.user_data['pending_month_end'] = {
        'month': current_month,
        'year': current_year,
        'need_balance': need_balance,
        'fun_balance': fun_balance,
        'saving_balance': saving_balance,
        'invest_balance': invest_balance,
        'mama_balance': mama_balance,
        'total_transfer': total_transfer,
        'total_expenses': total_expenses,
        'total_income': total_income,
        'net_savings': net_savings
    }

async def handle_month_end_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
    if not await check_authorization(update):
        return False
    
    user_id = update.effective_user.id
    
    pending_data = context.user_data.get('pending_month_end')
    if not pending_data:
        return False
    
    if message_text.upper().strip() == "CONFIRM":
        pass
    else:
        context.user_data.pop('pending_month_end', None)
        await send_formatted_message(update, 
            "⛔ *ĐÃ HỦY ĐÓNG THÁNG*\n\n"
            "💡 Dùng `/endmonth` khi bạn sẵn sàng đóng tháng")
        return True
    
    try:
        result = await _execute_month_end_processing(user_id, pending_data)
        
        if result['success']:
            context.user_data.pop('pending_month_end', None)
            await send_formatted_message(update, result['message'])
        else:
            await send_formatted_message(update, f"⛔ Lỗi khi đóng tháng: {result['error']}")
        
        return True
        
    except Exception as e:
        logging.error(f"Month-end processing error: {e}")
        await send_formatted_message(update, "⛔ Lỗi hệ thống khi đóng tháng. Vui lòng thử lại.")
        return True

async def _execute_month_end_processing(user_id: int, pending_data: dict):
    try:
        month = pending_data['month']
        year = pending_data['year']
        need_balance = pending_data['need_balance']
        fun_balance = pending_data['fun_balance']
        saving_balance = pending_data['saving_balance']
        invest_balance = pending_data['invest_balance']
        mama_balance = pending_data['mama_balance']
        
        user_id_str = str(user_id)
        
        logging.info(f"Processing month-end for user {user_id_str}, month {month}/{year}")
        
        balance_history_data = {
            "user_id": user_id_str,
            "year": int(year),
            "month": int(month),
            "need_balance": float(need_balance),
            "fun_balance": float(fun_balance),
            "saving_balance": float(saving_balance),
            "invest_balance": float(invest_balance),
            "mama_balance": float(mama_balance)
        }
        
        db.supabase.table("account_balance_history").insert(balance_history_data).execute()
        logging.info(f"Saved balance history for {month}/{year}")
        
        transfer_from_need = max(0, need_balance)
        transfer_from_fun = max(0, fun_balance)
        total_transfer = transfer_from_need + transfer_from_fun
        
        closure_data = {
            "user_id": user_id_str,
            "year": int(year),
            "month": int(month),
            "total_income": float(pending_data['total_income']),
            "total_expenses": float(pending_data['total_expenses']),
            "net_savings": float(pending_data['net_savings']),
            "need_balance_before": float(need_balance),
            "fun_balance_before": float(fun_balance),
            "saving_balance_before": float(saving_balance),
            "invest_balance_before": float(invest_balance),
            "mama_balance_before": float(mama_balance),
            "transferred_to_savings": float(total_transfer)
        }
        
        closure_result = db.insert_monthly_closure(closure_data)
        closure_id = closure_result.data[0]["id"] if closure_result.data else None
        logging.info(f"Created monthly closure with ID: {closure_id}")
        
        if need_balance != 0:
            db.update_account_balance(
                user_id, "need", -need_balance, "month_end_reset",
                f"Month-end reset: {format_currency(need_balance)} → 0đ", closure_id
            )
            logging.info(f"Reset need account: {need_balance} → 0")
        
        if fun_balance != 0:
            db.update_account_balance(
                user_id, "fun", -fun_balance, "month_end_reset",
                f"Month-end reset: {format_currency(fun_balance)} → 0đ", closure_id
            )
            logging.info(f"Reset fun account: {fun_balance} → 0")
        
        if total_transfer > 0:
            db.update_account_balance(
                user_id, "saving", total_transfer, "month_end_transfer",
                f"Month-end transfer: {format_currency(total_transfer)} from need+fun", closure_id
            )
            logging.info(f"Transferred {total_transfer} to savings")
        
        final_need_balance = 0
        final_fun_balance = 0
        final_saving_balance = db.get_account_balance(user_id, "saving")
        final_invest_balance = db.get_account_balance(user_id, "invest")
        final_mama_balance = db.get_account_balance(user_id, "mama")
        
        date_range = get_month_display(year, month)
        
        actions_performed = []
        
        if need_balance > 0:
            actions_performed.append(f"• Chuyển từ Thiết yếu: `{format_currency(need_balance)}` → Tiết kiệm")
        elif need_balance < 0:
            actions_performed.append(f"• Reset Thiết yếu: `{format_currency(need_balance)}` → `0đ` (số âm)")
        else:
            actions_performed.append(f"• Thiết yếu: `0đ` → `0đ` (không đổi)")
        
        if fun_balance > 0:
            actions_performed.append(f"• Chuyển từ Giải trí: `{format_currency(fun_balance)}` → Tiết kiệm")
        elif fun_balance < 0:
            actions_performed.append(f"• Reset Giải trí: `{format_currency(fun_balance)}` → `0đ` (số âm)")
        else:
            actions_performed.append(f"• Giải trí: `0đ` → `0đ` (không đổi)")
        
        actions_performed.append(f"• Lưu lịch sử số dư tháng {month}/{year}")
        
        success_message = f"""✅ **ĐÃ ĐÓNG THÁNG {month}/{year} THÀNH CÔNG!**
📅 **({date_range})**

🔄 **CÁC THAO TÁC ĐÃ THỰC HIỆN:**
{chr(10).join(actions_performed)}

💳 **TÀI KHOẢN SAU KHI ĐÓNG:**
🏠 Thiết yếu: `{format_currency(final_need_balance)}`
🎮 Giải trí: `{format_currency(final_fun_balance)}`
💰 Tiết kiệm: `{format_currency(final_saving_balance)}`
📈 Đầu tư: `{format_currency(final_invest_balance)}`
✅ Mama: `{format_currency(final_mama_balance)}`

📊 **TỔNG KẾT THÁNG:**
💵 Thu nhập: `{format_currency(pending_data['total_income'])}`
💸 Chi tiêu: `{format_currency(pending_data['total_expenses'])}`
📈 Tiết kiệm ròng: `{format_currency(pending_data['net_savings'])}`"""
        
        if total_transfer > 0:
            success_message += f"\n💰 Chuyển vào tiết kiệm: `{format_currency(total_transfer)}`"
        
        success_message += f"""\n💾 Đã lưu lịch sử số dư tháng {month}/{year}

🎉 **Tháng mới bắt đầu! Chúc bạn quản lý tài chính tốt!**

💡 **Xem lịch sử:** `/monthhistory` | `/balancehistory`"""
        
        return {'success': True, 'message': success_message}
        
    except Exception as e:
        logging.error(f"Month-end execution error: {e}")
        return {'success': False, 'error': str(e)}

async def balancehistory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    
    history_data = db.supabase.table("account_balance_history").select("*").eq("user_id", user_id_str).order("year", desc=True).order("month", desc=True).limit(6).execute()
    
    if not history_data.data:
        await send_formatted_message(update, 
            "📊 **CHƯA CÓ LỊCH SỬ SỐ DƯ**\n\n"
            "💡 Dùng `/endmonth` để đóng tháng và lưu lịch sử")
        return
    
    message = "📊 **LỊCH SỬ SỐ DƯ TÀI KHOẢN**\n\n"
    
    for record in history_data.data:
        month = record["month"]
        year = record["year"]
        date_range = get_month_display(year, month)
        
        need_bal = float(record.get("need_balance", 0))
        fun_bal = float(record.get("fun_balance", 0))
        saving_bal = float(record.get("saving_balance", 0))
        invest_bal = float(record.get("invest_balance", 0))
        mama_bal = float(record.get("mama_balance", 0))
        
        total_bal = need_bal + fun_bal + saving_bal + invest_bal + mama_bal
        
        message += f"📅 **THÁNG {month}/{year}** _{date_range}_\n"
        message += f"🏠 Thiết yếu: `{format_currency(need_bal)}`\n"
        message += f"🎮 Giải trí: `{format_currency(fun_bal)}`\n"
        message += f"💰 Tiết kiệm: `{format_currency(saving_bal)}`\n"
        message += f"📈 Đầu tư: `{format_currency(invest_bal)}`\n"
        message += f"✅ Mama: `{format_currency(mama_bal)}`\n"
        message += f"💎 **Tổng tài sản:** `{format_currency(total_bal)}`\n\n"
    
    message += "💡 _Chỉ hiển thị 6 tháng gần nhất_"
    
    await send_formatted_message(update, message)

async def monthhistory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_authorization(update):
        return
    
    user_id = update.effective_user.id
    
    closures_data = db.get_monthly_closures_history(user_id, limit=6)
    
    if not closures_data.data:
        await send_formatted_message(update, 
            "📅 *CHƯA CÓ LỊCH SỬ ĐÓNG THÁNG*\n\n"
            "💡 Dùng `/endmonth` để đóng tháng hiện tại")
        return
    
    message = "📅 *LỊCH SỬ TIẾT KIỆM THÁNG*\n\n"
    
    for closure in closures_data.data:
        month = closure["month"]
        year = closure["year"]
        created_date = closure["created_at"][:10]
        
        total_income = float(closure["total_income"])
        total_expenses = float(closure["total_expenses"])
        net_savings = float(closure["net_savings"])
        transferred = float(closure.get("transferred_to_savings", 0))
        
        saving_before = float(closure.get("saving_balance_before", 0))
        saving_after = saving_before + transferred
        
        date_range = get_month_display(year, month)
        
        message += f"📊 *THÁNG {month}/{year}* _(đóng {created_date})_\n"
        message += f"📅 _{date_range}_\n"
        message += f"💵 Thu: `{format_currency(total_income)}` | Chi: `{format_currency(total_expenses)}`\n"
        message += f"📈 Tiết kiệm ròng: `{format_currency(net_savings)}`\n"
        if transferred > 0:
            message += f"💰 Chuyển vào tiết kiệm: `{format_currency(transferred)}`\n"
        message += f"💳 Tiết kiệm cuối tháng: `{format_currency(saving_after)}`\n\n"
    
    message += "💡 _Chỉ hiển thị 6 tháng gần nhất_"
    
    await send_formatted_message(update, message)