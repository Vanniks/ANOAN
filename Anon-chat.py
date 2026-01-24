import os
import telebot
from telebot import types
import time
import threading
import requests
import shelve
from datetime import datetime, timedelta
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
        
    @app.route('/ping')
    def ping():
        return "pong", 200
        
except ImportError:
    logger.warning("Flask не установлен")
    app = None

# ======== НАСТРОЙКИ TELEGRAM STARS ========
# КУРС: 100 звёзд = 130 рублей
# Разработчик получает 70% от суммы

STAR_PACKAGES = {
    10: {"price": 1300, "label": "10 звёзд (13₽)", "rub_price": 13},
    50: {"price": 6500, "label": "50 звёзд (65₽)", "rub_price": 65},
    100: {"price": 13000, "label": "100 звёзд (130₽)", "rub_price": 130},
    250: {"price": 32500, "label": "250 звёзд (325₽)", "rub_price": 325},
    500: {"price": 65000, "label": "500 звёзд (650₽)", "rub_price": 650},
}

# Цены в звёздах для функций в боте
PREMIUM_PRICES = {
    'week': 50,      # 50 звёзд за неделю премиума
    'month': 180,    # 180 звёзд за месяц премиума
}

FEATURE_PRICES = {
    'gender_search': 30,    # 30 звёзд за поиск по полу (24 часа)
    'priority': 20,         # 20 звёзд за приоритет в очереди
    'unlimited': 100,       # 100 звёзд за безлимит на 24 часа
}

# ======== БАЗА ДАННЫХ ========
PROFILES_DB = "user_profiles.db"
CATEGORIES = {
    "💬 Общий чат": "general",
    "🎮 Игры": "games",
    "🎵 Музыка": "music",
    "🎬 Фильмы": "movies",
    "📚 Книги": "books",
    "💪 Спорт": "sport",
    "💕 Отношения": "relationships",
    "💼 Работа": "work",
    "🌍 Путешествия": "travel"
}

search_queue = []
active_pairs = {}
user_states = {}

# ======== АВТО-ПИНГ ДЛЯ RENDER ========
def keep_alive():
    """Периодически пингует себя чтобы Render не засыпал"""
    ping_interval = 8 * 60
    while True:
        try:
            requests.get("https://anoan-zqhd.onrender.com/ping", timeout=10)
            logger.info(f"Self-ping: {time.strftime('%H:%M:%S')}")
        except Exception as e:
            logger.error(f"Ping error: {e}")
        time.sleep(ping_interval)

# ======== ФУНКЦИИ ДЛЯ БАЗЫ ДАННЫХ ========
def get_user_profile(user_id):
    """Получает профиль пользователя"""
    with shelve.open(PROFILES_DB) as db:
        user_key = str(user_id)
        if user_key in db:
            return db[user_key]
        else:
            default_profile = {
                'name': 'Аноним',
                'gender': 'Не указан',
                'age': 0,
                'stars': 0,           # Виртуальные звёзды в боте
                'real_stars': 0,      # Купленные через Telegram
                'premium_until': None,
                'gender_search_until': None,
                'unlimited_until': None,
                'priority': False,    # Флаг приоритета
                'search_count': 0,
                'total_spent': 0,     # Всего потрачено звёзд
                'total_earned': 0,    # Всего заработано (в руб)
                'created_at': datetime.now().isoformat()
            }
            db[user_key] = default_profile
            return default_profile

def save_user_profile(user_id, profile_data):
    """Сохраняет профиль пользователя"""
    with shelve.open(PROFILES_DB) as db:
        db[str(user_id)] = profile_data

def update_profile_field(user_id, field, value):
    """Обновляет поле в профиле"""
    profile = get_user_profile(user_id)
    profile[field] = value
    save_user_profile(user_id, profile)

def get_user_stars(user_id):
    """Получает баланс звёзд"""
    profile = get_user_profile(user_id)
    return profile.get('stars', 0)

