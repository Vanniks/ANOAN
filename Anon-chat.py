import os
import telebot
from telebot import types
import time
import threading
import requests

TOKEN = "8236249109:AAFkiU0aYJBYgY12ZwO4ZJFk1M2ZavOJbIE"
bot = telebot.TeleBot(TOKEN)

# ======== Flask для Render ========
try:
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return "✅ Анонимный чат-бот работает!"
        
    @app.route('/health')
    def health():
        return "OK", 200
        
except ImportError:
    print("⚠️ Flask не установлен")
    app = None

# ======== ВАШ ОСНОВНОЙ КОД ========
search_queue = []
active_pairs = {}

# ======== ВАЖНО: УДАЛЯЕМ СТАРЫЕ UPDATES ПЕРЕД ЗАПУСКОМ ========
def cleanup_before_start():
    """Удаляет все pending updates и webhook перед запуском"""
    try:
        # 1. Удаляем webhook если есть
        webhook_url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook"
        response = requests.get(webhook_url, params={"drop_pending_updates": True})
        print(f"🗑️ Удаление webhook: {response.status_code}")
        
        # 2. Получаем последний update_id
        updates_url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        response = requests.get(updates_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('result'):
                last_update = data['result'][-1]['update_id']
                # 3. Подтверждаем все updates
                confirm_url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
                requests.get(confirm_url, params={"offset": last_update + 1})
                print(f"✅ Подтверждены updates до #{last_update}")
        
        # 4. Ждем 2 секунды
        time.sleep(2)
        
    except Exception as e:
        print(f"⚠️ Ошибка cleanup: {e}")

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
                    
                    print(f"✅ СОЕДИНЕНО: {user1} ↔️ {user2}")
                    send_match_notification(user1)
                    send_match_notification(user2)
        except Exception as e:
            print(f"⚠️ Ошибка поиска: {e}")
        
        time.sleep(1)

def send_match_notification(user_id):
    """Отправляет уведомление о найденном собеседнике"""
    try:
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_next = types.InlineKeyboardButton('🔄 Следующий', callback_data='next')
        btn_stop = types.InlineKeyboardButton('⛔️ Стоп', callback_data='stop')
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
        
        bot.send_message(user_id, message, reply_markup=markup, parse_mode="Markdown")
        print(f"📨 Уведомление отправлено пользователю {user_id}")
        
    except Exception as e:
        print(f"❌ Ошибка уведомления: {e}")

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
    btn_stop = types.InlineKeyboardButton('⛔️ Стоп', callback_data='stop')
    btn_profile = types.InlineKeyboardButton('👤 Профиль', callback_data='profile')
    btn_help = types.InlineKeyboardButton('❓ Помощь', callback_data='help')
    markup.add(btn_next, btn_stop, btn_profile, btn_help)
    
    bot.send_message(user_id, text, reply_markup=markup, parse_mode="Markdown")

# ======== КОМАНДА /START ========
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    cleanup_user(user_id)
    
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
        "⚡️ *Быстрый старт:*",
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
    show_start_buttons(partner_id, "⚠️ *Твой собеседник покинул диалог.*\nМожешь найти нового:")
    cleanup_user(user_id)
    search_queue.append(user_id)
    show_search_buttons(user_id, f"🔄 *Ищем нового собеседника...*\n\n📊 *Позиция в очереди:* {len(search_queue)}")

@bot.message_handler(commands=['stop'])
def stop_command(message):
    user_id = message.chat.id
    
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        show_start_buttons(partner_id, "❌ *Собеседник завершил диалог.*\nМожешь найти нового:")
    
    cleanup_user(user_id)
    show_start_buttons(user_id, "✅ *Диалог завершён.*\nНайди нового собеседника:")

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
        "👤 *Ваш профиль*\n\n📛 *Имя:* Аноним\n🚻 *Пол:* Не указан\n🎂 *Возраст:* Не указан\n\n⚙️ *Настройки:*",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# ======== ОБРАБОТКА СООБЩЕНИЙ ========
@bot.message_handler(func=lambda msg: True)
def handle_messages(message):
    user_id = message.chat.id
    
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        try:
            bot.send_message(partner_id, message.text)
        except Exception as e:
            print(f"❌ Ошибка пересылки: {e}")
    
    elif user_id in search_queue:
        position = search_queue.index(user_id) + 1
        show_search_buttons(user_id, f"⏳ *Ты всё ещё в поиске...*\n\n📊 *Позиция в очереди:* {position}\n💭 *Совет:* Наберитесь терпения!")
    else:
        show_start_buttons(user_id, "🤔 *Кажется, ты не в диалоге...*\nХочешь найти собеседника?")

# ======== ОБРАБОТКА INLINE-КНОПОК ========
@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    user_id = call.message.chat.id
    command = call.data
    
    try:
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    
    # Создаем фиктивное сообщение для обработки
    class FakeMessage:
        def __init__(self, chat_id):
            self.chat = type('obj', (object,), {'id': chat_id})()
    
    fake_msg = FakeMessage(user_id)
    
    if command == 'search':
        search_command(fake_msg)
        bot.answer_callback_query(call.id, "🔍 Начинаем поиск...")
        
    elif command == 'cancel':
        if user_id in search_queue:
            search_queue.remove(user_id)
        show_start_buttons(user_id, "✅ *Поиск отменён.*")
        bot.answer_callback_query(call.id, "✅ Поиск отменён")
        
    elif command == 'next':
        next_command(fake_msg)
        bot.answer_callback_query(call.id, "🔄 Ищем следующего...")
        
    elif command == 'stop':
        stop_command(fake_msg)
        bot.answer_callback_query(call.id, "✅ Диалог завершён")
        
    elif command == 'profile':
        profile_command(fake_msg)
        bot.answer_callback_query(call.id, "👤 Профиль")
        
    elif command == 'help':
        bot.send_message(
            user_id,
            "❓ *Помощь по командам*\n\n*/start* - Главное меню\n*/search* - Найти собеседника\n*/next* - Следующий собеседник\n*/stop* - Завершить диалог\n*/profile* - Мой профиль\n\n📌 *Как пользоваться:*\n1. Нажми 'Начать поиск'\n2. Дождись соединения\n3. Общайся анонимно\n4. Используй /next для нового собеседника\n\n📢 *Приглашай друзей:* @OnonChatTg_Bot",
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, "📖 Помощь")
        
    elif command == 'stats':
        bot.send_message(
            user_id,
            f"📊 *Статистика*\n\n👥 *В поиске:* {len(search_queue)}\n💬 *Активных диалогов:* {len(active_pairs)//2}\n🌐 *Всего пользователей:* Неизвестно\n\n✨ *Бот работает стабильно!*",
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, "📊 Статистика")
        
    elif command == 'back':
        start(fake_msg)
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
        
        bot.send_message(user_id, "🚻 *Выберите ваш пол:*", reply_markup=markup, parse_mode="Markdown")
        bot.answer_callback_query(call.id, "🚻 Пол")
    
    elif command in ['gender_male', 'gender_female', 'gender_other']:
        genders = {'gender_male': '👨 Мужской', 'gender_female': '👩 Женский', 'gender_other': '🌈 Другой'}
        bot.send_message(user_id, f"✅ Ваш пол установлен: {genders[command]}")
        bot.answer_callback_query(call.id, "✅ Сохранено")

# ======== ЗАПУСК ========
if __name__ == "__main__":
    print("="*50)
    print("🤖 АНОНИМНЫЙ ЧАТ - ПОДГОТОВКА К ЗАПУСКУ")
    print("="*50)
    
    # 1. ОЧИСТКА ПЕРЕД ЗАПУСКОМ
    print("🧹 Очистка старых updates и webhook...")
    cleanup_before_start()
    
    # 2. ПРОВЕРКА БОТА
    try:
        bot_info_url = f"https://api.telegram.org/bot{TOKEN}/getMe"
        response = requests.get(bot_info_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Бот активен: @{data['result']['username']}")
        else:
            print(f"❌ Ошибка бота: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Не удалось проверить бота: {e}")
    
    # 3. ЗАПУСК ФОНОВЫХ ПРОЦЕССОВ
    print("🚀 Запуск фоновых процессов...")
    
    # Запускаем фоновый поиск
    search_thread = threading.Thread(target=background_search, daemon=True)
    search_thread.start()
    
    # Функция запуска бота с защитой от 409
    def safe_polling():
        """Безопасный polling с обработкой 409 ошибки"""
        max_retries = 5
        retry_delay = 10
        
        for attempt in range(max_retries):
            try:
                print(f"🔄 Попытка запуска polling #{attempt + 1}...")
                
                # Очищаем перед каждой попыткой
                cleanup_before_start()
                time.sleep(3)  # Ждем
                
                # Запускаем polling БЕЗ skip_updates
                print("🤖 Запускаем polling...")
                bot.polling(
                    none_stop=True,
                    interval=3,
                    timeout=30,
                    skip_pending=True,  # ВАЖНО: True вместо False
                    allowed_updates=["message", "callback_query"]
                )
                
            except Exception as e:
                error_msg = str(e)
                print(f"❌ Ошибка polling (попытка {attempt + 1}): {error_msg}")
                
                if "409" in error_msg or "Conflict" in error_msg:
                    print("⚠️ Обнаружен конфликт! Удаляем старые updates...")
                    cleanup_before_start()
                    
                    # Увеличиваем задержку с каждой попыткой
                    wait_time = retry_delay * (attempt + 1)
                    print(f"⏳ Ждем {wait_time} секунд перед повторной попыткой...")
                    time.sleep(wait_time)
                else:
                    print(f"⏳ Ждем {retry_delay} секунд перед повторной попыткой...")
                    time.sleep(retry_delay)
        
        print("🔥 Все попытки исчерпаны. Перезапуск через 30 секунд...")
        time.sleep(30)
        safe_polling()  # Рекурсивный перезапуск
    
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=safe_polling, daemon=True)
    bot_thread.start()
    
    print("✅ Фоновые процессы запущены")
    print(f"📊 В очереди: {len(search_queue)} | Активных пар: {len(active_pairs)//2}")
    print("="*50)
    
    # 4. ЗАПУСК FLASK ДЛЯ RENDER
    if app:
        try:
            port = int(os.environ.get("PORT", 10000))
            print(f"🌐 Запускаем Flask сервер на порту {port}...")
            # ВАЖНО: use_reloader=False чтобы не создавался второй процесс
            app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
        except Exception as e:
            print(f"⚠️ Ошибка Flask: {e}")
            # Держим основной поток активным
            while True:
                time.sleep(3600)
    else:
        print("⚠️ Flask не установлен, бот работает без web-интерфейса")
        while True:
            time.sleep(3600)
