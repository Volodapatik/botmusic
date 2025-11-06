import re
import os
import logging
import telebot
import yt_dlp
from threading import Thread
from flask import Flask
import time
import requests
import random

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Токен бота из переменных окружения
TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
bot = telebot.TeleBot(TOKEN, parse_mode=None)

# Увеличенные таймауты для длинных треков
import telebot.apihelper
telebot.apihelper.CONNECT_TIMEOUT = 60
telebot.apihelper.READ_TIMEOUT = 600

# Flask для веб-сервера
app = Flask(__name__)

@app.route('/')
def home():
    return "🎵 YouTube Music Bot is running! Send /start to bot in Telegram"

@app.route('/health')
def health():
    return "OK"

@app.route('/ping')
def ping():
    return "pong"

def get_random_user_agent():
    """Возвращает случайный User-Agent для обхода блокировок"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0'
    ]
    return random.choice(user_agents)

def extract_youtube_url(text):
    """Извлекает YouTube URL из текста сообщения"""
    youtube_regex = (
        r'(https?://)?(www\.)?'
        r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
        r'(watch\?v=|embed/|v/|shorts/|.+[?&]v=)?([^&=%\?]{11})'
    )
    match = re.search(youtube_regex, text)
    return f"https://youtu.be/{match.group(6)}" if match else None

def sanitize_filename(filename):
    """Очищает имя файла от недопустимых символов"""
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    if len(filename) > 100:
        filename = filename[:100]
    return filename

def get_working_proxy():
    """Пытается найти рабочий прокси из бесплатных источников"""
    try:
        # Бесплатные прокси источники
        proxy_sources = [
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://www.proxy-list.download/api/v1/get?type=http",
        ]
        
        for source in proxy_sources:
            try:
                response = requests.get(source, timeout=10)
                proxies = response.text.split('\n')
                for proxy in proxies:
                    proxy = proxy.strip()
                    if proxy and ':' in proxy:
                        # Тестируем прокси
                        test_proxy = {'http': f'http://{proxy}', 'https': f'http://{proxy}'}
                        try:
                            test_response = requests.get('https://www.google.com', 
                                                       proxies=test_proxy, timeout=10)
                            if test_response.status_code == 200:
                                logger.info(f"Найден рабочий прокси: {proxy}")
                                return f'http://{proxy}'
                        except:
                            continue
            except:
                continue
    except Exception as e:
        logger.warning(f"Ошибка поиска прокси: {e}")
    
    return None

def download_and_send_audio(chat_id, url):
    mp3_path = None
    temp_files = []

    try:
        bot.send_message(chat_id, f"🎵 Начинаю обработку: {url}")

        # Создаем папку downloads
        os.makedirs("downloads", exist_ok=True)

        # Пытаемся использовать прокси
        proxy_url = get_working_proxy()
        user_agent = get_random_user_agent()

        # Сначала получаем информацию о видео
        ydl_info_opts = {
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Referer': 'https://www.youtube.com/',
            },
            'proxy': proxy_url,
            'socket_timeout': 30,
            'retries': 10,
        }

        with yt_dlp.YoutubeDL(ydl_info_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            duration = info.get('duration', 0)
            title = info.get('title', 'audio')
            sanitized_title = sanitize_filename(title)

        # Выбираем качество в зависимости от длительности
        if duration > 3600:
            quality = '96'
            bot.send_message(chat_id, f"⏱️ Длинный трек ({duration//60} мин). Использую качество 96 kbps...")
        elif duration > 1800:
            quality = '128'
            bot.send_message(chat_id, f"⏱️ Трек на {duration//60} минут. Качество: 128 kbps")
        else:
            quality = '192'

        output_template = f"downloads/{sanitized_title}.%(ext)s"

        # 🔥 ОСНОВНЫЕ НАСТРОЙКИ ДЛЯ ОБХОДА БЛОКИРОВКИ
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': quality,
            }],
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': False,
            
            # КРИТИЧЕСКИ ВАЖНЫЕ НАСТРОЙКИ
            'http_headers': {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Referer': 'https://www.youtube.com/',
            },
            'proxy': proxy_url,
            'extract_flat': False,
            'ignoreerrors': True,
            'no_check_certificate': True,
            'socket_timeout': 30,
            'retries': 10,
            'fragment_retries': 10,
            'extractor_retries': 3,
            'skip_download': False,
        }

        bot.send_message(chat_id, "⬇️ Загружаю аудио...")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # Ищем созданный MP3 файл
            expected_mp3 = f"downloads/{sanitized_title}.mp3"
            if os.path.exists(expected_mp3):
                mp3_path = expected_mp3
                temp_files.append(mp3_path)
            else:
                for file in os.listdir("downloads"):
                    if file.startswith(sanitized_title) and file.endswith('.mp3'):
                        mp3_path = os.path.join("downloads", file)
                        temp_files.append(mp3_path)
                        break

        if not mp3_path or not os.path.exists(mp3_path):
            bot.send_message(chat_id, "❌ Не удалось найти созданный MP3 файл")
            return

        # Проверяем размер файла
        file_size = os.path.getsize(mp3_path) / (1024 * 1024)
        logger.info(f"Размер файла: {file_size:.2f} МБ, путь: {mp3_path}")

        if file_size > 50:
            bot.send_message(chat_id, f"⚠️ Файл слишком большой ({file_size:.1f} МБ). Telegram лимит 50 МБ.")
            return

        # Отправка аудио
        bot.send_message(chat_id, f"📤 Отправляю файл ({file_size:.1f} МБ)...")

        with open(mp3_path, 'rb') as audio_file:
            bot.send_audio(
                chat_id, 
                audio_file,
                title=title[:64],
                performer=info.get('uploader', 'Unknown')[:64],
                duration=duration,
                timeout=600
            )

        bot.send_message(chat_id, "✅ Готово! Наслаждайтесь музыкой!")

    except Exception as e:
        logger.error(f"Ошибка при обработке {url}: {str(e)}", exc_info=True)
        error_msg = str(e)
        if "403" in error_msg or "Forbidden" in error_msg:
            bot.send_message(chat_id, "❌ YouTube заблокировал запрос. Пробую альтернативные методы...")
            # Пробуем без прокси
            try:
                bot.send_message(chat_id, "🔄 Пробую прямой запрос...")
                download_direct(chat_id, url)
            except:
                bot.send_message(chat_id, "❌ Все методы не сработали. Попробуйте позже или другую ссылку.")
        elif "No such file" in error_msg:
            bot.send_message(chat_id, "❌ Ошибка создания файла. Попробуйте другое видео.")
        else:
            bot.send_message(chat_id, f"❌ Ошибка: {str(e)}")

    finally:
        # Удаляем временные файлы
        for file_path in temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Удален временный файл: {file_path}")
            except Exception as e:
                logger.warning(f"Не удалось удалить файл {file_path}: {e}")

def download_direct(chat_id, url):
    """Прямое скачивание без прокси"""
    try:
        user_agent = get_random_user_agent()
        ydl_opts_direct = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'http_headers': {
                'User-Agent': user_agent,
                'Referer': 'https://www.youtube.com/',
            },
            'ignoreerrors': True,
            'no_check_certificate': True,
            'retries': 5,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts_direct) as ydl:
            info = ydl.extract_info(url, download=True)
            
        # Поиск и отправка файла
        for file in os.listdir("downloads"):
            if file.endswith('.mp3'):
                mp3_path = os.path.join("downloads", file)
                with open(mp3_path, 'rb') as audio_file:
                    bot.send_audio(chat_id, audio_file, timeout=600)
                os.remove(mp3_path)
                break
                
        bot.send_message(chat_id, "✅ Успешно через прямой метод!")
        
    except Exception as e:
        raise e

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message,
        "🎶 Привет! Просто отправь мне ссылку на YouTube видео, "
        "и я преобразую его в MP3!\n\n"
        "Пример: https://youtu.be/3QqwjYC3EAg"
    )

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = extract_youtube_url(message.text)
    if not url:
        bot.reply_to(message, "❌ Это не похоже на ссылку YouTube. Пришлите корректную ссылку.")
        return

    thread = Thread(target=download_and_send_audio, args=(message.chat.id, url))
    thread.start()

def keep_alive():
    """Функция для поддержания активности"""
    while True:
        try:
            time.sleep(300)
            logger.info("✓ Bot is alive and running")
        except Exception as e:
            logger.warning(f"Keep-alive error: {e}")

def run_bot():
    logger.info("----- Запуск YouTube Music Bot -----")
    while True:
        try:
            bot.infinity_polling(timeout=120, long_polling_timeout=120)
        except Exception as e:
            logger.error(f"Ошибка бота: {e}")
            time.sleep(10)
            logger.info("Перезапуск бота...")

if __name__ == "__main__":
    # Очищаем папку downloads при запуске
    try:
        for file in os.listdir("downloads"):
            file_path = os.path.join("downloads", file)
            if os.path.isfile(file_path):
                os.remove(file_path)
    except:
        pass

    # Запускаем бота в отдельном потоке
    bot_thread = Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    # Запускаем keep-alive
    keep_alive_thread = Thread(target=keep_alive)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()

    # Запускаем Flask сервер на порту 5000 (для Railway)
    app.run(host='0.0.0.0', port=5000)
