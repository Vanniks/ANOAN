import os
import telebot
from telebot import types
import threading
import time

# ======== НАСТРОЙКИ ========
TOKEN = "8236249109:AAFkiU0aYJBYgY12ZwO4ZJFk1M2ZavOJbIE"
bot = telebot.TeleBot(TOKEN)

# ======== ХРАНИЛИЩЕ ========
search_queue = []      # Очередь поиска
active_pairs = {}      # Активные пары {user1: user2, user2: user1}

# ======== ОСНОВНЫЕ ФУНКЦИИ ========
def find_and_connect_users():
    """Постоянно ищет и соединяет пользователей"""
    while True:
        try:
            # Если есть хотя бы 2 человека в очереди
            if len(search_queue) >= 2:
                user1 = search_queue.pop(0)
                user2 = search_queue.pop(0)
                
                print(f"🔗 СОЕДИНЯЕМ: {user1} и {user2}")
                
                # Соединяем их
                active_pairs[user1] = user2
                active_pairs[user2] = user1
                
                # ОТПРАВЛЯЕМ УВЕДОМЛЕНИЕ О НАЙДЕННОМ СОБЕСЕДНИКЕ
                send_match_found_message(user1)
                send_match_found_message(user2)
                
        except Exception as e:
            print(f"⚠️ Ошибка в find_and_connect_users: {e}")
        
        time.sleep(1)  # Проверяем каждую секунду

