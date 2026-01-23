import os
import telebot
from telebot import types
import threading
import time

TOKEN = "8236249109:AAFkiU0aYJBYgY12ZwO4ZJFk1M2ZavOJbIE"
bot = telebot.TeleBot(TOKEN)

search_queue = []
active_pairs = {}
user_last_messages = {}  # Храним последние message_id для каждого пользователя

# ======== ФУНКЦИЯ СОЕДИНЕНИЯ ========
def find_and_connect_users():
    while True:
        try:
            if len(search_queue) >= 2:
                user1 = search_queue.pop(0)
                user2 = search_queue.pop(0)
                
                print(f"🔗 СОЕДИНЯЕМ: {user1} и {user2}")
                
                active_pairs[user1] = user2
                active_pairs[user2] = user1
                
                # УДАЛЯЕМ старые сообщения с кнопками поиска
                delete_last_message(user1)
                delete_last_message(user2)
                
                # Отправляем НОВОЕ сообщение о найденном собеседнике
                send_match_message(user1)
                send_match_message(user2)
                
        except Exception as e:
            print(f"⚠️ Ошибка: {e}")
        
        time.sleep(1)

def delete_last_message(user_id):
    """Удаляем последнее сообщение бота у пользователя"""
    if user_id in user_last_messages:
        try:
            bot.delete_message(user_id, user_last_messages[user_id])
            del user_last_messages[user_id]
        except:
            pass

