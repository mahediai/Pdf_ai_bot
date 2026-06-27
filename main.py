import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import PyPDF2
import requests
import os

# ========= Railway থেকে Auto নিবে =========
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("API_KEY")
BKASH_NUMBER = os.getenv("BKASH_NUMBER")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
PRICE = int(os.getenv("PRICE", 100))
# ==========================================

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
user_payment = {}
user_state = {}

async def send_admin_alert(context: ContextTypes.DEFAULT_TYPE, user, trxid):
    alert_text = f"🔔 নতুন পেমেন্ট মামা!\n👤 নাম: {user.first_name}\n🆔 ID: {user.id}\n💳 TrxID: {trxid}\n💰 Amount: {PRICE} টাকা\nStatus: ✅ Auto-Approved"
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=alert_text)
    except Exception as e:
        print(f"❌ Admin Alert Error: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(f"💰 {PRICE} টাকা পে করুন", callback_data='pay')]]
    await update.message.reply_text(f"😎 ওই মামা, স্বাগতম!\n\nPDF পড়ে উত্তর দিব।\nফি: {PRICE} টাকা", reply_markup=InlineKeyboardMarkup(keyboard))

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data == 'pay':
        user_state[user_id] = "waiting_trxid"
        await query.edit_message_text(f"💸 বিকাশে {PRICE} টাকা সেন্ড মানি কর:\n\nনাম্বার: `{BKASH_NUMBER}`\n\nTrxID পাঠা মামা", parse_mode='Markdown')

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    if user_id == ADMIN_ID and text.startswith("/block"):
        try:
            block_id = int(text.split()[1])
            user_payment.pop(block_id, None)
            await update.message.reply_text(f"🚫 User {block_id} Blocked")
        except:
            await update.message.reply_text("❌ Format: /block 123456789")
            return
    if user_state.get(user_id) == "waiting_trxid":
        if len(text) < 8:
            await update.message.reply_text("❌ ভুল TrxID মামা")
            return
        user_payment[user_id] = True
        user_state[user_id] = "paid"
        await send_admin_alert(context, update.message.from_user, text)
        await update.message.reply_text("✅ পেমেন্ট কনফার্মড! PDF পাঠা")
        return
    if user_id in user_payment and 'pdf_text' in context.user_data:
        await ask_ai(update, context)
    elif user_id not in user_payment:
        await update.message.reply_text(f"❌ আগে {PRICE} টাকা পেমেন্ট কর। /start দে")
    else:
        await update.message.reply_text("❌ আগে PDF ফাইল দে মামা")

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_payment:
        await update.message.reply_text(f"❌ আগে {PRICE} টাকা পেমেন্ট কর। /start দে")
        return
    if update.message.document.mime_type!= 'application/pdf':
        await update.message.reply_text("❌ শুধু PDF দে মামা")
        return
    await update.message.reply_text("📚 PDF পড়তেছি...")
    pdf_file = await update.message.document.get_file()
    pdf_path = await pdf_file.download_to_drive()
    text = ""
    with open(pdf_path, 'rb') as file:
        for page in PyPDF2.PdfReader(file).pages:
            text += page.extract_text() if page.extract_text() else ""
    context.user_data['pdf_text'] = text[:12000]
    await update.message.reply_text("✅ PDF পড়া শেষ! প্রশ্ন কর মামা")

async def ask_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    data = {"messages": [{"role": "system", "content": f"PDF তথ্য: {context.user_data['pdf_text']}"}, {"role": "user", "content": update.message.text}], "model": "llama-3.1-8b-instant", "max_tokens": 1000}
    try:
        answer = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data, timeout=30).json()['choices'][0]['message']['content']
        await update.message.reply_text(f"🎯 উত্তর:\n\n{answer}")
    except Exception as e:
        await update.message.reply_text("❌ AI ঘুমায় গেছে। 2 মিনিট পর চেষ্টা কর")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_pdf))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("🔥 Bot Railway এ চালু!")
    app.run_polling()

if __name__ == '__main__':
    main()