def send_match_found_message(user_id):
    """Отправляет сообщение о найденном собеседнике"""
    try:
        # Создаем инлайн-кнопки
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_next = types.InlineKeyboardButton('🔄 Следующий', callback_data='next')
        btn_stop = types.InlineKeyboardButton('⛔ Стоп', callback_data='stop')
        markup.add(btn_next, btn_stop)
        
        # Текст сообщения (ТОТ САМЫЙ, КОТОРЫЙ ТЫ ХОТЕЛ)
        message_text = (
            "✅ *Собеседник найден! Начинайте общение.*\n\n"
            "📋 *Доступные команды:*\n"
            "/next — следующий собеседник\n"
            "/stop — остановить поиск и завершить диалог\n\n"
            "📢 *Хочешь найти новых друзей? Приглашай друзей в бота:*\n"
            "@OnonChatTg_Bot"
        )
        
        # Отправляем сообщение
        bot.send_message(
            user_id,
            message_text,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
        print(f"📨 Уведомление отправлено пользователю {user_id}")
        
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления: {e}")

# ======== ЗАПУСК ПОТОКА ПОИСКА ========
search_thread = threading.Thread(target=find_and_connect_users, daemon=True)
search_thread.start()

# ======== ОБРАБОТЧИКИ КОМАНД ========
@bot.message_handler(commands=['start'])
def start_command(message):
    """Команда /start - главное меню"""
    user_id = message.chat.id
    
    # Очищаем старые состояния
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        del active_pairs[user_id]
        del active_pairs[partner_id]
        bot.send_message(partner_id, "⚠️ Собеседник перезапустил бота.")
    
    if user_id in search_queue:
        search_queue.remove(user_id)
    
    # Создаем инлайн-кнопку
    markup = types.InlineKeyboardMarkup()
    btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
    markup.add(btn_search)
    
    # Отправляем приветствие
    bot.send_message(
        user_id,
        "👋 *Привет! Я бот для анонимного общения.*\n\n"
        "Нажми кнопку ниже, чтобы найти собеседника:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['search'])
def search_command(message):
    """Команда /search - начать поиск"""
    user_id = message.chat.id
    
    # Проверяем, не в паре ли уже
    if user_id in active_pairs:
        bot.send_message(user_id, "❌ У тебя уже есть собеседник!")
        return
    
    # Проверяем, не в поиске ли уже
    if user_id in search_queue:
        bot.send_message(user_id, "⏳ Ты уже в поиске...")
        return
    
    # Добавляем в очередь
    search_queue.append(user_id)
    
    # Создаем кнопку для отмены поиска
    markup = types.InlineKeyboardMarkup()
    btn_cancel = types.InlineKeyboardButton('❌ Отменить поиск', callback_data='cancel_search')
    markup.add(btn_cancel)
    
    # Отправляем сообщение
    position = len(search_queue)
    bot.send_message(
        user_id,
        f"🔍 *Ищем собеседника...*\n\n"
        f"📊 Позиция в очереди: *{position}*\n"
        f"⏱️ Ожидайте соединения...",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['next'])
def next_command(message):
    """Команда /next - найти нового собеседника"""
    user_id = message.chat.id
    
    if user_id not in active_pairs:
        # Если нет собеседника, предлагаем начать поиск
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
        markup.add(btn_search)
        
        bot.send_message(
            user_id,
            "❌ *У тебя нет активного собеседника.*\n\n"
            "Нажми кнопку ниже, чтобы найти собеседника:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return
    
    # Получаем текущего собеседника
    partner_id = active_pairs[user_id]
    
    # Уведомляем партнера
    markup = types.InlineKeyboardMarkup()
    btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
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
    
    # Добавляем инициатора в поиск
    search_queue.append(user_id)
    
    # Сообщаем инициатору
    markup = types.InlineKeyboardMarkup()
    btn_cancel = types.InlineKeyboardButton('❌ Отменить поиск', callback_data='cancel_search')
    markup.add(btn_cancel)
    
    position = len(search_queue)
    bot.send_message(
        user_id,
        f"🔄 *Ищем нового собеседника...*\n\n"
        f"📊 Позиция в очереди: *{position}*\n"
        f"⏱️ Ожидайте...",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['stop'])
def stop_command(message):
    """Команда /stop - остановить диалог"""
    user_id = message.chat.id
    
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        
        # Уведомляем партнера
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
        markup.add(btn_search)
        
        bot.send_message(
            partner_id,
            "❌ *Собеседник завершил диалог.*\n\n"
            "Нажми кнопку ниже, чтобы найти нового собеседника:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
        # Удаляем пару
        del active_pairs[user_id]
        del active_pairs[partner_id]
    
    # Удаляем из поиска
    if user_id in search_queue:
        search_queue.remove(user_id)
    
    # Предлагаем начать новый поиск
    markup = types.InlineKeyboardMarkup()
    btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
    markup.add(btn_search)
    
    bot.send_message(
        user_id,
        "✅ *Диалог завершён.*\n\n"
        "Нажми кнопку ниже, чтобы найти нового собеседника:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# ======== ОБРАБОТЧИК СООБЩЕНИЙ ========
@bot.message_handler(func=lambda msg: True, content_types=['text', 'photo', 'voice', 'video', 'document', 'sticker'])
def handle_messages(message):
    """Обработка всех сообщений"""
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
        markup = types.InlineKeyboardMarkup()
        btn_cancel = types.InlineKeyboardButton('❌ Отменить поиск', callback_data='cancel_search')
        markup.add(btn_cancel)
        
        bot.send_message(
            user_id,
            f"⏳ *Ты всё ещё в поиске...*\n"
            f"Позиция в очереди: *{position}*\n\n"
            f"Ожидайте соединения!",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    
    # Если пользователь ничего не делает
    else:
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
        markup.add(btn_search)
        
        bot.send_message(
            user_id,
            "🤔 *Кажется, ты не в диалоге...*\n\n"
            "Хочешь найти собеседника?",
            reply_markup=markup,
            parse_mode="Markdown"
        )

# ======== ОБРАБОТЧИК INLINE-КНОПОК ========
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    """Обработка нажатий на инлайн-кнопки"""
    user_id = call.message.chat.id
    
    try:
        # Удаляем сообщение с кнопкой
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    
    if call.data == 'search':
        # Начать поиск
        search_command(call.message)
        bot.answer_callback_query(call.id, "🔍 Начинаем поиск...")
        
    elif call.data == 'cancel_search':
        # Отменить поиск
        if user_id in search_queue:
            search_queue.remove(user_id)
        
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
        markup.add(btn_search)
        
        bot.send_message(
            user_id,
            "✅ *Поиск отменён.*\n\n"
            "Нажми кнопку ниже, чтобы начать заново:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, "✅ Поиск отменён")
        
    elif call.data == 'next':
        # Следующий собеседник (через кнопку)
        next_command(call.message)
        bot.answer_callback_query(call.id, "🔄 Ищем следующего...")
        
    elif call.data == 'stop':
        # Остановить диалог (через кнопку)
        stop_command(call.message)
        bot.answer_callback_query(call.id, "✅ Диалог завершён")

# ======== ЗАПУСК БОТА ========
if __name__ == "__main__":
    print("="*50)
    print("🤖 АНОНИМНЫЙ ЧАТ ЗАПУЩЕН")
    print("="*50)
    print(f"📊 В очереди: {len(search_queue)}")
    print(f"💬 Активных пар: {len(active_pairs)//2}")
    print("="*50)
    
    try:
        bot.polling(none_stop=True, interval=1, timeout=30)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