def send_match_message(user_id):
    """Отправляем сообщение о найденном собеседнике с НОВЫМИ кнопками"""
    try:
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_next = types.InlineKeyboardButton('🔄 Следующий', callback_data='next')
        btn_stop = types.InlineKeyboardButton('⛔ Стоп', callback_data='stop')
        markup.add(btn_next, btn_stop)
        
        message_text = (
            "✅ *Собеседник найден! Начинайте общение.*\n\n"
            "📋 *Доступные команды:*\n"
            "/next — следующий собеседник\n"
            "/stop — остановить поиск и завершить диалог\n\n"
            "📢 *Хочешь найти новых друзей? Приглашай друзей в бота:*\n"
            "@OnonChatTg_Bot"
        )
        
        # Отправляем и сохраняем ID сообщения
        msg = bot.send_message(
            user_id,
            message_text,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
        user_last_messages[user_id] = msg.message_id
        print(f"📨 Отправлено уведомление пользователю {user_id}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

# ======== ЗАПУСК ПОТОКА ========
search_thread = threading.Thread(target=find_and_connect_users, daemon=True)
search_thread.start()

# ======== КОМАНДА /START ========
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.chat.id
    
    # Очищаем старые состояния
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        del active_pairs[user_id]
        del active_pairs[partner_id]
        bot.send_message(partner_id, "⚠️ Собеседник перезапустил бота.")
    
    if user_id in search_queue:
        search_queue.remove(user_id)
    
    delete_last_message(user_id)  # Удаляем старые сообщения
    
    markup = types.InlineKeyboardMarkup()
    btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
    markup.add(btn_search)
    
    msg = bot.send_message(
        user_id,
        "👋 *Привет! Я бот для анонимного общения.*\n\n"
        "Нажми кнопку ниже, чтобы найти собеседника:",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    user_last_messages[user_id] = msg.message_id

# ======== КОМАНДА /SEARCH ========
@bot.message_handler(commands=['search'])
def search_command(message):
    user_id = message.chat.id
    
    if user_id in active_pairs:
        markup = types.InlineKeyboardMarkup()
        btn_next = types.InlineKeyboardButton('🔄 Следующий', callback_data='next')
        btn_stop = types.InlineKeyboardButton('⛔ Стоп', callback_data='stop')
        markup.add(btn_next, btn_stop)
        
        msg = bot.send_message(
            user_id,
            "❌ У тебя уже есть собеседник!\n"
            "Используй кнопки ниже:",
            reply_markup=markup
        )
        user_last_messages[user_id] = msg.message_id
        return
    
    if user_id in search_queue:
        bot.send_message(user_id, "⏳ Ты уже в поиске...")
        return
    
    search_queue.append(user_id)
    delete_last_message(user_id)
    
    markup = types.InlineKeyboardMarkup()
    btn_cancel = types.InlineKeyboardButton('❌ Отменить поиск', callback_data='cancel_search')
    markup.add(btn_cancel)
    
    position = len(search_queue)
    msg = bot.send_message(
        user_id,
        f"🔍 *Ищем собеседника...*\n\n"
        f"📊 Позиция в очереди: *{position}*\n"
        f"⏱️ Ожидайте соединения...",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    user_last_messages[user_id] = msg.message_id

# ======== КОМАНДА /NEXT ========
@bot.message_handler(commands=['next'])
def next_command(message):
    user_id = message.chat.id
    
    if user_id not in active_pairs:
        delete_last_message(user_id)
        
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
        markup.add(btn_search)
        
        msg = bot.send_message(
            user_id,
            "❌ *У тебя нет активного собеседника.*\n\n"
            "Нажми кнопку ниже, чтобы найти собеседника:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        user_last_messages[user_id] = msg.message_id
        return
    
    partner_id = active_pairs[user_id]
    
    delete_last_message(partner_id)
    markup = types.InlineKeyboardMarkup()
    btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
    markup.add(btn_search)
    
    msg = bot.send_message(
        partner_id,
        "⚠️ *Твой собеседник покинул диалог.*\n\n"
        "Нажми кнопку ниже, чтобы найти нового собеседника:",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    user_last_messages[partner_id] = msg.message_id
    
    del active_pairs[user_id]
    del active_pairs[partner_id]
    
    search_queue.append(user_id)
    delete_last_message(user_id)
    
    markup = types.InlineKeyboardMarkup()
    btn_cancel = types.InlineKeyboardButton('❌ Отменить поиск', callback_data='cancel_search')
    markup.add(btn_cancel)
    
    position = len(search_queue)
    msg = bot.send_message(
        user_id,
        f"🔄 *Ищем нового собеседника...*\n\n"
        f"📊 Позиция в очереди: *{position}*\n"
        f"⏱️ Ожидайте...",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    user_last_messages[user_id] = msg.message_id

# ======== КОМАНДА /STOP ========
@bot.message_handler(commands=['stop'])
def stop_command(message):
    user_id = message.chat.id
    
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        
        delete_last_message(partner_id)
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
        markup.add(btn_search)
        
        msg = bot.send_message(
            partner_id,
            "❌ *Собеседник завершил диалог.*\n\n"
            "Нажми кнопку ниже, чтобы найти нового собеседника:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        user_last_messages[partner_id] = msg.message_id
        
        del active_pairs[user_id]
        del active_pairs[partner_id]
    
    if user_id in search_queue:
        search_queue.remove(user_id)
    
    delete_last_message(user_id)
    markup = types.InlineKeyboardMarkup()
    btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
    markup.add(btn_search)
    
    msg = bot.send_message(
        user_id,
        "✅ *Диалог завершён.*\n\n"
        "Нажми кнопку ниже, чтобы найти нового собеседника:",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    user_last_messages[user_id] = msg.message_id

# ======== ОБРАБОТКА СООБЩЕНИЙ ========
@bot.message_handler(func=lambda msg: True, content_types=['text', 'photo', 'voice', 'video', 'document', 'sticker'])
def handle_messages(message):
    user_id = message.chat.id
    
    # Если пользователь в паре - пересылаем сообщение
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        
        try:
            if message.text:
                bot.send_message(partner_id, message.text)
            elif message.photo:
                bot.send_photo(partner_id, message.photo[-1].file_id, caption=message.caption)
            elif message.voice:
                bot.send_voice(partner_id, message.voice.file_id)
            elif message.video:
                bot.send_video(partner_id, message.video.file_id, caption=message.caption)
            elif message.document:
                bot.send_document(partner_id, message.document.file_id, caption=message.caption)
            elif message.sticker:
                bot.send_sticker(partner_id, message.sticker.file_id)
        except:
            pass
    
    # Если пользователь в поиске
    elif user_id in search_queue:
        position = search_queue.index(user_id) + 1
        bot.send_message(
            user_id,
            f"⏳ *Ты всё ещё в поиске...*\n"
            f"Позиция в очереди: *{position}*\n\n"
            f"Ожидайте соединения!"
        )
    
    # Если пользователь ничего не делает
    else:
        delete_last_message(user_id)
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
        markup.add(btn_search)
        
        msg = bot.send_message(
            user_id,
            "🤔 *Кажется, ты не в диалоге...*\n\n"
            "Хочешь найти собеседника?",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
        user_last_messages[user_id] = msg.message_id

# ======== ОБРАБОТКА INLINE-КНОПОК ========
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.message.chat.id
    
    # Удаляем сообщение с кнопкой
    try:
        bot.delete_message(user_id, call.message.message_id)
        if user_id in user_last_messages and user_last_messages[user_id] == call.message.message_id:
            del user_last_messages[user_id]
    except:
        pass
    
    if call.data == 'search':
        search_command(call.message)
        bot.answer_callback_query(call.id, "🔍 Начинаем поиск...")
        
    elif call.data == 'cancel_search':
        if user_id in search_queue:
            search_queue.remove(user_id)
        
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
        markup.add(btn_search)
        
        msg = bot.send_message(
            user_id,
            "✅ *Поиск отменён.*\n\n"
            "Нажми кнопку ниже, чтобы начать заново:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
        user_last_messages[user_id] = msg.message_id
        bot.answer_callback_query(call.id, "✅ Поиск отменён")
        
    elif call.data == 'next':
        next_command(call.message)
        bot.answer_callback_query(call.id, "🔄 Ищем следующего...")
        
    elif call.data == 'stop':
        stop_command(call.message)
        bot.answer_callback_query(call.id, "✅ Диалог завершён")

# ======== ЗАПУСК ========
if __name__ == "__main__":
    print("="*50)
    print("🤖 АНОНИМНЫЙ ЧАТ ЗАПУЩЕН")
    print("="*50)
    
    try:
        bot.polling(none_stop=True, interval=1, timeout=30)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
