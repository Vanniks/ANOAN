import os
import asyncio
import threading
import requests
import time
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# --- Конфигурация ---
TOKEN = os.environ.get("8920183520:AAG8RYf9WlNPdQbMBY-AWdUhsZ2ohbS197Q")
YOUR_LINK = "https://t.me/chat_d1ya_obsheniya"  # <-- замени на свою ссылку
APP_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:5000") # Render сам пропишет этот URL

# --- Инициализация ---
bot = Bot(token=TOKEN)
dp = Dispatcher()
app = Flask(__name__)

# --- Обработчики бота ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = f"""
👋 Привет, {message.from_user.first_name}!

Добро пожаловать в наш дружный чат общения! 

🔗 Вот твоя ссылка: {YOUR_LINK}

Надеюсь тебе понравится! 😊
    """
    await message.answer(welcome_text)

@dp.message()
async def echo(message: types.Message):
    await message.answer(
        f"Привет! Нажми /start для приветствия или перейди по ссылке: {YOUR_LINK}"
    )

# --- Flask-ручки для Render ---
@app.route('/')
def index():
    return "Bot is running!"

@app.route('/health')
def health():
    return "OK", 200

# --- Функция Anti-Sleep (пингует сама себя) ---
def keep_alive():
    """Фоновая функция, которая каждые 5 минут дергает health-check"""
    while True:
        time.sleep(300) # 5 минут
        try:
            # Стучимся сами к себе
            ping_url = f"{APP_URL}/health"
            response = requests.get(ping_url)
            print(f"Self-ping: {ping_url} -> {response.status_code}")
        except Exception as e:
            print(f"Keep-alive error: {e}")

# --- Запуск всего ---
async def main():
    await dp.start_polling(bot)

def run_bot():
    asyncio.run(main())

if __name__ == "__main__":
    # Запускаем aiogram в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем anti-sleep пингер в отдельном потоке
    ping_thread = threading.Thread(target=keep_alive, daemon=True)
    ping_thread.start()
    
    # Запускаем Flask-сервер
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
