import asyncio
import httpx
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ==========================
# Global variables
# ==========================
# Async HTTP Client để quản lý session và cookies
http_client = None
task = None
stop_flag = False
BASE_URL = "https://nullzereptool.com"

# ==========================
# Utility Functions
# ==========================

# Hàm này sẽ khởi tạo httpx.AsyncClient để quản lý cookies (session)
async def init_client():
    global http_client
    if http_client is not None:
        await http_client.aclose()
    
    # Sử dụng headers chuẩn để giả lập trình duyệt
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": BASE_URL + "/",
        "Origin": BASE_URL,
        "X-Requested-With": "XMLHttpRequest" # Thường dùng cho các request AJAX
    }
    # Khởi tạo client, tự động quản lý cookies
    http_client = httpx.AsyncClient(base_url=BASE_URL, headers=headers)


# ==========================
# /login (API Call)
# ==========================
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global http_client
    
    if len(context.args) == 0:
        await update.message.reply_text("Nhập code dạng: /login CODE")
        return

    code = context.args[0]
    await update.message.reply_text(f"🔑 Đang login bằng API với code: {code} ...")
    
    try:
        # 1. Khởi tạo Client mới
        await init_client()

        # 2. Gửi request POST Login
        data = {
            "mode": "login",
            "code": code
        }
        
        # Gửi POST request đến /packet
        response = await http_client.post("/packet", data=data)
        
        # Kiểm tra trạng thái response
        response.raise_for_status()
        
        # Phản hồi của API này thường là HTML (hoặc JSON lỗi)
        # Nếu login thành công, Cookies session sẽ được lưu tự động trong http_client
        
        response_text = response.text.strip()

        # Nếu login thành công, server sẽ phản hồi bằng HTML của trang dashboard
        if "Logged in successfully" in response_text or "User Information" in response_text:
            # Gửi thêm một request 'stats' để kiểm tra xem session có hoạt động không
            info = await get_stats_data()
            if "User_Name" in info:
                await update.message.reply_text(
                    f"✅ Login API thành công.\n"
                    f"👤 User: {info['User_Name']}\n"
                    f"Dùng /stats để tự động claim."
                )
            else:
                 await update.message.reply_text("✅ Login API thành công. Không thể đọc được thông tin user.")
        elif "Invalid Code" in response_text:
            await update.message.reply_text("❌ Login thất bại: Code không hợp lệ.")
        else:
            await update.message.reply_text(f"❌ Login thất bại. Phản hồi không mong muốn:\n{response_text[:100]}...")

    except httpx.HTTPStatusError as e:
        await update.message.reply_text(f"❌ Lỗi HTTP: {e.response.status_code}")
    except httpx.RequestError as e:
        await update.message.reply_text(f"❌ Lỗi kết nối mạng: {e}")
    except Exception as e:
        await update.message.reply_text(f"❌ Đã xảy ra lỗi không xác định: {e}")


# ==========================
# Auto claim loop (API Call)
# ==========================
async def auto_claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stop_flag, http_client # Đặt khai báo global ở đầu hàm

    if http_client is None:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Client chưa được khởi tạo. Dùng /login CODE trước."
        )
        return

    while not stop_flag:
        try:
            # 1. Claim Gold
            data_gold = {"mode": "claim_gold"}
            response_gold = await http_client.post("/packet", data=data_gold)
            response_gold.raise_for_status()
            
            # 2. Claim XP
            data_xp = {"mode": "claim_xp"}
            response_xp = await http_client.post("/packet", data=data_xp)
            response_xp.raise_for_status()
            
            # Gửi thông báo thành công
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="💰 Claim thành công (Gold & XP) bằng API!"
            )
            
            # Chờ 5 giây trước khi check lại/chu kỳ claim tiếp theo
            await asyncio.sleep(5) 
            
            # Sau khi claim, check stats và gửi thông báo
            info = await get_stats_data()
            if "Gems" in info:
                 await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"🔄 Stats mới:\n"
                         f"• Gems: {info.get('Gems', '?')}\n"
                         f"• Gold: {info.get('Gold', '?')}\n"
                         f"• XP: {info.get('XP', '?')}"
                )
            
            # Đợi 1 giờ (3600 giây) trước lần claim tiếp theo
            if not stop_flag:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="⏳ Đã claim xong. Đang đợi 60 phút cho lần claim tiếp theo..."
                )
                await asyncio.sleep(3600) # Đợi 1 giờ

        except httpx.HTTPStatusError as e:
            msg = f"❌ Lỗi HTTP khi Claim: {e.response.status_code}. Có thể session đã hết hạn."
            await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            # Dừng vòng lặp nếu lỗi nghiêm trọng
            stop_flag = True 
        except httpx.RequestError as e:
            msg = f"❌ Lỗi kết nối mạng khi Claim: {e}"
            await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            await asyncio.sleep(60) # Đợi 1 phút rồi thử lại

        except Exception as e:
            msg = f"⚠️ Lỗi claim không xác định: {e}. Đang đợi 10 giây rồi thử lại..."
            await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            await asyncio.sleep(10)