def add_stars(user_id, amount, is_real=False):
    """Добавляет звёзды"""
    profile = get_user_profile(user_id)
    profile['stars'] = profile.get('stars', 0) + amount
    if is_real:
        profile['real_stars'] = profile.get('real_stars', 0) + amount
        profile['total_spent'] = profile.get('total_spent', 0) + amount
        # Рассчитываем примерный заработок в рублях (70% от суммы)
        earned_rub = (amount * 130 / 100) * 0.7
        profile['total_earned'] = profile.get('total_earned', 0) + earned_rub
    save_user_profile(user_id, profile)
    logger.info(f"User {user_id} received {amount} stars (real: {is_real})")

def spend_stars(user_id, amount):
    """Тратит звёзды"""
    profile = get_user_profile(user_id)
    if profile.get('stars', 0) >= amount:
        profile['stars'] -= amount
        save_user_profile(user_id, profile)
        logger.info(f"User {user_id} spent {amount} stars")
        return True
    logger.warning(f"User {user_id} has insufficient stars: {profile.get('stars', 0)}/{amount}")
    return False

def is_premium(user_id):
    """Проверяет премиум статус"""
    profile = get_user_profile(user_id)
    if profile.get('premium_until'):
        try:
            premium_until = datetime.fromisoformat(profile['premium_until'])
            if premium_until > datetime.now():
                return True
            else:
                # Очищаем просроченный премиум
                update_profile_field(user_id, 'premium_until', None)
        except Exception as e:
            logger.error(f"Premium date error for user {user_id}: {e}")
            return False
    return False

def has_gender_search(user_id):
    """Проверяет доступен ли поиск по полу"""
    # Премиум пользователи имеют доступ всегда
    if is_premium(user_id):
        return True
    
    profile = get_user_profile(user_id)
    if profile.get('gender_search_until'):
        try:
            until = datetime.fromisoformat(profile['gender_search_until'])
            if until > datetime.now():
                return True
            else:
                # Очищаем просроченный доступ
                update_profile_field(user_id, 'gender_search_until', None)
        except Exception as e:
            logger.error(f"Gender search date error for user {user_id}: {e}")
            return False
    return False

def has_unlimited_search(user_id):
    """Проверяет безлимитный поиск"""
    profile = get_user_profile(user_id)
    if profile.get('unlimited_until'):
        try:
            until = datetime.fromisoformat(profile['unlimited_until'])
            if until > datetime.now():
                return True
            else:
                # Очищаем просроченный доступ
                update_profile_field(user_id, 'unlimited_until', None)
        except Exception as e:
            logger.error(f"Unlimited search date error for user {user_id}: {e}")
            return False
    return False

def has_priority(user_id):
    """Проверяет наличие приоритета"""
    profile = get_user_profile(user_id)
    return profile.get('priority', False)

# ======== ОЧИСТКА ПЕРЕД ЗАПУСКОМ ========
def cleanup_before_start():
    """Удаляет старые updates"""
    try:
        webhook_url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook"
        response = requests.get(webhook_url, params={"drop_pending_updates": True})
        logger.info(f"Удаление webhook: {response.status_code}")
        time.sleep(2)
    except Exception as e:
        logger.error(f"Ошибка cleanup: {e}")

# ======== ФУНКЦИЯ ФОНОВОГО ПОИСКА ========
def background_search():
    """Ищет пары в фоне"""
    while True:
        try:
            if len(search_queue) >= 2:
                # Проверяем совместимость
                for i in range(len(search_queue)):
                    for j in range(i + 1, len(search_queue)):
                        user1_data = search_queue[i]
                        user2_data = search_queue[j]
                        user1 = user1_data['user_id']
                        user2 = user2_data['user_id']
                        
                        # Проверяем категорию
                        if user1_data['category'] != user2_data['category']:
                            continue
                            
                        # Проверяем фильтр по полу если есть
                        if not check_gender_compatibility(user1_data, user2_data):
                            continue
                        
                        # Нашли пару
                        search_queue.pop(j)
                        search_queue.pop(i)
                        active_pairs[user1] = user2
                        active_pairs[user2] = user1
                        
                        logger.info(f"Соединено: {user1} ↔️ {user2}")
                        
                        # Отправляем уведомления
                        category_name = [k for k, v in CATEGORIES.items() if v == user1_data['category']][0]
                        notify_match(user1, user2, category_name)
                        
                        # Обновляем счётчики
                        update_profile_field(user1, 'search_count', get_user_profile(user1).get('search_count', 0) + 1)
                        update_profile_field(user2, 'search_count', get_user_profile(user2).get('search_count', 0) + 1)
                        
                        break
                    break
        except Exception as e:
            logger.error(f"Ошибка поиска: {e}")
        time.sleep(1)

