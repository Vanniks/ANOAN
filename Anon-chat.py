import os
import telebot
from telebot import types
import threading
import time

TOKEN = "8236249109:AAFkiU0aYJBYgY12ZwO4ZJFk1M2ZavOJbIE"
bot = telebot.TeleBot(TOKEN)

search_queue = []
active_pairs = {}

# Функция отправки сообщения о найденном собеседнике
def send_match_message(user_id):
    try:
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_next = types.InlineKeyboardButton('🔄 Следующий', callback_data='next_chat')
        btn_stop = types.InlineKeyboardButton('⛔ Стоп', callback_data='stop_chat')
        markup.add(btn_next, btn_stop)
        
        message_text = (
            "✅ *Собеседник найден! Начинайте общение.*\n\n"
            "📋 *Доступные команды:*\n"
            "🔄 */next* — следующий собеседник\n"
            "⛔ */stop* — остановить диалог\n\n"
            "📢 *Приглашай друзей в бота:*\n"
            "@OnonChatTg_Bot"
        )
        
        bot.send_message(
            user_id,
            message_text,
            reply_markup=markup,
            parse_mode="Markdown"
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
        
        time.sleep(1)

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
            "⚠️ *Собеседник перезапустил бота.*\n\n"
            "Нажми кнопку ниже, чтобы найти нового собеседника:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    
    # Показываем инлайн-кнопку (ВАЖНО: только инлайн!)
    markup = types.InlineKeyboardMarkup()
    btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='start_search')
    markup.add(btn_search)
    
    bot.send_message(
        user_id,
        "👋 *Привет! Я бот для анонимного общения.*\n\n"
        "📌 *Как пользоваться:*\n"
        "1. Нажми кнопку ниже 👇\n"
        "2. Жди соединения с собеседником\n"
        "3. Общайся анонимно\n"
        "4. Используй /next для нового собеседника\n\n"
        "📢 *Приглашай друзей:* @OnonChatTg_Bot",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    # Удаляем сообщение с текстом "🔍 Начать поиск" если оно есть
    try:
        bot.delete_message(user_id, message.message_id)
    except:
        pass
# Обработчик инлайн-кнопок
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.message.chat.id
    
    if call.data == 'start_search':
        # Удаляем старые сообщения с кнопками
        try:
            bot.delete_message(user_id, call.message.message_id)
        except:
            pass
        
        # Запускаем поиск
        if user_id in active_pairs:
            bot.answer_callback_query(call.id, "❌ У тебя уже есть собеседник!")
            return
        
        if user_id in search_queue:
            bot.answer_callback_query(call.id, "🔍 Ты уже в очереди поиска...")
            return
        
        # Добавляем в очередь
        search_queue.append(user_id)
        bot.send_message(user_id, "🔍 Ищем собеседника...")
        bot.answer_callback_query(call.id, "✅ Начинаем поиск...")
        
    elif call.data == 'stop_search':
        # Удаляем из поиска
        if user_id in search_queue:
            search_queue.remove(user_id)
        
        # Показываем кнопку поиска
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='start_search')
        markup.add(btn_search)
        
        bot.send_message(
            user_id,
            "✅ Поиск остановлен.\n\n"
            "Нажми кнопку ниже, чтобы начать поиск заново:",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id, "✅ Поиск остановлен")
        
    elif call.data == 'next_chat':
        # Команда "Следующий" из инлайн-кнопки
        if user_id not in active_pairs:
            bot.answer_callback_query(call.id, "❌ У тебя нет собеседника!")
            return
        
        partner_id = active_pairs[user_id]
        
        # Уведомляем партнёра
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='start_search')
        markup.add(btn_search)
        
        bot.send_message(
            partner_id,
            "⚠️ *Твой собеседник покинул диалог.*\n\n"
            "Нажми кнопку ниже, чтобы найти нового собеседника:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
        # Удаляем пару
        del active_pairs[user_id]
        del active_pairs[partner_id]
        
        # Только инициатор идёт в поиск
        search_queue.append(user_id)
        
        # Уведомляем инициатора
        markup_user = types.InlineKeyboardMarkup()
        btn_stop = types.InlineKeyboardButton('⛔ Остановить поиск', callback_data='stop_search')
        markup_user.add(btn_stop)
        
        bot.send_message(
            user_id,
            "🔄 *Ищем нового собеседника...*\n\n"
            "Нажми кнопку ниже, чтобы остановить поиск:",
            reply_markup=markup_user,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, "🔄 Ищем нового собеседника...")
        
    elif call.data == 'stop_chat':
        # Команда "Стоп" из инлайн-кнопки
        if user_id in active_pairs:
            partner_id = active_pairs[user_id]
            
            # Уведомляем партнёра
            markup = types.InlineKeyboardMarkup()
            btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='start_search')
            markup.add(btn_search)
            
            bot.send_message(
                partner_id,
                "❌ *Собеседник завершил диалог.*\n\n"
                "Нажми кнопку ниже, чтобы найти нового собеседника:",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            
            del active_pairs[user_id]
            del active_pairs[partner_id]
        
        # Удаляем из поиска
        if user_id in search_queue:
            search_queue.remove(user_id)
        
        # Показываем кнопку поиска
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='start_search')
        markup.add(btn_search)
        
        bot.send_message(
            user_id,
            "✅ *Диалог завершён.*\n\n"
            "Нажми кнопку ниже, чтобы найти нового собеседника:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, "✅ Диалог завершён")

# Команда /next - найти нового собеседника
@bot.message_handler(commands=['next'])
def next_chat(message):
    user_id = message.chat.id
    
    if user_id not in active_pairs:
        # Показываем инлайн-кнопку
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='start_search')
        markup.add(btn_search)
        
        bot.send_message(
            user_id,
            "❌ *У тебя нет активного собеседника.*\n\n"
            "Нажми кнопку ниже, чтобы найти собеседника:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return
    
    partner_id = active_pairs[user_id]
    
    # Уведомляем партнёра
    markup_partner = types.InlineKeyboardMarkup()
    btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='start_search')
    markup_partner.add(btn_search)
    
    bot.send_message(
        partner_id,
        "⚠️ *Твой собеседник покинул диалог.*\n\n"
        "Нажми кнопку ниже, чтобы найти нового собеседника:",
        reply_markup=markup_partner,
        parse_mode="Markdown"
    )
    
    # Удаляем пару
    del active_pairs[user_id]
    del active_pairs[partner_id]
    
    # Только инициатор идёт в поиск
    search_queue.append(user_id)
    
    # Уведомляем инициатора
    markup_user = types.InlineKeyboardMarkup()
    btn_stop = types.InlineKeyboardButton('⛔ Остановить поиск', callback_data='stop_search')
    markup_user.add(btn_stop)
    
    bot.send_message(
        user_id,
        "🔄 *Ищем нового собеседника...*\n\n"
        "Нажми кнопку ниже, чтобы остановить поиск:",
        reply_markup=markup_user,
        parse_mode="Markdown"
    )