# ==========================
# /stats bắt đầu claim
# ==========================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global task, stop_flag # Đặt khai báo global ở đầu hàm

    if http_client is None:
        await update.message.reply_text("❌ Chưa login. Dùng /login CODE trước.")
        return

    # Lấy thông tin lần đầu trước khi bắt đầu loop
    await check(update, context)

    if task is not None and not task.done():
        await update.message.reply_text("⚠️ Auto claim đang chạy.")
        return

    await update.message.reply_text("▶️ Bắt đầu auto claim API (chu kỳ 60 phút)...")

    stop_flag = False
    task = asyncio.create_task(auto_claim(update, context))

# ==========================
# /stop
# ==========================
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stop_flag, task # Đặt khai báo global ở đầu hàm

    stop_flag = True
    if task:
        task.cancel() # Hủy task hiện tại nếu đang chạy
        task = None

    await update.message.reply_text("🛑 Đã dừng auto claim.")

# ==========================
# /out
# ==========================
async def out(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global http_client, stop_flag, task # Đặt khai báo global ở đầu hàm

    # Dừng auto claim
    stop_flag = True
    if task:
        task.cancel()
        task = None

    # Đóng client
    if http_client:
        await http_client.aclose()
        http_client = None

    await update.message.reply_text("🚪 Đã đóng session API.")

# ==========================
# /check — Lấy info user (API Call)
# ==========================
async def get_stats_data():
    """Gửi request API để lấy thông tin user và parse kết quả."""
    global http_client

    if http_client is None:
        return {}
    
    try:
        data_stats = {"mode": "stats"}
        response = await http_client.post("/packet", data=data_stats)
        response.raise_for_status()
        
        html_content = response.text
        data = {}
        
        # Sử dụng Regex để tìm các giá trị (tương tự như cách Selenium đọc HTML)
        # Các key có thể là: User_Name, Gems, Level, Gold, Food, XP, Account Status, Reason, Premium Expired At
        
        # Regex mẫu để bắt cặp key: value trong HTML trả về
        pattern = re.compile(r'<div[^>]*>\s*(.*?):\s*<span[^>]*>(.*?)<\/span>\s*<\/div>', re.DOTALL)
        matches = pattern.findall(html_content)
        
        for key, value in matches:
            key = key.strip().replace(" ", "_") # Chuyển thành dạng key dễ sử dụng
            data[key] = value.strip()
            
        return data

    except Exception as e:
        print(f"Lỗi khi lấy stats qua API: {e}")
        return {}


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global http_client

    if http_client is None:
        await update.message.reply_text("❌ Chưa login.")
        return

    await update.message.reply_text("🔄 Đang lấy thông tin user bằng API...")
    
    data = await get_stats_data()

    if not data:
        await update.message.reply_text("❌ Không thể đọc dữ liệu user. Có thể session đã hết hạn.")
        return

    msg = (
        f"👤 **User Info (API):**\n"
        f"• Name: {data.get('User_Name', '?')}\n"
        f"• Gems: {data.get('Gems', '?')}\n"
        f"• Level: {data.get('Level', '?')}\n"
        f"• Gold: {data.get('Gold', '?')}\n"
        f"• Food: {data.get('Food', '?')}\n"
        f"• XP: {data.get('XP', '?')}\n"
        f"• Status: {data.get('Account_Status', '?')}\n"
        f"• Reason: {data.get('Reason', '?')}\n"
        f"• Premium: {data.get('Premium_Expired_At', '?')}\n"
    )

    await update.message.reply_text(msg, parse_mode="Markdown")

# ==========================
# Run bot
# ==========================
async def main():
    # Thay thế TOKEN bằng token Telegram Bot của bạn
    TOKEN = "8029102657:AAF536W2Fh0ihZdCIC92dDAAWHqpwqPrVXo" 
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("out", out))
    app.add_handler(CommandHandler("check", check))

    await app.run_polling()

if __name__ == '__main__':
    # Chạy hàm main trong môi trường asyncio
    # Thay thế asyncio.run(main()) bằng logic an toàn hơn để tránh lỗi "This event loop is already running"
    try:
        asyncio.run(main())
    except RuntimeError as e:
        # Nếu lỗi là do vòng lặp đã chạy (ví dụ: trong môi trường tương tác), 
        # hãy kiểm tra xem có vòng lặp nào đang chạy không
        if "already running" in str(e):
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_running():
                    # Nếu có loop nhưng chưa chạy, chúng ta chạy nó
                    loop.run_until_complete(main())
                else:
                    # Nếu loop đang chạy (ví dụ: trong một môi trường như Jupyter), 
                    # chúng ta tạo task và chờ nó kết thúc
                    task = loop.create_task(main())
                    # In ra thông báo để user biết rằng bot đã được khởi động
                    print("Bot started in an existing asyncio loop as a task.")
            except Exception as loop_e:
                print(f"Error handling existing loop: {loop_e}")
                raise e
        else:
            raise e