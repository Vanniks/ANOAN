import os
import telebot
from flask import Flask, request
from telebot import types
import threading
import time

# Токен бота
TOKEN = "8236249109:AAFkiU0aYJBYgY12ZwO4ZJFk1M2ZavOJbIE"
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

# Хранилище для очереди поиска и текущих пар
search_queue = []
active_pairs = {}

# Функция отправки сообщения о найденном собеседнике
def send_match_message(user_id):
    try:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btn_next = types.KeyboardButton('/next')
        btn_stop = types.KeyboardButton('/stop')
        markup.add(btn_next, btn_stop)
        
        message_text = (
            "✅ Собеседник найден! Начинайте общение.\n\n"
            "📋 Доступные команды:\n"
            "/next — следующий собеседник\n"
            "/stop — остановить поиск и завершить диалог\n\n"
            "📢 Хочешь найти новых друзей? Приглашай друзей в бота:\n"
            "@OnonChatTg_Bot"
        )
        
        bot.send_message(
            user_id,
            message_text,
            reply_markup=markup
        )
        print(f"📨 Сообщение отправлено пользователю {user_id}")
    except Exception as e:
        print(f"❌ Ошибка отправки сообщения: {e}")

# Функция для соединения пользователей
def connect_users():
    while True:
        try:
            if len(search_queue) >= 2:
                user1 = search_queue.pop(0)
                user2 = search_queue.pop(0)
                
                # Проверяем, что пользователи ещё не в паре
                if user1 not in active_pairs and user2 not in active_pairs:
                    # Соединяем их
                    active_pairs[user1] = user2
                    active_pairs[user2] = user1
                    
                    print(f"🔗 Соединены: {user1} и {user2}")
                    
                    # Отправляем сообщение о найденном собеседнике
                    send_match_message(user1)
                    send_match_message(user2)
        except Exception as e:
            print(f"❌ Ошибка в connect_users: {e}")
        
        time.sleep(1)  # Пауза между проверками

# Запускаем поток для соединения пользователей
connect_thread = threading.Thread(target=connect_users, daemon=True)
connect_thread.start()

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    
    # Очищаем предыдущие состояния
    if user_id in search_queue:
        search_queue.remove(user_id)
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        del active_pairs[user_id]
        del active_pairs[partner_id]
        
        # Уведомляем партнёра
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='start_search')
        markup.add(btn_search)
        
        bot.send_message(
            partner_id,
            "⚠️ Собеседник перезапустил бота.\n\n"
            "Нажми кнопку ниже, чтобы найти нового собеседника:",
            reply_markup=markup
        )
    
    # Показываем инлайн-кнопку
    markup = types.InlineKeyboardMarkup()
    btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='start_search')
    markup.add(btn_search)
    
    bot.send_message(
        user_id,
        "👋 *Привет! Я бот для анонимного общения.*\n\n"
        "Нажми кнопку ниже, чтобы найти собеседника:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# Команда /stop - остановить диалог
@bot.message_handler(commands=['stop'])
def stop_chat(message):
    user_id = message.chat.id
    
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        bot.send_message(partner_id, "❌ Собеседник завершил диалог.")
        
        del active_pairs[user_id]
        del active_pairs[partner_id]
    
    # Удаляем из очереди поиска
    if user_id in search_queue:
        search_queue.remove(user_id)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_search = types.KeyboardButton('🔍 Начать поиск')
    markup.add(btn_search)
    
    bot.send_message(
        user_id,
        "✅ Диалог завершён. Используй кнопку ниже для нового поиска.",
        reply_markup=markup
    )

# Пересылка сообщений между собеседниками
@bot.message_handler(func=lambda msg: True, content_types=['text', 'photo', 'voice', 'video', 'document', 'sticker'])
def forward_message(message):
    user_id = message.chat.id
    
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        
        # Пересылаем текст
        if message.text:
            bot.send_message(partner_id, message.text)
        # Пересылаем фото
        elif message.photo:
            bot.send_photo(partner_id, message.photo[-1].file_id, caption=message.caption)
        # Пересылаем голосовое
        elif message.voice:
            bot.send_voice(partner_id, message.voice.file_id)
        # Пересылаем стикеры и другие типы
        else:
            bot.send_message(partner_id, "📎 [Сообщение недоступно для предпросмотра]")
    elif user_id not in search_queue:
        bot.send_message(user_id, "❌ У тебя нет собеседника. Нажми '🔍 Начать поиск' или используй /start")

# Flask маршруты
@app.route('/')
def home():
    return f"Bot is running! Users in queue: {len(search_queue)}, Active pairs: {len(active_pairs)//2}"

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    return 'Bad request', 400

# Запуск бота в отдельном потоке
def run_bot():
    print("🤖 Бот запущен и готов к работе...")
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=30)
        except Exception as e:
            print(f"⚠️ Ошибка polling: {e}")
            time.sleep(5)

# Запуск
if __name__ == "__main__":
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем Flask
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Flask запущен на порту {port}")
    app.run(host="0.0.0.0", port=port)



