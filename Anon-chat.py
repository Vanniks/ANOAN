import os
import telebot
from telebot import types
import threading
import time

TOKEN = "8236249109:AAFkiU0aYJBYgY12ZwO4ZJFk1M2ZavOJbIE"
bot = telebot.TeleBot(TOKEN)

search_queue = []
active_pairs = {}
user_last_messages = {}

# ======== ФУНКЦИИ ========
def delete_last_message(user_id):
    if user_id in user_last_messages:
        try:
            bot.delete_message(user_id, user_last_messages[user_id])
            del user_last_messages[user_id]
        except:
            pass

def send_match_message(user_id):
    """Отправка сообщения о найденном собеседнике"""
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
        
        msg = bot.send_message(
            user_id,
            message_text,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
        user_last_messages[user_id] = msg.message_id
        print(f"✅ Уведомление отправлено {user_id}")
        
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")

def find_and_connect_users():
    """Постоянный поиск пар"""
    while True:
        try:
            if len(search_queue) >= 2:
                user1 = search_queue.pop(0)
                user2 = search_queue.pop(0)
                
                print(f"🔗 Соединяем: {user1} и {user2}")
                
                active_pairs[user1] = user2
                active_pairs[user2] = user1
                
                delete_last_message(user1)
                delete_last_message(user2)
                
                send_match_message(user1)
                send_match_message(user2)
                
        except Exception as e:
            print(f"⚠️ Ошибка соединения: {e}")
        
        time.sleep(1)

# ======== ЗАПУСК ПОТОКА ========
search_thread = threading.Thread(target=find_and_connect_users, daemon=True)
search_thread.start()

# ======== КОМАНДЫ ========
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.chat.id
    
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        del active_pairs[user_id]
        del active_pairs[partner_id]
        bot.send_message(partner_id, "⚠️ Собеседник вышел.")
    
    if user_id in search_queue:
        search_queue.remove(user_id)
    
    delete_last_message(user_id)
    
    markup = types.InlineKeyboardMarkup()
    btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
    markup.add(btn_search)
    
    msg = bot.send_message(
        user_id,
        "👋 *Привет! Нажми кнопку ниже, чтобы найти собеседника:*",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    user_last_messages[user_id] = msg.message_id

@bot.message_handler(commands=['search'])
def search_command(message):
    user_id = message.chat.id
    
    if user_id in active_pairs:
        bot.send_message(user_id, "❌ У тебя уже есть собеседник!")
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
        f"🔍 *Ищем собеседника...*\n"
        f"📊 Позиция в очереди: *{position}*",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    user_last_messages[user_id] = msg.message_id

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
            "❌ *Нет активного собеседника.*\n"
            "Нажми кнопку ниже:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return
    
    partner_id = active_pairs[user_id]
    
    delete_last_message(partner_id)
    markup = types.InlineKeyboardMarkup()
    btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
    markup.add(btn_search)
    
    bot.send_message(
        partner_id,
        "⚠️ *Собеседник покинул диалог.*",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    del active_pairs[user_id]
    del active_pairs[partner_id]
    
    search_queue.append(user_id)
    delete_last_message(user_id)
    
    markup = types.InlineKeyboardMarkup()
    btn_cancel = types.InlineKeyboardButton('❌ Отменить поиск', callback_data='cancel_search')
    markup.add(btn_cancel)
    
    position = len(search_queue)
    bot.send_message(
        user_id,
        f"🔄 *Ищем нового...*\n"
        f"📊 Позиция: *{position}*",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['stop'])
def stop_command(message):
    user_id = message.chat.id
    
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        
        delete_last_message(partner_id)
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
        markup.add(btn_search)
        
        bot.send_message(
            partner_id,
            "❌ *Собеседник завершил диалог.*",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
        del active_pairs[user_id]
        del active_pairs[partner_id]
    
    if user_id in search_queue:
        search_queue.remove(user_id)
    
    delete_last_message(user_id)
    markup = types.InlineKeyboardMarkup()
    btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
    markup.add(btn_search)
    
    bot.send_message(
        user_id,
        "✅ *Диалог завершён.*\n"
        "Найди нового собеседника:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: True)
def handle_messages(message):
    user_id = message.chat.id
    
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        try:
            bot.send_message(partner_id, message.text)
        except:
            pass
    elif user_id in search_queue:
        position = search_queue.index(user_id) + 1
        bot.send_message(
            user_id,
            f"⏳ *В поиске...*\n"
            f"Позиция: *{position}*",
            parse_mode="Markdown"
        )
    else:
        delete_last_message(user_id)
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
        markup.add(btn_search)
        
        bot.send_message(
            user_id,
            "🤔 *Не в диалоге.*\n"
            "Найди собеседника:",
            reply_markup=markup,
            parse_mode="Markdown"
        )

# ======== INLINE КНОПКИ ========
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.message.chat.id
    
    try:
        bot.delete_message(user_id, call.message.message_id)
        if user_id in user_last_messages and user_last_messages[user_id] == call.message.message_id:
            del user_last_messages[user_id]
    except:
        pass
    
    if call.data == 'search':
        search_command(call.message)
        bot.answer_callback_query(call.id, "🔍 Ищем...")
        
    elif call.data == 'cancel_search':
        if user_id in search_queue:
            search_queue.remove(user_id)
        
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
        markup.add(btn_search)
        
        bot.send_message(
            user_id,
            "✅ *Поиск отменён.*",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, "✅ Отменено")
        
    elif call.data == 'next':
        next_command(call.message)
        bot.answer_callback_query(call.id, "🔄 Ищем...")
        
    elif call.data == 'stop':
        stop_command(call.message)
        bot.answer_callback_query(call.id, "✅ Завершено")

# ======== ЗАПУСК ========
if __name__ == "__main__":
    print("="*50)
    print("🤖 БОТ ЗАПУСКАЕТСЯ...")
    print("="*50)
    
    # Ждём 3 секунды перед запуском (решение конфликта)
    time.sleep(3)
    
    try:
        # skip_pending пропускает старые сообщения
        bot.polling(none_stop=True, skip_pending=True, interval=1, timeout=30)
        print("✅ Бот успешно запущен!")
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")
        print("🔄 Перезапуск через 10 секунд...")
        time.sleep(10)
