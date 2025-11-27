import asyncio
import requests
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = "8029102657:AAF536W2Fh0ihZdCIC92dDAAWHqpwqPrVXo"

LOGIN_URL = "https://nullzereptool.com/login"
CLAIM_URL = "https://nullzereptool.com/packet"
DASHBOARD_URL = "https://nullzereptool.com/"
# Global session info
session_cookies = {}
login_code = None
claim_task = None
stop_flag = False

# Header chung cho cả login và claim
HEADERS = {
    "accept": "*/*",
    "accept-language": "vi,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
    "origin": "https://nullzereptool.com",
    "referer": "https://nullzereptool.com/",
    "sec-ch-ua": '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0",
}

# Default cookie template
DEFAULT_COOKIES = {
    "_ga": "GA1.1.1116835132.1763643652",
    "_ga_9VN68P741L": "GS2.1.s1763643651$o1$g0$t1763643676$j35$l0$h0",
    "ban_reason": "Your account is currently safe",
    "xp": "2152000314",
    "PHPSESSID": "d08be5982482fccb3f0c666624a46221",
}


async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global session_cookies, login_code

    if len(context.args) != 1:
        await update.message.reply_text("❌ Vui lòng gửi /login <code>")
        return

    code = context.args[0]
    login_code = code

    await update.message.reply_text("⏳ Đang gửi request login...")

    files = {
        "code": (None, code),
        "loginType": (None, "user"),
    }

    try:
        response = requests.post(
            LOGIN_URL,
            headers=HEADERS,
            cookies=DEFAULT_COOKIES,
            files=files,
            timeout=20,
        )

        # Lưu cookie trả về
        session_cookies = response.cookies.get_dict()

        text = response.text
        if len(text) > 4000:
            text = "⚠️ Response quá dài."

        await update.message.reply_text(
            f"✅ Login request đã gửi!\nStatus: {response.status_code}\nResponse:\n{text}"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi khi login: {e}")


async def start_claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stop_flag, claim_task

    if not login_code or not session_cookies:
        await update.message.reply_text("❌ Bạn chưa login. Dùng /login <code> trước!")
        return

    if claim_task and not claim_task.done():
        await update.message.reply_text("⚠️ Bot đang chạy claim rồi!")
        return

    await update.message.reply_text("⏳ Bắt đầu auto-claim mỗi 10s...")

    stop_flag = False

    async def claim_loop():
        global stop_flag
        while not stop_flag:
            try:
                data = {"mode": "claim-gold-xp"}
                response = requests.post(
                    CLAIM_URL,
                    headers=HEADERS,
                    cookies=session_cookies,
                    data=data,
                    timeout=20,
                )

                text = response.text
                if len(text) > 2000:
                    text = text[:2000] + "...(cắt ngắn)"

                await update.message.reply_text(f"✅ Claim xong!\n{text}")

            except Exception as e:
                await update.message.reply_text(f"⚠️ Lỗi claim: {e}")
                await asyncio.sleep(7)
                await start_claim(update, context)
                

            await asyncio.sleep(5)  # Delay giữa các lần claim

    claim_task = asyncio.create_task(claim_loop())


async def stop_claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stop_flag
    stop_flag = True
    await update.message.reply_text("⏹️ Dừng auto-claim.")


async def start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot sẵn sàng!\nCommands:\n/start\n/login <code>\n/startclaim\n/stop\n/check\n/out")

async def exit_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stop_flag, app
    stop_flag = True
    await update.message.reply_text("🚪 Bot sẽ thoát...")
    if app:
        await app.stop()
async def check_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not session_cookies:
        await update.message.reply_text("❌ Bạn chưa login. Dùng /login <code> trước!")
        return

    await update.message.reply_text("⏳ Đang lấy thông tin người chơi...")

    try:
        response = requests.get(DASHBOARD_URL, headers=HEADERS, cookies=session_cookies, timeout=20)
        html = response.text

        # Regex: lấy <div>key: <span>value</span></div>
        pattern = r'<div[^>]*>\s*([^:<>]+):\s*<span[^>]*>(.*?)</span>'
        matches = re.findall(pattern, html, re.DOTALL)
        player_info = {k.strip(): v.strip() for k, v in matches}

        if player_info:
            msg = "\n".join([f"{k}: {v}" for k, v in player_info.items()])
            await update.message.reply_text(f"📄 Thông tin người chơi:\n{msg}")
        else:
            await update.message.reply_text("❌ Không lấy được thông tin người chơi!")

    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi khi check info: {e}")        
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_bot))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("starts", start_claim))  # dùng /startclaim để bắt đầu
    app.add_handler(CommandHandler("check", check_info))
    app.add_handler(CommandHandler("stop", stop_claim))
    app.add_handler(CommandHandler("out", exit_bot))
    
    app.run_polling()


if __name__ == "__main__":
    main()
