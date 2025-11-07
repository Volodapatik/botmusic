import os
import telebot
import yt_dlp
import re
import subprocess
from flask import Flask

# ТОКЕН ТІЛЬКИ З ЗМІННИХ ОТОЧЕННЯ
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    print("❌ ПОМИЛКА: TELEGRAM_BOT_TOKEN не встановлено!")
    exit(1)

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "🎵 YouTube Music Bot is running!"

def extract_url(text):
    match = re.search(r'youtu\.be/([^\s&]+)|youtube\.com/watch\?v=([^\s&]+)', text)
    return f"https://youtu.be/{match.group(1) or match.group(2)}" if match else None

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "🎵 Бот запущен! Отправь ссылку YouTube")

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    url = extract_url(message.text)
    if not url:
        bot.reply_to(message, "❌ Неверная ссылка")
        return
    
    try:
        chat_id = message.chat.id
        bot.send_message(chat_id, f"🎵 Обрабатываю: {url}")
        
        ydl_opts = {
            'format': 'worst[height<=360]',
            'outtmpl': 'video.%(ext)s',
        }
        
        bot.send_message(chat_id, "⬇️ Скачиваю видео...")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Перевіряємо скачане відео
        video_file = None
        for file in os.listdir('.'):
            if file.startswith('video.'):
                video_file = file
                break
        
        if not video_file:
            bot.reply_to(message, "❌ YouTube временно блокирует запрос. Попробуйте позже или другую ссылку.")
            return
        
        bot.send_message(chat_id, "🎵 Конвертирую в MP3...")
        
        # Конвертація
        mp3_file = 'audio.mp3'
        subprocess.run([
            'ffmpeg', '-i', video_file, 
            '-vn', '-acodec', 'libmp3lame', '-ab', '192k',
            '-y', mp3_file
        ], check=True, timeout=300)
        
        if os.path.exists(mp3_file):
            file_size = os.path.getsize(mp3_file) / (1024 * 1024)
            
            if file_size > 50:
                bot.send_message(chat_id, f"❌ Файл слишком большой ({file_size:.1f} МБ)")
            else:
                bot.send_message(chat_id, f"📤 Отправляю ({file_size:.1f} МБ)...")
                with open(mp3_file, 'rb') as f:
                    bot.send_audio(chat_id, f, timeout=300)
                bot.send_message(chat_id, "✅ Готово!")
        else:
            bot.reply_to(message, "❌ Не удалось конвертировать в MP3")
            
    except Exception as e:
        error_msg = str(e)
        if "bot" in error_msg.lower() or "cookies" in error_msg.lower():
            bot.reply_to(message, "❌ YouTube временно блокирует запрос. Попробуйте другую ссылку или повторите позже.")
        else:
            bot.reply_to(message, f"❌ Ошибка: {error_msg}")
    
    finally:
        # Очистка
        for file in ['video.mp4', 'video.webm', 'audio.mp3']:
            try:
                if os.path.exists(file):
                    os.remove(file)
            except:
                pass

if __name__ == "__main__":
    print("🚀 Бот запущен с улучшенным обходом блокировки!")
    
    from threading import Thread
    
    def run_bot():
        bot.infinity_polling()
    
    bot_thread = Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
