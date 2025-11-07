import os
import telebot
import yt_dlp
import re
import subprocess
from flask import Flask

# Токен бота
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '7767505553:AAE-doqqnURz2ySunKO5zgKMpwCwya92i70')
bot = telebot.TeleBot(TOKEN)

# Flask для Railway
app = Flask(__name__)

@app.route('/')
def home():
    return "🎵 YouTube Music Bot is running!"

@app.route('/health')
def health():
    return "OK"

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
        
        # Скачиваем ВИДЕО (форматы 91/94)
        ydl_opts = {
            'format': 'worst[height<=360]',
            'outtmpl': 'video.%(ext)s',
        }
        
        bot.send_message(chat_id, "⬇️ Скачиваю видео...")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Проверяем что видео скачалось
        video_file = None
        for file in os.listdir('.'):
            if file.startswith('video.'):
                video_file = file
                break
        
        if not video_file:
            bot.reply_to(message, "❌ Не удалось скачать видео")
            return
        
        bot.send_message(chat_id, "🎵 Конвертирую в MP3...")
        
        # Конвертируем видео в MP3
        mp3_file = 'audio.mp3'
        subprocess.run([
            'ffmpeg', '-i', video_file, 
            '-vn', '-acodec', 'libmp3lame', '-ab', '192k',
            '-y', mp3_file
        ], check=True)
        
        # Отправляем MP3
        if os.path.exists(mp3_file):
            file_size = os.path.getsize(mp3_file) / (1024 * 1024)
            bot.send_message(chat_id, f"📤 Отправляю ({file_size:.1f} МБ)...")
            
            with open(mp3_file, 'rb') as f:
                bot.send_audio(chat_id, f, timeout=300)
            
            bot.send_message(chat_id, "✅ Готово!")
            
            # Удаляем временные файлы
            if os.path.exists(video_file):
                os.remove(video_file)
            if os.path.exists(mp3_file):
                os.remove(mp3_file)
        else:
            bot.reply_to(message, "❌ Не удалось конвертировать в MP3")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}")

if __name__ == "__main__":
    print("🚀 Бот запущен с обходом блокировки YouTube!")
    
    # Запускаем бота в отдельном потоке
    from threading import Thread
    import time
    
    def run_bot():
        bot.infinity_polling()
    
    bot_thread = Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Запускаем Flask для Railway
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
