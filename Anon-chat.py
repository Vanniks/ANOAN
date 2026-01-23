import telebot
from telebot import types
import time
import threading

TOKEN = "8236249109:AAFkiU0aYJBYgY12ZwO4ZJFk1M2ZavOJbIE"
bot = telebot.TeleBot(TOKEN)

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
                
                # Проверяем, что пользователи ещё не в паре
                if user1 not in active_pairs and user2 not in active_pairs:
                    active_pairs[user1] = user2
                    active_pairs[user2] = user1
                    
                    print(f"✅ СОЕДИНЕНО: {user1} ↔ {user2}")
                    
                    # Отправляем уведомление ОБОИМ
                    send_match_notification(user1)
                    send_match_notification(user2)
        except Exception as e:
            print(f"⚠️ Ошибка поиска: {e}")
        
        time.sleep(1)  # Проверяем каждую секунду

# Запускаем фоновый поиск
search_thread = threading.Thread(target=background_search, daemon=True)
search_thread.start()

# ======== ОСНОВНЫЕ ФУНКЦИИ ========
def send_match_notification(user_id):
    """Отправляет уведомление о найденном собеседнике"""
    try:
        # Клавиатура со ВСЕМИ командами
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_next = types.InlineKeyboardButton('🔄 Следующий', callback_data='next')
        btn_stop = types.InlineKeyboardButton('⛔ Стоп', callback_data='stop')
        btn_profile = types.InlineKeyboardButton('👤 Профиль', callback_data='profile')
        btn_search = types.InlineKeyboardButton('🔍 Поиск', callback_data='search')
        btn_help = types.InlineKeyboardButton('❓ Помощь', callback_data='help')
        markup.add(btn_next, btn_stop, btn_profile, btn_search, btn_help)
        
        message = (
            "🎉 *СОБЕСЕДНИК НАЙДЕН!*\n\n"
            "💬 *Можете начинать общение!*\n\n"
            "📋 *Доступные команды:*\n"
            "• Напишите что-нибудь — отправится собеседнику\n"
            "• /next — найти нового собеседника\n"
            "• /stop — завершить диалог\n"
            "• /profile — ваш профиль\n"
            "• /search — начать поиск\n\n"
            "✨ *Приятного общения!*"
        )
        
        bot.send_message(
            user_id,
            message,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
        print(f"📨 Уведомление отправлено пользователю {user_id}")
        
    except Exception as e:
        print(f"❌ Ошибка уведомления: {e}")

# ======== КОМАНДА /START ========
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    
    # Очищаем предыдущие состояния
    cleanup_user(user_id)
    
    # Главное меню с кнопками
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
    btn_profile = types.InlineKeyboardButton('👤 Мой профиль', callback_data='profile')
    btn_help = types.InlineKeyboardButton('❓ Помощь', callback_data='help')
    btn_stats = types.InlineKeyboardButton('📊 Статистика', callback_data='stats')
    markup.add(btn_search, btn_profile, btn_help, btn_stats)
    
    bot.send_message(
        user_id,
        "👋 *Добро пожаловать в анонимный чат!*\n\n"
        "🎭 *Общайтесь анонимно с людьми со всего мира.*\n\n"
        "⚡ *Быстрый старт:*",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['search'])
def search_command(message):
    user_id = message.chat.id
    
    if user_id in active_pairs:
        show_active_chat_buttons(user_id, "❌ У тебя уже есть собеседник!")
        return
    
    if user_id in search_queue:
        show_search_buttons(user_id, "⏳ Ты уже в очереди поиска...")
        return
    
    # Добавляем в поиск
    search_queue.append(user_id)
    show_search_buttons(
        user_id, 
        f"🔍 *Ищем собеседника...*\n\n"
        f"📊 *Позиция в очереди:* {len(search_queue)}\n"
        f"⏱️ *Ожидайте соединения...*"
    )

@bot.message_handler(commands=['next'])
def next_command(message):
    user_id = message.chat.id
    
    if user_id not in active_pairs:
        show_start_buttons(user_id, "❌ У тебя нет активного собеседника.")
        return
    
    partner_id = active_pairs[user_id]
    
    # Уведомляем партнёра
    show_start_buttons(
        partner_id,
        "⚠️ *Твой собеседник покинул диалог.*\n"
        "Можешь найти нового:"
    )
    
    # Удаляем пару
    cleanup_user(user_id)
    
    # Инициатор ищет нового
    search_queue.append(user_id)
    show_search_buttons(
        user_id,
        f"🔄 *Ищем нового собеседника...*\n\n"
        f"📊 *Позиция в очереди:* {len(search_queue)}"
    )

@bot.message_handler(commands=['stop'])
def stop_command(message):
    user_id = message.chat.id
    
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        show_start_buttons(
            partner_id,
            "❌ *Собеседник завершил диалог.*\n"
            "Можешь найти нового:"
        )
    
    cleanup_user(user_id)
    show_start_buttons(
        user_id,
        "✅ *Диалог завершён.*\n"
        "Найди нового собеседника:"
    )

@bot.message_handler(commands=['profile'])
def profile_command(message):
    user_id = message.chat.id
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_name = types.InlineKeyboardButton('✏️ Имя', callback_data='set_name')
    btn_gender = types.InlineKeyboardButton('🚻 Пол', callback_data='set_gender')
    btn_age = types.InlineKeyboardButton('🎂 Возраст', callback_data='set_age')
    btn_back = types.InlineKeyboardButton('🔙 Назад', callback_data='back')
    markup.add(btn_name, btn_gender, btn_age, btn_back)
    
    bot.send_message(
        user_id,
        "👤 *Ваш профиль*\n\n"
        "📛 *Имя:* Аноним\n"
        "🚻 *Пол:* Не указан\n"
        "🎂 *Возраст:* Не указан\n\n"
        "⚙️ *Настройки:*",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# ======== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ========
def cleanup_user(user_id):
    """Очищает данные пользователя"""
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        if partner_id in active_pairs:
            del active_pairs[partner_id]
        del active_pairs[user_id]
    
    if user_id in search_queue:
        search_queue.remove(user_id)

def show_start_buttons(user_id, text):
    """Показывает главные кнопки"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search')
    btn_profile = types.InlineKeyboardButton('👤 Профиль', callback_data='profile')
    btn_help = types.InlineKeyboardButton('❓ Помощь', callback_data='help')
    markup.add(btn_search, btn_profile, btn_help)
    
    bot.send_message(user_id, text, reply_markup=markup, parse_mode="Markdown")

def show_search_buttons(user_id, text):
    """Показывает кнопки поиска"""
    markup = types.InlineKeyboardMarkup()
    btn_cancel = types.InlineKeyboardButton('❌ Отменить поиск', callback_data='cancel')
    markup.add(btn_cancel)
    
    bot.send_message(user_id, text, reply_markup=markup, parse_mode="Markdown")

def show_active_chat_buttons(user_id, text):
    """Показывает кнопки активного чата"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_next = types.InlineKeyboardButton('🔄 Следующий', callback_data='next')
    btn_stop = types.InlineKeyboardButton('⛔ Стоп', callback_data='stop')
    btn_profile = types.InlineKeyboardButton('👤 Профиль', callback_data='profile')
    btn_help = types.InlineKeyboardButton('❓ Помощь', callback_data='help')
    markup.add(btn_next, btn_stop, btn_profile, btn_help)
    
    bot.send_message(user_id, text, reply_markup=markup, parse_mode="Markdown")

# ======== ОБРАБОТКА СООБЩЕНИЙ ========
@bot.message_handler(func=lambda msg: True)
def handle_messages(message):
    user_id = message.chat.id
    
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        try:
            # Пересылаем сообщение
            bot.send_message(partner_id, message.text)
        except Exception as e:
            print(f"❌ Ошибка пересылки: {e}")
    
    elif user_id in search_queue:
        position = search_queue.index(user_id) + 1
        show_search_buttons(
            user_id,
            f"⏳ *Ты всё ещё в поиске...*\n\n"
            f"📊 *Позиция в очереди:* {position}\n"
            f"💭 *Совет:* Наберитесь терпения!"
        )
    
    else:
        show_start_buttons(
            user_id,
            "🤔 *Кажется, ты не в диалоге...*\n"
            "Хочешь найти собеседника?"
        )

# ======== ОБРАБОТКА INLINE-КНОПОК ========
@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    user_id = call.message.chat.id
    command = call.data
    
    # Удаляем старое сообщение с кнопками
    try:
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    
    if command == 'search':
        search_command(call.message)
        bot.answer_callback_query(call.id, "🔍 Начинаем поиск...")
        
    elif command == 'cancel':
        if user_id in search_queue:
            search_queue.remove(user_id)
        show_start_buttons(user_id, "✅ *Поиск отменён.*")
        bot.answer_callback_query(call.id, "✅ Поиск отменён")
        
    elif command == 'next':
        next_command(call.message)
        bot.answer_callback_query(call.id, "🔄 Ищем следующего...")
        
    elif command == 'stop':
        stop_command(call.message)
        bot.answer_callback_query(call.id, "✅ Диалог завершён")
        
    elif command == 'profile':
        profile_command(call.message)
        bot.answer_callback_query(call.id, "👤 Профиль")
        
    elif command == 'help':
        bot.send_message(
            user_id,
            "❓ *Помощь по командам*\n\n"
            "*/start* - Главное меню\n"
            "*/search* - Найти собеседника\n"
            "*/next* - Следующий собеседник\n"
            "*/stop* - Завершить диалог\n"
            "*/profile* - Мой профиль\n\n"
            "📌 *Как пользоваться:*\n"
            "1. Нажми 'Начать поиск'\n"
            "2. Дождись соединения\n"
            "3. Общайся анонимно\n"
            "4. Используй /next для нового собеседника\n\n"
            "📢 *Приглашай друзей:* @OnonChatTg_Bot",
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, "📖 Помощь")
        
    elif command == 'stats':
        bot.send_message(
            user_id,
            f"📊 *Статистика*\n\n"
            f"👥 *В поиске:* {len(search_queue)}\n"
            f"💬 *Активных диалогов:* {len(active_pairs)//2}\n"
            f"🌐 *Всего пользователей:* Неизвестно\n\n"
            f"✨ *Бот работает стабильно!*",
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, "📊 Статистика")
        
    elif command == 'back':
        start(call.message)
        bot.answer_callback_query(call.id, "🔙 Назад")
        
    elif command == 'set_name':
        bot.send_message(user_id, "✏️ *Введите ваше имя:*", parse_mode="Markdown")
        bot.answer_callback_query(call.id, "✏️ Имя")
        
    elif command == 'set_gender':
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_male = types.InlineKeyboardButton('👨 Мужской', callback_data='gender_male')
        btn_female = types.InlineKeyboardButton('👩 Женский', callback_data='gender_female')
        btn_other = types.InlineKeyboardButton('🌈 Другой', callback_data='gender_other')
        btn_back = types.InlineKeyboardButton('🔙 Назад', callback_data='back')
        markup.add(btn_male, btn_female, btn_other, btn_back)
        
        bot.send_message(
            user_id,
            "🚻 *Выберите ваш пол:*",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, "🚻 Пол")

# ======== ЗАПУСК ========
if __name__ == "__main__":
    print("="*50)
    print("🤖 АНОНИМНЫЙ ЧАТ ЗАПУЩЕН")
    print("="*50)
    print(f"📊 Пользователей в поиске: {len(search_queue)}")
    print(f"💬 Активных диалогов: {len(active_pairs)//2}")
    print("="*50)
    
    # Ждём перед запуском
    time.sleep(3)
    
    try:
        bot.polling(none_stop=True, skip_pending=True, interval=1, timeout=30)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("🔄 Перезапуск через 10 секунд...")
        time.sleep(10)