# Команда /stop - остановить диалог
@bot.message_handler(commands=['stop'])
def stop_chat(message):
    user_id = message.chat.id
    
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        
        # Показываем партнёру инлайн-кнопку
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='start_search')
        markup.add(btn_search)
        
        bot.send_message(
            partner_id,
            "❌ *Собеседник завершил диалог.*\n\n"
            "Нажми кнопку ниже, чтобы найти нового собеседника:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
        del active_pairs[user_id]
        del active_pairs[partner_id]
    
    # Удаляем из очереди поиска
    if user_id in search_queue:
        search_queue.remove(user_id)
    
    # Показываем инлайн-кнопку
    markup = types.InlineKeyboardMarkup()
    btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='start_search')
    markup.add(btn_search)
    
    bot.send_message(
        user_id,
        "✅ *Диалог завершён.*\n\n"
        "Нажми кнопку ниже, чтобы найти нового собеседника:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# Пересылка сообщений между собеседниками
@bot.message_handler(func=lambda msg: True, content_types=['text', 'photo', 'voice', 'video', 'document', 'sticker'])
def forward_message(message):
    user_id = message.chat.id
    
    # Если пользователь написал "🔍 Начать поиск" или "Начать поиск"
    if message.text and (message.text == '🔍 Начать поиск' or message.text == 'Начать поиск'):
        # Показываем инлайн-кнопку вместо старой логики
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='start_search')
        markup.add(btn_search)
        
        bot.send_message(
            user_id,
            "ℹ️ *Пожалуйста, используй кнопку ниже для поиска:*\n\n"
            "Нажми на кнопку 👇 чтобы начать поиск собеседника:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return
    
    # Если пользователь в активной паре - пересылаем сообщение
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
    
    # Если пользователь в поиске - уведомляем его
    elif user_id in search_queue:
        markup = types.InlineKeyboardMarkup()
        btn_stop = types.InlineKeyboardButton('⛔ Остановить поиск', callback_data='stop_search')
        markup.add(btn_stop)
        
        bot.send_message(
            user_id,
            "⏳ *Ты всё ещё в поиске собеседника...*\n"
            "Ожидайте соединения.\n\n"
            "Нажми кнопку ниже, чтобы остановить поиск:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    
    # Если пользователь не в поиске и не в паре - предлагаем начать поиск
    else:
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='start_search')
        markup.add(btn_search)
        
        bot.send_message(
            user_id,
            "❌ *У тебя нет собеседника.*\n\n"
            "Нажми кнопку ниже, чтобы начать поиск:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
# Запуск бота
if __name__ == "__main__":
    print("🤖 Бот запущен и готов к работе...")
    print("📊 Статистика: поиск каждую секунду")
    
    try:
        bot.polling(none_stop=True, interval=1, timeout=30)
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")

