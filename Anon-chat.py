import os
import telebot
from telebot import types
import threading
import time
import random
from datetime import datetime

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = "8236249109:AAFkiU0aYJBYgY12ZwO4ZJFk1M2ZavOJbIE"
bot = telebot.TeleBot(TOKEN)

# ==================== ХРАНИЛИЩА ДАННЫХ ====================
search_queue = []          # Очередь поиска
active_pairs = {}          # Текущие пары {user1: user2, user2: user1}
user_data = {}             # Данные пользователей {id: {'name': '', 'gender': '', 'age': 0}}
message_history = {}       # История сообщений {user_id: [messages]}
waiting_for_gender = {}    # Ожидание выбора пола
waiting_for_age = {}       # Ожидание ввода возраста

# ==================== СТАТИСТИКА ====================
stats = {
    'total_users': 0,
    'total_connections': 0,
    'active_chats': 0,
    'messages_exchanged': 0
}

# ==================== УЛУЧШЕНИЯ ====================
TOPICS = [
    "🎬 Фильмы и сериалы",
    "🎵 Музыка",
    "🎮 Игры",
    "📚 Книги",
    "🏀 Спорт",
    "🍕 Еда",
    "✈️ Путешествия",
    "💻 Технологии",
    "🐶 Животные",
    "🎨 Искусство"
]

COMPLIMENTS = [
    "Ты отличный собеседник! 😊",
    "С тобой приятно общаться! 🌟",
    "У тебя хорошее чувство юмора! 😄",
    "Интересные мысли! 💭",
    "Рад нашему разговору! 🤝"
]

# ==================== СИСТЕМНЫЕ ФУНКЦИИ ====================
def print_stats():
    """Вывод статистики в консоль"""
    print(f"\n{'='*40}")
    print(f"📊 СТАТИСТИКА БОТА")
    print(f"👥 Всего пользователей: {stats['total_users']}")
    print(f"🔗 Всего соединений: {stats['total_connections']}")
    print(f"💬 Активных чатов: {stats['active_chats']}")
    print(f"📨 Обмен сообщений: {stats['messages_exchanged']}")
    print(f"⏳ В очереди поиска: {len(search_queue)}")
    print(f"{'='*40}\n")

def save_message(user_id, text, sender="user"):
    """Сохранение истории сообщений"""
    if user_id not in message_history:
        message_history[user_id] = []
    
    message_history[user_id].append({
        'text': text,
        'sender': sender,
        'time': datetime.now().strftime("%H:%M:%S")
    })
    
    # Ограничиваем историю последними 50 сообщениями
    if len(message_history[user_id]) > 50:
        message_history[user_id] = message_history[user_id][-50:]
    
    stats['messages_exchanged'] += 1

def get_user_profile(user_id):
    """Получение профиля пользователя"""
    if user_id not in user_data:
        user_data[user_id] = {
            'name': f"Аноним #{user_id % 10000:04d}",
            'gender': 'не указан',
            'age': 0,
            'join_date': datetime.now().strftime("%d.%m.%Y"),
            'connections': 0
        }
        stats['total_users'] += 1
    return user_data[user_id]

# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================
def send_match_message(user_id, partner_id):
    """Отправка сообщения о найденном собеседнике"""
    try:
        # Получаем данные пользователей
        user_profile = get_user_profile(user_id)
        partner_profile = get_user_profile(partner_id)
        
        # Создаём клавиатуру
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_next = types.InlineKeyboardButton('🔄 Следующий', callback_data='next_chat')
        btn_stop = types.InlineKeyboardButton('⛔ Стоп', callback_data='stop_chat')
        btn_topics = types.InlineKeyboardButton('💬 Темы для разговора', callback_data='suggest_topics')
        markup.add(btn_next, btn_stop, btn_topics)
        
        # Собираем информацию о собеседнике
        partner_info = ""
        if partner_profile['gender'] != 'не указан' or partner_profile['age'] > 0:
            partner_info = "\n\n👤 *Информация о собеседнике:*\n"
            if partner_profile['gender'] != 'не указан':
                partner_info += f"• Пол: {partner_profile['gender']}\n"
            if partner_profile['age'] > 0:
                partner_info += f"• Возраст: {partner_profile['age']}\n"
        
        # Тема для разговора
        topic = random.choice(TOPICS)
        
        # Сообщение
        message_text = (
            f"✅ *Собеседник найден!*\n\n"
            f"🎯 *Тема для разговора:* {topic}\n"
            f"💡 *Совет:* Начните с приветствия и представьтесь!\n"
            f"{partner_info}\n"
            f"📋 *Доступные команды:*\n"
            f"🔄 `/next` — следующий собеседник\n"
            f"⛔ `/stop` — остановить диалог\n"
            f"👤 `/profile` — мой профиль\n"
            f"💬 `/topics` — темы для разговора\n\n"
            f"📢 *Приглашай друзей:* @OnonChatTg_Bot"
        )
        
        # Отправляем
        bot.send_message(
            user_id,
            message_text,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
        # Добавляем комплимент (случайно)
        if random.random() < 0.3:  # 30% шанс
            time.sleep(1)
            bot.send_message(
                user_id,
                f"🌟 *Бонус:* {random.choice(COMPLIMENTS)}",
                parse_mode="Markdown"
            )
        
        # Сохраняем в историю
        save_message(user_id, "Система: Собеседник найден!", "system")
        
        print(f"📨 Сообщение о соединении отправлено пользователю {user_id}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка отправки match_message: {e}")
        return False

def connect_users():
    """Поиск и соединение пользователей"""
    while True:
        try:
            if len(search_queue) >= 2:
                user1 = search_queue.pop(0)
                user2 = search_queue.pop(0)
                
                # Проверяем, что пользователи не в другой паре
                if user1 not in active_pairs and user2 not in active_pairs:
                    # Соединяем
                    active_pairs[user1] = user2
                    active_pairs[user2] = user1
                    
                    # Обновляем статистику
                    user_data[user1]['connections'] = user_data[user1].get('connections', 0) + 1
                    user_data[user2]['connections'] = user_data[user2].get('connections', 0) + 1
                    stats['total_connections'] += 1
                    stats['active_chats'] += 1
                    
                    print(f"🔗 Соединены: {user1} ↔ {user2}")
                    print_stats()
                    
                    # Отправляем уведомления
                    send_match_message(user1, user2)
                    send_match_message(user2, user1)
                    
        except Exception as e:
            print(f"❌ Ошибка в connect_users: {e}")
        
        time.sleep(1)

# ==================== ОБРАБОТЧИКИ КОМАНД ====================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    profile = get_user_profile(user_id)
    
    # Очищаем предыдущие состояния
    cleanup_user(user_id)
    
    # Приветственное сообщение
    welcome_text = (
        f"👋 *Привет, {profile['name']}!*\n\n"
        f"🎭 *Анонимный чат* — общайся без границ!\n\n"
        f"✨ *Особенности:*\n"
        f"• Анонимное общение\n"
        f"• Быстрый поиск собеседников\n"
        f"• Темы для разговора\n"
        f"• Безопасно и конфиденциально\n\n"
        f"📌 *Как начать:*\n"
        f"1. Настрой профиль (/profile)\n"
        f"2. Найди собеседника (/search)\n"
        f"3. Общайся и находи друзей!\n\n"
        f"⚡ *Быстрый старт:*"
    )
    
    # Клавиатура
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_search = types.InlineKeyboardButton('🔍 Найти собеседника', callback_data='start_search')
    btn_profile = types.InlineKeyboardButton('👤 Мой профиль', callback_data='my_profile')
    btn_stats = types.InlineKeyboardButton('📊 Статистика', callback_data='show_stats')
    btn_help = types.InlineKeyboardButton('❓ Помощь', callback_data='show_help')
    markup.add(btn_search, btn_profile, btn_stats, btn_help)
    
    bot.send_message(
        user_id,
        welcome_text,
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    save_message(user_id, "Система: Бот запущен", "system")

@bot.message_handler(commands=['profile'])
def profile_command(message):
    user_id = message.chat.id
    profile = get_user_profile(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_name = types.InlineKeyboardButton('✏️ Изменить имя', callback_data='change_name')
    btn_gender = types.InlineKeyboardButton('🚻 Указать пол', callback_data='set_gender')
    btn_age = types.InlineKeyboardButton('🎂 Указать возраст', callback_data='set_age')
    btn_back = types.InlineKeyboardButton('🔙 Назад', callback_data='main_menu')
    markup.add(btn_name, btn_gender, btn_age, btn_back)
    
    profile_text = (
        f"👤 *Твой профиль*\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"📛 Имя: *{profile['name']}*\n"
        f"🚻 Пол: *{profile['gender']}*\n"
        f"🎂 Возраст: *{profile['age'] if profile['age'] > 0 else 'не указан'}*\n"
        f"📅 С нами с: *{profile['join_date']}*\n"
        f"🔗 Диалогов: *{profile['connections']}*\n\n"
        f"⚙️ *Настройки:*"
    )
    
    bot.send_message(
        user_id,
        profile_text,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['search'])
def search_command(message):
    user_id = message.chat.id
    
    if user_id in active_pairs:
        bot.send_message(user_id, "❌ У тебя уже есть собеседник! Используй /stop чтобы завершить текущий диалог.")
        return
    
    if user_id in search_queue:
        bot.send_message(user_id, "⏳ Ты уже в очереди поиска...")
        return
    
    # Добавляем в поиск
    search_queue.append(user_id)
    
    # Показываем статус
    markup = types.InlineKeyboardMarkup()
    btn_stop = types.InlineKeyboardButton('⛔ Отменить поиск', callback_data='stop_search')
    markup.add(btn_stop)
    
    position = len(search_queue)
    bot.send_message(
        user_id,
        f"🔍 *Ищем собеседника...*\n\n"
        f"📊 Твоя позиция в очереди: *{position}*\n"
        f"⏱️ Ожидайте соединения...",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    save_message(user_id, f"Система: Начат поиск (позиция {position})", "system")

@bot.message_handler(commands=['next'])
def next_command(message):
    user_id = message.chat.id
    
    if user_id not in active_pairs:
        bot.send_message(
            user_id,
            "❌ У тебя нет активного собеседника.\n"
            "Используй /search чтобы найти нового."
        )
        return
    
    # Ищем нового собеседника
    switch_partner(user_id)

@bot.message_handler(commands=['stop'])
def stop_command(message):
    user_id = message.chat.id
    cleanup_user(user_id, notify_partner=True)
    
    markup = types.InlineKeyboardMarkup()
    btn_search = types.InlineKeyboardButton('🔍 Найти нового', callback_data='start_search')
    markup.add(btn_search)
    
    bot.send_message(
        user_id,
        "✅ *Диалог завершён.*\n\n"
        "Надеюсь, общение было приятным! 🥰\n"
        "Можешь найти нового собеседника:",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    save_message(user_id, "Система: Диалог завершён", "system")

@bot.message_handler(commands=['topics'])
def topics_command(message):
    user_id = message.chat.id
    
    topics_list = "\n".join([f"• {topic}" for topic in TOPICS])
    
    bot.send_message(
        user_id,
        f"💬 *Темы для разговора:*\n\n{topics_list}\n\n"
        f"🎯 *Совет:* Выбери тему и задай вопрос собеседнику!",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['stats'])
def stats_command(message):
    user_id = message.chat.id
    profile = get_user_profile(user_id)
    
    stats_text = (
        f"📊 *Твоя статистика*\n\n"
        f"👤 Имя: *{profile['name']}*\n"
        f"🔗 Диалогов: *{profile['connections']}*\n"
        f"📅 С нами с: *{profile['join_date']}*\n\n"
        f"🌐 *Общая статистика бота:*\n"
        f"👥 Пользователей: *{stats['total_users']}*\n"
        f"💬 Активных чатов: *{stats['active_chats']}*\n"
        f"📨 Сообщений: *{stats['messages_exchanged']}*\n"
        f"🔗 Всего соединений: *{stats['total_connections']}*"
    )
    
    bot.send_message(user_id, stats_text, parse_mode="Markdown")

# ==================== ОБРАБОТЧИКИ СООБЩЕНИЙ ====================
@bot.message_handler(func=lambda msg: True, content_types=['text', 'photo', 'voice', 'video', 'document', 'sticker', 'audio'])
def handle_messages(message):
    user_id = message.chat.id
    
    # Обработка ввода имени/возраста/пола
    if user_id in waiting_for_gender:
        handle_gender_input(message)
        return
    elif user_id in waiting_for_age:
        handle_age_input(message)
        return
    
    # Если пользователь в активной паре - пересылаем сообщение
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        
        # Сохраняем сообщение
        if message.text:
            save_message(user_id, message.text, "user")
            
            # Пересылаем партнёру
            try:
                # Если есть имя, добавляем его
                user_profile = get_user_profile(user_id)
                if user_profile['name'].startswith('Аноним'):
                    forwarded_text = message.text
                else:
                    forwarded_text = f"*{user_profile['name']}:*\n{message.text}"
                
                bot.send_message(partner_id, forwarded_text, parse_mode="Markdown")
                save_message(partner_id, f"Собеседник: {message.text}", "partner")
                
                # Случайный комплимент (1% шанс)
                if random.random() < 0.01 and len(message.text) > 10:
                    time.sleep(0.5)
                    bot.send_message(user_id, f"💫 {random.choice(COMPLIMENTS)}")
                    
            except Exception as e:
                print(f"❌ Ошибка пересылки: {e}")
        
        # Обработка медиа
        elif message.content_type in ['photo', 'voice', 'video', 'document', 'sticker', 'audio']:
            try:
                forward_media(message, partner_id)
            except Exception as e:
                print(f"❌ Ошибка пересылки медиа: {e}")
    
    # Если пользователь в поиске
    elif user_id in search_queue:
        position = search_queue.index(user_id) + 1 if user_id in search_queue else 0
        bot.send_message(
            user_id,
            f"⏳ *Ты всё ещё в поиске...*\n"
            f"Позиция в очереди: *{position}*\n\n"
            f"Наберись терпения! Скоро найдём собеседника 😊",
            parse_mode="Markdown"
        )
    
    # Если пользователь ничего не делает
    else:
        markup = types.InlineKeyboardMarkup()
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='start_search')
        markup.add(btn_search)
        
        bot.send_message(
            user_id,
            "🤔 *Кажется, ты не в диалоге...*\n\n"
            "Хочешь найти собеседника для анонимного общения?",
            reply_markup=markup,
            parse_mode="Markdown"
        )

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def forward_media(message, partner_id):
    """Пересылка медиафайлов"""
    if message.photo:
        bot.send_photo(partner_id, message.photo[-1].file_id, caption=message.caption)
    elif message.voice:
        bot.send_voice(partner_id, message.voice.file_id)
    elif message.video:
        bot.send_video(partner_id, message.video.file_id, caption=message.caption)
    elif message.document:
        bot.send_document(partner_id, message.document.file_id, caption=message.caption)
    elif message.sticker:
        bot.send_sticker(partner_id, message.sticker.file_id)
    elif message.audio:
        bot.send_audio(partner_id, message.audio.file_id, caption=message.caption)

def cleanup_user(user_id, notify_partner=False):
    """Очистка данных пользователя"""
    # Уведомляем партнёра
    if user_id in active_pairs and notify_partner:
        partner_id = active_pairs[user_id]
        if partner_id in active_pairs:
            del active_pairs[partner_id]
            
            markup = types.InlineKeyboardMarkup()
            btn_search = types.InlineKeyboardButton('🔍 Найти нового', callback_data='start_search')
            markup.add(btn_search)
            
            bot.send_message(
                partner_id,
                "⚠️ *Собеседник покинул диалог.*\n\n"
                "Можешь найти нового собеседника:",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            
            stats['active_chats'] = max(0, stats['active_chats'] - 1)
    
    # Удаляем из активных пар
    if user_id in active_pairs:
        del active_pairs[user_id]
        stats['active_chats'] = max(0, stats['active_chats'] - 1)
    
    # Удаляем из очереди
    if user_id in search_queue:
        search_queue.remove(user_id)
    
    # Очищаем временные данные
    if user_id in waiting_for_gender:
        del waiting_for_gender[user_id]
    if user_id in waiting_for_age:
        del waiting_for_age[user_id]

def switch_partner(user_id):
    """Поиск нового собеседника"""
    if user_id not in active_pairs:
        return
    
    partner_id = active_pairs[user_id]
    
    # Уведомляем старого партнёра
    markup = types.InlineKeyboardMarkup()
    btn_search = types.InlineKeyboardButton('🔍 Найти нового', callback_data='start_search')
    markup.add(btn_search)
    
    bot.send_message(
        partner_id,
        "🔄 *Твой собеседник ищет нового партнёра.*\n\n"
        "Можешь тоже найти нового собеседника:",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    
    # Удаляем старую пару
    cleanup_user(user_id, notify_partner=False)
    
    # Добавляем в поиск
    search_queue.append(user_id)
    
    # Уведомляем
    markup = types.InlineKeyboardMarkup()
    btn_stop = types.InlineKeyboardButton('⛔ Отменить поиск', callback_data='stop_search')
    markup.add(btn_stop)
    
    position = len(search_queue)
    bot.send_message(
        user_id,
        f"🔄 *Ищем нового собеседника...*\n\n"
        f"📊 Позиция в очереди: *{position}*\n"
        f"⏱️ Ожидайте...",
        reply_markup=markup,
        parse_mode="Markdown"
    )

def handle_gender_input(message):
    """Обработка выбора пола"""
    user_id = message.chat.id
    text = message.text.lower()
    
    gender_map = {
        'м': 'мужской', 'муж': 'мужской', 'парень': 'мужской', 'мальчик': 'мужской',
        'ж': 'женский', 'жен': 'женский', 'девушка': 'женский', 'девочка': 'женский',
        'другой': 'другой', 'не скажу': 'не указан'
    }
    
    if text in gender_map:
        gender = gender_map[text]
        user_data[user_id]['gender'] = gender
        
        # Спрашиваем возраст
        waiting_for_age[user_id] = True
        del waiting_for_gender[user_id]
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        btn_skip = types.KeyboardButton('Пропустить')
        markup.add(btn_skip)
        
        bot.send_message(
            user_id,
            f"✅ Пол сохранён: *{gender}*\n\n"
            f"🎂 *Сколько тебе лет?*\n"
            f"Напиши число от 12 до 100\n"
            f"Или нажми 'Пропустить'",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    else:
        bot.send_message(
            user_id,
            "❌ Не понял твой ответ.\n\n"
            "Выбери один из вариантов:\n"
            "• Мужской\n"
            "• Женский\n"
            "• Другой\n"
            "• Не скажу"
        )

def handle_age_input(message):
    """Обработка ввода возраста"""
    user_id = message.chat.id
    text = message.text
    
    if text.lower() in ['пропустить', 'skip', 'не скажу']:
        user_data[user_id]['age'] = 0
        bot.send_message(
            user_id,
            "✅ Профиль обновлён! Теперь можно искать собеседников.",
            reply_markup=types.ReplyKeyboardRemove()
        )
    elif text.isdigit() and 12 <= int(text) <= 100:
        age = int(text)
        user_data[user_id]['age'] = age
        bot.send_message(
            user_id,
            f"✅ Возраст сохранён: *{age} лет*\n\n"
            f"🎉 *Профиль готов!*\n"
            f"Теперь можно искать собеседников 😊",
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode="Markdown"
        )
    else:
        bot.send_message(
            user_id,
            "❌ Пожалуйста, введи число от 12 до 100\n"
            "Или нажми 'Пропустить'"
        )
    
    del waiting_for_age[user_id]

# ==================== ОБРАБОТЧИКИ INLINE-КНОПОК ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.message.chat.id
    
    try:
        # Удаляем предыдущее сообщение с кнопками
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    
    if call.data == 'start_search':
        search_command(call.message)
        
    elif call.data == 'stop_search':
        if user_id in search_queue:
            search_queue.remove(user_id)
        bot.answer_callback_query(call.id, "✅ Поиск отменён")
        start(call.message)
        
    elif call.data == 'next_chat':
        next_command(call.message)
        bot.answer_callback_query(call.id, "🔄 Ищем нового собеседника...")
        
    elif call.data == 'stop_chat':
        stop_command(call.message)
        bot.answer_callback_query(call.id, "✅ Диалог завершён")
        
    elif call.data == 'suggest_topics':
        topic = random.choice(TOPICS)
        bot.send_message(
            user_id,
            f"💡 *Предлагаю тему:*\n\n"
            f"**{topic}**\n\n"
            f"*Вопрос для собеседника:*\n"
            f"Что ты думаешь об этом?",
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, "💬 Тема предложена")
        
    elif call.data == 'my_profile':
        profile_command(call.message)
        
    elif call.data == 'show_stats':
        stats_command(call.message)
        
    elif call.data == 'show_help':
        help_text = (
            "❓ *Помощь по командам*\n\n"
            "*/start* - Главное меню\n"
            "*/search* - Найти собеседника\n"
            "*/next* - Следующий собеседник\n"
            "*/stop* - Завершить диалог\n"
            "*/profile* - Мой профиль\n"
            "*/topics* - Темы для разговора\n"
            "*/stats* - Статистика\n\n"
            "📌 *Советы:*\n"
            "• Будь вежлив и уважай других\n"
            "• Не отправляй личные данные\n"
            "• Используй /stop если диалог не складывается\n"
            "• Приглашай друзей: @OnonChatTg_Bot"
        )
        bot.send_message(user_id, help_text, parse_mode="Markdown")
        bot.answer_callback_query(call.id, "📖 Помощь")
        
    elif call.data == 'main_menu':
        start(call.message)
        
    elif call.data == 'change_name':
        bot.send_message(
            user_id,
            "✏️ *Придумай себе имя:*\n\n"
            "Напиши, как тебя называть в чате\n"
            "(Максимум 20 символов)",
            parse_mode="Markdown"
        )
        # Здесь можно добавить ожидание ввода имени
        
    elif call.data == 'set_gender':
        waiting_for_gender[user_id] = True
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        btn_male = types.KeyboardButton('Мужской')
        btn_female = types.KeyboardButton('Женский')
        btn_other = types.KeyboardButton('Другой')
        btn_skip = types.KeyboardButton('Не скажу')
        markup.add(btn_male, btn_female, btn_other, btn_skip)
        
        bot.send_message(
            user_id,
            "🚻 *Выбери свой пол:*",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
    elif call.data == 'set_age':
        waiting_for_age[user_id] = True
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        btn_skip = types.KeyboardButton('Пропустить')
        markup.add(btn_skip)
        
        bot.send_message(
            user_id,
            "🎂 *Сколько тебе лет?*\n\n"
            "Напиши число от 12 до 100\n"
            "Или нажми 'Пропустить'",
            reply_markup=markup,
            parse_mode="Markdown"
        )

# ==================== ЗАПУСК СИСТЕМЫ ====================
if __name__ == "__main__":
    # Запускаем поток для соединения пользователей
    connect_thread = threading.Thread(target=connect_users, daemon=True)
    connect_thread.start()
    
    print("="*50)
    print("🤖 АНОНИМНЫЙ ЧАТ-БОТ ЗАПУЩЕН")
    print("="*50)
    print_stats()
    
    # Периодический вывод статистики
    def stats_monitor():
        while True:
            time.sleep(300)  # Каждые 5 минут
            print_stats()
    
    monitor_thread = threading.Thread(target=stats_monitor, daemon=True)
    monitor_thread.start()
    
    # Запуск бота
    try:
        bot.polling(none_stop=True, interval=1, timeout=30)
        print("✅ Бот успешно запущен")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        print("Попытка перезапуска через 10 секунд...")
        time.sleep(10)
