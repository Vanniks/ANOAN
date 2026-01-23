import os
import telebot
from telebot import types
import time
import threading
import subprocess
import sys

# Автоматическая установка Flask если нет
try:
    from flask import Flask
except ImportError:
    print("Installing Flask...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask"])
    from flask import Flask

TOKEN = "8236249109:AAFkiU0aYJBYgY12ZwO4ZJFk1M2ZavOJbIE"
bot = telebot.TeleBot(TOKEN)

# ======== Flask приложение только для порта ========
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running with polling!"

# ======== ВАШ ОСНОВНОЙ КОД ========
search_queue = []
active_pairs = {}

# ======== ФУНКЦИЯ ФОНОВОГО ПОИСКА ========
def background_search():
    """Постоянно ищет пары в фоне"""
    while True:
        try:
            if len(search_queue) >= 2:
                user1 = search_queue.pop(0)
                user2 = search_queue.pop(0)
                
                if user1 not in active_pairs and user2 not in active_pairs:
                    active_pairs[user1] = user2
                    active_pairs[user2] = user1
                    
                    print(f"✅ СОЕДИНЕНО: {user1} ↔ {user2}")
                    
                    # Отправляем уведомление ОБОИМ
                    send_match_notification(user1)  # Убедитесь, что эта функция определена
                    send_match_notification(user2)
        except Exception as e:
            print(f"⚠️ Ошибка поиска: {e}")
        
        time.sleep(1)

# ======== ФУНКЦИЯ УВЕДОМЛЕНИЙ (ЕСЛИ ЕСТЬ В ВАШЕМ КОДЕ) ========
def send_match_notification(user_id):
    """Отправляет уведомление о соединении"""
    try:
        bot.send_message(user_id, "✅ Найден собеседник! Можете общаться.")
    except:
        pass

# ======== ХЕНДЛЕРЫ БОТА ========
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Привет! Я анонимный чат-бот. Используй /search для поиска собеседника.")

@bot.message_handler(commands=['search'])
def search(message):
    user_id = message.chat.id
    if user_id in active_pairs:
        bot.send_message(user_id, "❌ Вы уже в чате. Используйте /stop чтобы выйти.")
        return
    
    if user_id in search_queue:
        bot.send_message(user_id, "⏳ Вы уже в очереди поиска...")
        return
    
    search_queue.append(user_id)
    bot.send_message(user_id, "🔍 Ищем собеседника...")

@bot.message_handler(commands=['stop'])
def stop(message):
    user_id = message.chat.id
    # ... ваш код отключения ...

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.chat.id
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        try:
            bot.send_message(partner_id, message.text)
        except:
            pass

# ======== ЗАПУСК ПРИЛОЖЕНИЯ ========
if __name__ == "__main__":
    # Запускаем фоновый поток поиска
    threading.Thread(target=background_search, daemon=True).start()
    
    # Запускаем бота в отдельном потоке
    def start_bot():
        print("Starting bot polling...")
        bot.polling(none_stop=True, interval=1, timeout=20)
    
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем Flask сервер для порта
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting Flask server on port {port}...")
    app.run(host="0.0.0.0", port=port)
