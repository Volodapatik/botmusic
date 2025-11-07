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
        
        # ... решта коду без змін ...