def check_gender_compatibility(user1_data, user2_data):
    """Проверяет совместимость по полу"""
    if user1_data['gender_pref'] == 'any' and user2_data['gender_pref'] == 'any':
        return True
    
    # Получаем профили
    profile1 = get_user_profile(user1_data['user_id'])
    profile2 = get_user_profile(user2_data['user_id'])
    
    gender1 = profile1.get('gender', '')
    gender2 = profile2.get('gender', '')
    
    # Проверяем предпочтения
    if user1_data['gender_pref'] != 'any':
        if user1_data['gender_pref'] == 'male' and gender2 != 'Мужской':
            return False
        if user1_data['gender_pref'] == 'female' and gender2 != 'Женский':
            return False
    
    if user2_data['gender_pref'] != 'any':
        if user2_data['gender_pref'] == 'male' and gender1 != 'Мужской':
            return False
        if user2_data['gender_pref'] == 'female' and gender1 != 'Женский':
            return False
    
    return True

def notify_match(user1, user2, category_name):
    """Отправляет уведомления о найденной паре"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_next = types.InlineKeyboardButton('🔄 Следующий', callback_data='next')
    btn_stop = types.InlineKeyboardButton('⛔️ Стоп', callback_data='stop')
    btn_profile = types.InlineKeyboardButton('👤 Профиль', callback_data='profile')
    btn_help = types.InlineKeyboardButton('❓ Помощь', callback_data='help')
    markup.add(btn_next, btn_stop, btn_profile, btn_help)
    
    message = (
        f"🎉 *СОБЕСЕДНИК НАЙДЕН!*\n\n"
        f"🏷️ *Категория:* {category_name}\n"
        f"💬 *Можете начинать общение!*\n\n"
        f"✨ *Просто напишите сообщение — оно отправится собеседнику.*"
    )
    
    try:
        bot.send_message(user1, message, reply_markup=markup, parse_mode="Markdown")
        bot.send_message(user2, message, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {e}")

# ======== ОЧИСТКА ПОЛЬЗОВАТЕЛЯ ========
def cleanup_user(user_id):
    """Очищает данные пользователя"""
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        if partner_id in active_pairs:
            del active_pairs[partner_id]
        del active_pairs[user_id]
    
    # Удаляем из очереди поиска
    search_queue[:] = [u for u in search_queue if u['user_id'] != user_id]
    
    # Очищаем состояние
    if user_id in user_states:
        del user_states[user_id]

# ======== КОМАНДА /START ========
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    cleanup_user(user_id)
    
    # Создаем профиль если нет
    get_user_profile(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search_menu')
    btn_profile = types.InlineKeyboardButton('👤 Мой профиль', callback_data='profile')
    btn_help = types.InlineKeyboardButton('❓ Помощь', callback_data='help')
    btn_stats = types.InlineKeyboardButton('📊 Статистика', callback_data='stats')
    btn_shop = types.InlineKeyboardButton('🛒 Магазин', callback_data='shop')
    markup.add(btn_search, btn_profile, btn_help, btn_stats, btn_shop)
    
    bot.send_message(
        user_id,
        "👋 *Добро пожаловать в анонимный чат!*\n\n"
        "🎭 *Общайтесь анонимно с людьми со всего мира.*\n\n"
        "✨ *Новые возможности:*\n"
        "• 🏷️ 9 категорий для общения\n"
        "• 🔍 Поиск по полу (премиум)\n"
        "• ⭐ Система Telegram Stars\n"
        "• 💎 Премиум подписка\n\n"
        "⚡️ *Быстрый старт:*",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# ======== МЕНЮ ПОИСКА ========
@bot.callback_query_handler(func=lambda call: call.data == 'search_menu')
def search_menu(call):
    user_id = call.message.chat.id
    
    if user_id in active_pairs:
        bot.answer_callback_query(call.id, "❌ У тебя уже есть собеседник!")
        return
    
    # Проверяем доступные функции
    has_gender = has_gender_search(user_id)
    has_unlimited = has_unlimited_search(user_id)
    has_priority_user = has_priority(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for category_name, category_id in CATEGORIES.items():
        buttons.append(types.InlineKeyboardButton(category_name, callback_data=f'category_{category_id}'))
    
    # Добавляем кнопки категорий
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.add(buttons[i], buttons[i + 1])
        else:
            markup.add(buttons[i])
    
    markup.add(types.InlineKeyboardButton('🔙 Назад', callback_data='back'))
    
    message = "🏷️ *Выберите категорию для общения:*"
    
    if has_gender:
        message += "\n\n✨ *У вас доступен поиск по полу!*"
    if has_unlimited:
        message += "\n♾️ *Безлимитный поиск активен*"
    if has_priority_user:
        message += "\n⚡️ *Приоритет в очереди активен*"
    
    try:
        bot.edit_message_text(
            message,
            user_id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения: {e}")
        bot.send_message(user_id, message, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('category_'))
def select_category(call):
    user_id = call.message.chat.id
    category_id = call.data.replace('category_', '')
    
    # Проверяем доступность поиска по полу
    if has_gender_search(user_id):
        # Показываем выбор пола собеседника
        markup = types.InlineKeyboardMarkup(row_width=3)
        btn_any = types.InlineKeyboardButton('👥 Любой', callback_data=f'gender_pref_any_{category_id}')
        btn_male = types.InlineKeyboardButton('👨 Мужской', callback_data=f'gender_pref_male_{category_id}')
        btn_female = types.InlineKeyboardButton('👩 Женский', callback_data=f'gender_pref_female_{category_id}')
        btn_back = types.InlineKeyboardButton('🔙 Назад', callback_data='search_menu')
        markup.add(btn_any, btn_male, btn_female, btn_back)
        
        bot.edit_message_text(
            "🔍 *Выберите пол собеседника:*",
            user_id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    else:
        # Начинаем поиск без фильтра
        start_search(user_id, category_id, 'any', call)

@bot.callback_query_handler(func=lambda call: call.data.startswith('gender_pref_'))
def select_gender_pref(call):
    user_id = call.message.chat.id
    parts = call.data.split('_')
    gender_pref = parts[2]
    category_id = parts[3]
    
    start_search(user_id, category_id, gender_pref, call)

def start_search(user_id, category_id, gender_pref, call=None):
    """Начинает поиск собеседника"""
    if user_id in active_pairs:
        if call:
            bot.answer_callback_query(call.id, "❌ У тебя уже есть собеседник!")
        return
    
    # Проверяем, не в очереди ли уже
    for item in search_queue:
        if item['user_id'] == user_id:
            if call:
                bot.answer_callback_query(call.id, "⏳ Ты уже в очереди поиска...")
            return
    
    # Добавляем в очередь
    search_data = {
        'user_id': user_id,
        'gender_pref': gender_pref,
        'category': category_id,
        'added_time': time.time()
    }
    
    # Если есть приоритет, ставим в начало
    if has_priority(user_id):
        search_queue.insert(0, search_data)
        logger.info(f"User {user_id} added to queue with PRIORITY")
    else:
        search_queue.append(search_data)
    
    # Показываем сообщение
    category_name = [k for k, v in CATEGORIES.items() if v == category_id][0]
    position = len([u for u in search_queue if u['user_id'] != user_id]) + 1
    
    markup = types.InlineKeyboardMarkup()
    btn_cancel = types.InlineKeyboardButton('❌ Отменить поиск', callback_data='cancel')
    markup.add(btn_cancel)
    
    message = f"🔍 *Ищем собеседника...*\n\n🏷️ *Категория:* {category_name}\n"
    
    if gender_pref != 'any':
        gender_text = {'male': '👨 Мужской', 'female': '👩 Женский'}
        message += f"🚻 *Пол собеседника:* {gender_text[gender_pref]}\n"
    
    message += f"📊 *Позиция в очереди:* {position}\n"
    
    if has_priority(user_id):
        message += "⚡️ *Приоритет активен*\n"
    
    message += "⏱️ *Ожидайте...*"
    
    if call:
        try:
            bot.edit_message_text(
                message,
                user_id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка редактирования: {e}")
            bot.send_message(user_id, message, reply_markup=markup, parse_mode="Markdown")
        
        bot.answer_callback_query(call.id, "🔍 Начинаем поиск...")
    else:
        bot.send_message(user_id, message, reply_markup=markup, parse_mode="Markdown")

# ======== МАГАЗИН TELEGRAM STARS ========
@bot.callback_query_handler(func=lambda call: call.data == 'shop')
def show_shop(call):
    user_id = call.message.chat.id
    stars = get_user_stars(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Кнопки покупки звёзд (через Stars API)
    btn_buy_10 = types.InlineKeyboardButton('⭐ 10 звёзд - 13₽', callback_data='stars_buy_10')
    btn_buy_50 = types.InlineKeyboardButton('⭐ 50 звёзд - 65₽', callback_data='stars_buy_50')
    btn_buy_100 = types.InlineKeyboardButton('⭐⭐ 100 звёзд - 130₽', callback_data='stars_buy_100')
    btn_buy_250 = types.InlineKeyboardButton('⭐⭐⭐ 250 звёзд - 325₽', callback_data='stars_buy_250')
    btn_buy_500 = types.InlineKeyboardButton('⭐⭐⭐⭐ 500 звёзд - 650₽', callback_data='stars_buy_500')
    
    # Премиум подписки
    btn_premium_week = types.InlineKeyboardButton('🌟 Неделя - 50⭐', callback_data='premium_week')
    btn_premium_month = types.InlineKeyboardButton('🌟 Месяц - 180⭐', callback_data='premium_month')
    
    # Платные функции
    btn_gender = types.InlineKeyboardButton('🔍 Поиск по полу - 30⭐', callback_data='buy_gender_search')
    btn_priority = types.InlineKeyboardButton('⚡️ Приоритет - 20⭐', callback_data='buy_priority')
    btn_unlimited = types.InlineKeyboardButton('♾️ Безлимит на день - 100⭐', callback_data='buy_unlimited')
    
    btn_back = types.InlineKeyboardButton('🔙 Назад', callback_data='back')
    
    markup.add(btn_buy_10, btn_buy_50, btn_buy_100, btn_buy_250, btn_buy_500,
               btn_premium_week, btn_premium_month,
               btn_gender, btn_priority, btn_unlimited,
               btn_back)
    
    stars_rub = round(stars * 1.3, 2)
    premium_status = "✅ АКТИВЕН" if is_premium(user_id) else "❌ НЕТ"
    
    message = (
        f"🛒 *Магазин Telegram Stars*\n\n"
        f"⭐️ *Ваш баланс:* {stars} звёзд (~{stars_rub}₽)\n"
        f"🌟 *Премиум статус:* {premium_status}\n\n"
        f"💫 *Купить звёзды:*\n"
        f"• 10⭐ - 13₽ (курс: 100⭐ = 130₽)\n"
        f"• 50⭐ - 65₽ (70% идёт разработчику)\n"
        f"• 100⭐ - 130₽\n"
        f"• 250⭐ - 325₽\n"
        f"• 500⭐ - 650₽\n\n"
        f"✨ *Премиум подписка:*\n"
        f"• 1 неделя - 50⭐\n"
        f"• 1 месяц - 180⭐\n\n"
        f"⚡️ *Платные функции:*\n"
        f"• Поиск по полу (24ч) - 30⭐\n"
        f"• Приоритет в очереди - 20⭐\n"
        f"• Безлимит на 24ч - 100⭐\n\n"
        f"💰 *Как купить:*\n"
        f"1. Выберите пакет звёзд\n"
        f"2. Оплатите через Telegram Stars\n"
        f"3. Звёзды поступят моментально"
    )
    
    try:
        bot.edit_message_text(
            message,
            user_id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка показа магазина: {e}")
        bot.send_message(user_id, message, reply_markup=markup, parse_mode="Markdown")

# ======== ПОКУПКА ЗВЁЗД ЧЕРЕЗ TELEGRAM STARS API ========
@bot.callback_query_handler(func=lambda call: call.data.startswith('stars_buy_'))
def handle_stars_purchase(call):
    user_id = call.message.chat.id
    stars_amount = int(call.data.replace('stars_buy_', ''))
    
    # Получаем информацию о пакете
    price_info = STAR_PACKAGES.get(stars_amount, STAR_PACKAGES[100])
    price_rub = price_info['rub_price']
    label = price_info['label']
    
    try:
        # Создаем инвойс для Telegram Stars
        prices = [types.LabeledPrice(label=label, amount=price_info['price'])]
        
        # Для Telegram Stars нужно использовать специальный провайдер
        # Временно используем тестовый метод с ссылкой
        bot.answer_callback_query(call.id, f"💫 Подготовка покупки {stars_amount} звёзд...")
        
        # Создаем сообщение с кнопкой для оплаты
        markup = types.InlineKeyboardMarkup()
        # В реальном боте здесь должна быть ссылка на оплату через Stars
        # Временно используем эмуляцию
        btn_pay = types.InlineKeyboardButton(
            f"💳 Оплатить {price_rub}₽", 
            callback_data=f'confirm_pay_{stars_amount}'
        )
        btn_cancel = types.InlineKeyboardButton('❌ Отмена', callback_data='shop')
        markup.add(btn_pay, btn_cancel)
        
        bot.send_message(
            user_id,
            f"💫 *Покупка {stars_amount} звёзд*\n\n"
            f"💰 *Стоимость:* {price_rub}₽\n"
            f"⭐ *Вы получите:* {stars_amount} звёзд\n\n"
            f"💳 *Для оплаты нажмите кнопку ниже*\n"
            f"(В демо-режиме звёзды начисляются автоматически)",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка создания платежа: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка, попробуйте позже", show_alert=True)

# Обработчик подтверждения оплаты (демо-режим)
@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_pay_'))
def handle_confirm_payment(call):
    user_id = call.message.chat.id
    stars_amount = int(call.data.replace('confirm_pay_', ''))
    
    # В демо-режиме просто начисляем звёзды
    price_info = STAR_PACKAGES.get(stars_amount, STAR_PACKAGES[100])
    price_rub = price_info['rub_price']
    
    # Начисляем звёзды
    add_stars(user_id, stars_amount, is_real=True)
    
    # Удаляем сообщение с кнопкой оплаты
    try:
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    
    # Показываем успешное сообщение
    bot.send_message(
        user_id,
        f"✅ *Оплата успешно завершена!*\n\n"
        f"💰 *Сумма:* {price_rub}₽\n"
        f"⭐ *Начислено:* {stars_amount} звёзд\n"
        f"💫 *Текущий баланс:* {get_user_stars(user_id)} звёзд\n\n"
        f"✨ Спасибо за поддержку проекта!\n"
        f"💎 70% от суммы поступит разработчику.\n\n"
        f"🛒 Можете продолжить покупки в магазине!",
        parse_mode="Markdown"
    )
    
    # Возвращаем в магазин
    show_shop(call)

# ======== ПОКУПКА ПРЕМИУМА И ФУНКЦИЙ ========
@bot.callback_query_handler(func=lambda call: call.data.startswith('premium_'))
def handle_premium_purchase(call):
    user_id = call.message.chat.id
    stars = get_user_stars(user_id)
    
    if 'week' in call.data:
        cost = PREMIUM_PRICES['week']
        days = 7
    else:
        cost = PREMIUM_PRICES['month']
        days = 30
    
    if stars >= cost:
        if spend_stars(user_id, cost):
            premium_until = datetime.now() + timedelta(days=days)
            update_profile_field(user_id, 'premium_until', premium_until.isoformat())
            
            bot.answer_callback_query(
                call.id,
                f"✅ Премиум активирован на {days} дней!\n"
                f"⭐ Списано: {cost} звёзд",
                show_alert=True
            )
            show_shop(call)
        else:
            bot.answer_callback_query(
                call.id,
                "❌ Ошибка при списании звёзд",
                show_alert=True
            )
    else:
        bot.answer_callback_query(
            call.id,
            f"❌ Недостаточно звёзд!\nНужно: {cost}⭐\nУ вас: {stars}⭐",
            show_alert=True
        )

@bot.callback_query_handler(func=lambda call: call.data == 'buy_gender_search')
def buy_gender_search(call):
    user_id = call.message.chat.id
    stars = get_user_stars(user_id)
    cost = FEATURE_PRICES['gender_search']
    
    if stars >= cost:
        if spend_stars(user_id, cost):
            until = datetime.now() + timedelta(hours=24)
            update_profile_field(user_id, 'gender_search_until', until.isoformat())
            
            bot.answer_callback_query(
                call.id,
                f"✅ Поиск по полу активирован на 24 часа!\n"
                f"⭐ Списано: {cost} звёзд",
                show_alert=True
            )
            show_shop(call)
        else:
            bot.answer_callback_query(
                call.id,
                "❌ Ошибка при списании звёзд",
                show_alert=True
            )
    else:
        bot.answer_callback_query(
            call.id,
            f"❌ Недостаточно звёзд!\nНужно: {cost}⭐\nУ вас: {stars}⭐",
            show_alert=True
        )

@bot.callback_query_handler(func=lambda call: call.data == 'buy_priority')
def buy_priority(call):
    user_id = call.message.chat.id
    stars = get_user_stars(user_id)
    cost = FEATURE_PRICES['priority']
    
    if stars >= cost:
        if spend_stars(user_id, cost):
            update_profile_field(user_id, 'priority', True)
            
            bot.answer_callback_query(
                call.id,
                f"✅ Приоритет в очереди активирован!\n"
                f"⭐ Списано: {cost} звёзд\n\n"
                f"⚡️ Теперь вы будете в начале очереди поиска!",
                show_alert=True
            )
            show_shop(call)
        else:
            bot.answer_callback_query(
                call.id,
                "❌ Ошибка при списании звёзд",
                show_alert=True
            )
    else:
        bot.answer_callback_query(
            call.id,
            f"❌ Недостаточно звёзд!\nНужно: {cost}⭐\nУ вас: {stars}⭐",
            show_alert=True
        )

@bot.callback_query_handler(func=lambda call: call.data == 'buy_unlimited')
def buy_unlimited(call):
    user_id = call.message.chat.id
    stars = get_user_stars(user_id)
    cost = FEATURE_PRICES['unlimited']
    
    if stars >= cost:
        if spend_stars(user_id, cost):
            until = datetime.now() + timedelta(hours=24)
            update_profile_field(user_id, 'unlimited_until', until.isoformat())
            
            bot.answer_callback_query(
                call.id,
                f"✅ Безлимитный поиск активирован на 24 часа!\n"
                f"⭐ Списано: {cost} звёзд\n\n"
                f"♾️ Теперь вы можете искать собеседников без ограничений!",
                show_alert=True
            )
            show_shop(call)
        else:
            bot.answer_callback_query(
                call.id,
                "❌ Ошибка при списании звёзд",
                show_alert=True
            )
    else:
        # ДОБАВЬТЕ ЭТОТ КОД:
        bot.answer_callback_query(
            call.id,
            f"❌ Недостаточно звёзд!\nНужно: {cost}⭐\nУ вас: {stars}⭐",
            show_alert=True
        )
