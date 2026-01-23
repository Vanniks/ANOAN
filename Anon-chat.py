import os
import telebot
from flask import Flask, request
from telebot import types

# Токен бота
TOKEN = "8236249109:AAFkiU0aYJBYgY12ZwO4ZJFk1M2ZavOJbIE"
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

# Хранилище для очереди поиска и текущих пар
search_queue = []
active_pairs = {}

# Функция отправки сообщения о найденном собеседнике
def send_match_message(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_next = types.KeyboardButton('/next')
    btn_stop = types.KeyboardButton('/stop')
    markup.add(btn_next, btn_stop)
    
    message_text = (
        "✅ *Собеседник найден! Начинайте общение.*\n\n"
        "📋 *Доступные команды:*\n"
        "*/next* — следующий собеседник\n"
        "*/stop* — остановить поиск и завершить диалог\n\n"
        "📢 *Хочешь найти новых друзей? Приглашай друзей в бота:*\n"
        "@OnonChatTg_Bot"
    )
    
    bot.send_message(
        user_id,
        message_text,
        reply_markup=markup,
        parse_mode="Markdown"
    )

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_search = types.KeyboardButton('🔍 Начать поиск')
    markup.add(btn_search)
    
    bot.send_message(
        message.chat.id,
        "👋 Привет! Я бот для анонимного общения.\n"
        "Нажми кнопку ниже, чтобы найти собеседника.",
        reply_markup=markup
    )

# Обработчик кнопки поиска
@bot.message_handler(func=lambda msg: msg.text == '🔍 Начать поиск')
def search(message):
    user_id = message.chat.id
    
    if user_id in active_pairs:
        bot.send_message(user_id, "❌ У тебя уже есть собеседник! Используй /stop чтобы завершить текущий диалог.")
        return
    
    if user_id in search_queue:
        bot.send_message(user_id, "🔍 Ты уже в очереди поиска...")
        return
    
    # Добавляем в очередь
    search_queue.append(user_id)
    bot.send_message(user_id, "🔍 Ищем собеседника...")
    
    # Проверяем, есть ли пара
    if len(search_queue) >= 2:
        user1 = search_queue.pop(0)
        user2 = search_queue.pop(0)
        
        # Соединяем их
        active_pairs[user1] = user2
        active_pairs[user2] = user1
        
        # Отправляем сообщение о найденном собеседнике (ТО САМОЕ СООБЩЕНИЕ!)
        send_match_message(user1)
        send_match_message(user2)

# Команда /next - найти нового собеседника
@bot.message_handler(commands=['next'])
def next_chat(message):
    user_id = message.chat.id
    
    if user_id not in active_pairs:
        bot.send_message(user_id, "❌ У тебя нет активного собеседника. Используй /start для поиска.")
        return
    
    # Получаем текущего собеседника
    partner_id = active_pairs[user_id]
    
    # Уведомляем собеседника
    bot.send_message(partner_id, "⚠️ *Твой собеседник покинул диалог.*\nИспользуй /next для поиска нового.", parse_mode="Markdown")
    
    # Разрываем текущую связь
    del active_pairs[user_id]
    del active_pairs[partner_id]
    
    # Добавляем обоих обратно в поиск
    search_queue.append(user_id)
    search_queue.append(partner_id)
    
    bot.send_message(user_id, "🔄 Ищем нового собеседника...")
    
    # Проверяем пары
    if len(search_queue) >= 2:
        user1 = search_queue.pop(0)
        user2 = search_queue.pop(0)
        
        active_pairs[user1] = user2
        active_pairs[user2] = user1
        
        send_match_message(user1)
        send_match_message(user2)

# Команда /stop - остановить диалог
@bot.message_handler(commands=['stop'])
def stop_chat(message):
    user_id = message.chat.id
    
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        bot.send_message(partner_id, "❌ *Собеседник завершил диалог.*", parse_mode="Markdown")
        
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
    return "Bot is running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    return 'Bad request', 400

# Запуск
if __name__ == "__main__":
    print("🤖 Бот запущен...")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)





