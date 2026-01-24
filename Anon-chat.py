import os
import telebot
from telebot import types
import time
import threading
import requests
import shelve
from datetime import datetime, timedelta

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
    print("⚠️ Flask не установлен")
    app = None

# ======== НАСТРОЙКИ TELEGRAM STARS ========
# КУРС: 100 звёзд = 130 рублей
# Разработчик получает 70% от суммы

STAR_PACKAGES = {
    10: {"price": 1300, "label": "10 звёзд (13₽)"},      # 13 руб
    50: {"price": 6500, "label": "50 звёзд (65₽)"},      # 65 руб
    100: {"price": 13000, "label": "100 звёзд (130₽)"},  # 130 руб
    250: {"price": 32500, "label": "250 звёзд (325₽)"},  # 325 руб
    500: {"price": 65000, "label": "500 звёзд (650₽)"},  # 650 руб
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
            print(f"🔄 Self-ping: {time.strftime('%H:%M:%S')}")
        except:
            pass
        time.sleep(ping_interval)

# ======== ФУНКЦИИ ДЛЯ БАЗЫ ДАННЫХ ========
def get_user_profile(user_id):
    """Получает профиль пользователя"""
    with shelve.open(PROFILES_DB) as db:
        if str(user_id) in db:
            return db[str(user_id)]
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
                'search_count': 0,
                'total_spent': 0,     # Всего потрачено звёзд
                'total_earned': 0,    # Всего заработано (в руб)
                'created_at': datetime.now().isoformat()
            }
            db[str(user_id)] = default_profile
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

def spend_stars(user_id, amount):
    """Тратит звёзды"""
    profile = get_user_profile(user_id)
    if profile.get('stars', 0) >= amount:
        profile['stars'] -= amount
        save_user_profile(user_id, profile)
        return True
    return False

def is_premium(user_id):
    """Проверяет премиум статус"""
    profile = get_user_profile(user_id)
    if profile.get('premium_until'):
        try:
            premium_until = datetime.fromisoformat(profile['premium_until'])
            return premium_until > datetime.now()
        except:
            return False
    return False

def has_gender_search(user_id):
    """Проверяет доступен ли поиск по полу"""
    profile = get_user_profile(user_id)
    if is_premium(user_id):
        return True
    if profile.get('gender_search_until'):
        try:
            until = datetime.fromisoformat(profile['gender_search_until'])
            return until > datetime.now()
        except:
            return False
    return False

def has_unlimited_search(user_id):
    """Проверяет безлимитный поиск"""
    profile = get_user_profile(user_id)
    if profile.get('unlimited_until'):
        try:
            until = datetime.fromisoformat(profile['unlimited_until'])
            return until > datetime.now()
        except:
            return False
    return False

# ======== ОЧИСТКА ПЕРЕД ЗАПУСКОМ ========
def cleanup_before_start():
    """Удаляет старые updates"""
    try:
        webhook_url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook"
        response = requests.get(webhook_url, params={"drop_pending_updates": True})
        print(f"🗑️ Удаление webhook: {response.status_code}")
        time.sleep(2)
    except Exception as e:
        print(f"⚠️ Ошибка cleanup: {e}")

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
                        
                        print(f"✅ СОЕДИНЕНО: {user1} ↔️ {user2}")
                        
                        # Отправляем уведомления
                        category_name = [k for k, v in CATEGORIES.items() if v == user1_data['category']][0]
                        notify_match(user1, user2, category_name)
                        
                        # Обновляем счётчики
                        update_profile_field(user1, 'search_count', get_user_profile(user1).get('search_count', 0) + 1)
                        update_profile_field(user2, 'search_count', get_user_profile(user2).get('search_count', 0) + 1)
                        
                        break
                    break
        except Exception as e:
            print(f"⚠️ Ошибка поиска: {e}")
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
    except:
        pass

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
    
    try:
        bot.edit_message_text(
            message,
            user_id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except:
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
    profile = get_user_profile(user_id)
    if 'priority' in profile and profile['priority']:
        search_queue.insert(0, search_data)
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
    
    message += f"📊 *Позиция в очереди:* {position}\n⏱️ *Ожидайте...*"
    
    if call:
        bot.edit_message_text(
            message,
            user_id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, "🔍 Начинаем поиск...")
    else:
        bot.send_message(user_id, message, reply_markup=markup, parse_mode="Markdown")

# ======== МАГАЗИН TELEGRAM STARS ========
@bot.callback_query_handler(func=lambda call: call.data == 'shop')
def show_shop(call):
    user_id = call.message.chat.id
    stars = get_user_stars(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Кнопки покупки звёзд
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
        f"2. Оплатите через Telegram\n"
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
    except:
        bot.send_message(user_id, message, reply_markup=markup, parse_mode="Markdown")

# ======== ПОКУПКА ЗВЁЗД ========
@bot.callback_query_handler(func=lambda call: call.data.startswith('stars_buy_'))
def handle_stars_purchase(call):
    user_id = call.message.chat.id
    stars_amount = int(call.data.replace('stars_buy_', ''))
    
    # Цена в копейках
    price_info = STAR_PACKAGES.get(stars_amount, STAR_PACKAGES[100])
    price_kop = price_info['price']
    label = price_info['label']
    
    # Создаем инвойс
    prices = [types.LabeledPrice(label=label, amount=price_kop)]
    
    try:
        bot.send_invoice(
            chat_id=user_id,
            title=f"Покупка {stars_amount} звёзд",
            description=f"Пополнение баланса на {stars_amount} звёзд",
            provider_token="",  # Для Telegram Stars оставляем пустым
            currency="RUB",
            prices=prices,
            payload=f"stars_{user_id}_{stars_amount}",
            start_parameter=f"stars_{stars_amount}",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False
        )
        
        bot.answer_callback_query(call.id, "💫 Открывается окно оплаты...")
        
    except Exception as e:
        print(f"❌ Ошибка создания инвойса: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка, попробуйте позже", show_alert=True)

# ======== ОБРАБОТКА ПЛАТЕЖЕЙ ========
@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message):
    user_id = message.chat.id
    payment_info = message.successful_payment
    
    payload = payment_info.invoice_payload
    if payload.startswith('stars_'):
        parts = payload.split('_')
        if len(parts) >= 3:
            stars_amount = int(parts[2])
            
            # Добавляем звёзды пользователю
            add_stars(user_id, stars_amount, is_real=True)
            
            # Уведомляем
            bot.send_message(
                user_id,
                f"✅ *Оплата успешна!*\n\n"
                f"💫 Вам начислено: *{stars_amount} звёзд*\n"
                f"⭐️ Текущий баланс: *{get_user_stars(user_id)} звёзд*\n\n"
                f"✨ Спасибо за поддержку проекта!\n"
                f"💰 70% от суммы поступит разработчику.",
                parse_mode="Markdown"
            )
            
            print(f"💰 Получен платёж: {stars_amount} звёзд от {user_id}")

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
        spend_stars(user_id, cost)
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
            f"❌ Недостаточно звёзд!\nНужно: {cost}⭐\nУ вас: {stars}⭐",
            show_alert=True
        )

@bot.callback_query_handler(func=lambda call: call.data == 'buy_gender_search')
def buy_gender_search(call):
    user_id = call.message.chat.id
    stars = get_user_stars(user_id)
    cost = FEATURE_PRICES['gender_search']
    
    if stars >= cost:
        spend_stars(user_id, cost)
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
            f"❌ Недостаточно звёзд!\nНужно: {cost}⭐\nУ вас: {stars}⭐",
            show_alert=True
        )

@bot.callback_query_handler(func=lambda call: call.data == 'buy_priority')
def buy_priority(call):
    user_id = call.message.chat.id
    stars = get_user_stars(user_id)
    cost = FEATURE_PRICES['priority']
    
    if stars >= cost:
        spend_stars(user_id, cost)
        # Устанавливаем флаг приоритета
        profile = get_user_profile(user_id)
        profile['priority'] = True
        save_user_profile(user_id, profile)
        
        bot.answer_callback_query(
            call.id,
            f"✅ Приоритет активирован!\n"
            f"⭐ Списано: {cost} звёзд",
            show_alert=True
        )
        show_shop(call)
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
        spend_stars(user_id, cost)
        until = datetime.now() + timedelta(hours=24)
        update_profile_field(user_id, 'unlimited_until', until.isoformat())
        
        bot.answer_callback_query(
            call.id,
            f"✅ Безлимитный поиск активирован на 24 часа!\n"
            f"⭐ Списано: {cost} звёзд",
            show_alert=True
        )
        show_shop(call)
    else:
        bot.answer_callback_query(
            call.id,
            f"❌ Недостаточно звёзд!\nНужно: {cost}⭐\nУ вас: {stars}⭐",
            show_alert=True
        )

# ======== ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ ========
@bot.callback_query_handler(func=lambda call: call.data == 'profile')
def show_profile(call):
    user_id = call.message.chat.id
    profile = get_user_profile(user_id)
    
    premium_text = "❌ Нет"
    if profile.get('premium_until'):
        try:
            premium_until = datetime.fromisoformat(profile['premium_until'])
            if premium_until > datetime.now():
                premium_text = f"✅ До {premium_until.strftime('%d.%m.%Y')}"
        except:
            pass
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_name = types.InlineKeyboardButton('✏️ Имя', callback_data='set_name')
    btn_gender = types.InlineKeyboardButton('🚻 Пол', callback_data='set_gender')
    btn_age = types.InlineKeyboardButton('🎂 Возраст', callback_data='set_age')
    btn_stars = types.InlineKeyboardButton(f'⭐ {profile.get("stars", 0)} звёзд', callback_data='stars_info')
    btn_back = types.InlineKeyboardButton('🔙 Назад', callback_data='back')
    markup.add(btn_name, btn_gender, btn_age, btn_stars, btn_back)
    
    message = (
        f"👤 *Ваш профиль*\n\n"
        f"📛 *Имя:* {profile.get('name', 'Аноним')}\n"
        f"🚻 *Пол:* {profile.get('gender', 'Не указан')}\n"
        f"🎂 *Возраст:* {profile.get('age', 'Не указан')}\n"
        f"⭐ *Звёзды:* {profile.get('stars', 0)}\n"
        f"💰 *Всего потрачено:* {profile.get('total_spent', 0)}⭐\n"
        f"💎 *Премиум:* {premium_text}\n"
        f"🔍 *Поисков:* {profile.get('search_count', 0)}\n\n"
        f"⚙️ *Настройки:*"
      )
    
    try:
        bot.edit_message_text(
            message,
            user_id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except:
        bot.send_message(user_id, message, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == 'stars_info')
def show_stars_info(call):
    user_id = call.message.chat.id
    profile = get_user_profile(user_id)
    
    markup = types.InlineKeyboardMarkup()
    btn_shop = types.InlineKeyboardButton('🛒 Магазин', callback_data='shop')
    btn_back = types.InlineKeyboardButton('🔙 Назад', callback_data='profile')
    markup.add(btn_shop, btn_back)
    
    message = (
        f"⭐️ *Информация о звёздах*\n\n"
        f"💫 *Текущий баланс:* {profile.get('stars', 0)}⭐\n"
        f"💰 *Куплено:* {profile.get('real_stars', 0)}⭐\n"
        f"💸 *Потрачено всего:* {profile.get('total_spent', 0)}⭐\n"
        f"💎 *Заработано разработчиком:* ~{profile.get('total_earned', 0):.2f}₽\n\n"
        f"✨ *Курс:* 100⭐ = 130₽\n"
        f"💳 *Разработчик получает:* 70% от суммы\n\n"
        f"🚀 Спасибо за поддержку проекта!"
    )
    
    bot.edit_message_text(
        message,
        user_id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('save_gender_'))
def save_gender(call):
    user_id = call.message.chat.id
    gender = call.data.replace('save_gender_', '')
    
    gender_text = {'male': 'Мужской', 'female': 'Женский', 'other': 'Другой'}
    update_profile_field(user_id, 'gender', gender_text[gender])
    
    bot.answer_callback_query(call.id, f"✅ Пол сохранен: {gender_text[gender]}")
    show_profile(call)

@bot.callback_query_handler(func=lambda call: call.data == 'set_age')
def set_age_handler(call):
    user_id = call.message.chat.id
    user_states[user_id] = {'awaiting': 'age'}
    
    bot.edit_message_text(
        "🎂 *Введите ваш возраст (число от 13 до 99):*",
        user_id,
        call.message.message_id,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == 'set_name')
def set_name_handler(call):
    user_id = call.message.chat.id
    user_states[user_id] = {'awaiting': 'name'}
    
    bot.edit_message_text(
        "✏️ *Введите ваше имя (максимум 20 символов):*",
        user_id,
        call.message.message_id,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.chat.id in user_states)
def handle_profile_input(message):
    user_id = message.chat.id
    state = user_states.get(user_id, {})
    
    if 'awaiting' in state:
        if state['awaiting'] == 'age':
            try:
                age = int(message.text)
                if 13 <= age <= 99:
                    update_profile_field(user_id, 'age', age)
                    bot.send_message(user_id, f"✅ Возраст сохранен: {age} лет")
                    del user_states[user_id]
                else:
                    bot.send_message(user_id, "❌ Возраст должен быть от 13 до 99 лет")
            except:
                bot.send_message(user_id, "❌ Введите корректное число")
                
        elif state['awaiting'] == 'name':
            name = message.text.strip()
            if 1 <= len(name) <= 20:
                update_profile_field(user_id, 'name', name)
                bot.send_message(user_id, f"✅ Имя сохранено: {name}")
                del user_states[user_id]
            else:
                bot.send_message(user_id, "❌ Имя должно быть от 1 до 20 символов")

# ======== ОБРАБОТКА СООБЩЕНИЙ ========
@bot.message_handler(func=lambda msg: True)
def handle_messages(message):
    user_id = message.chat.id
    
    if user_id in active_pairs:
        partner_id = active_pairs[user_id]
        try:
            bot.send_message(partner_id, message.text)
        except:
            print(f"❌ Ошибка пересылки")
    
    elif any(u['user_id'] == user_id for u in search_queue):
        position = next(i for i, u in enumerate(search_queue) if u['user_id'] == user_id) + 1
        bot.send_message(user_id, f"⏳ *Ты всё ещё в поиске...*\n\n📊 *Позиция в очереди:* {position}")
    else:
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_search = types.InlineKeyboardButton('🔍 Начать поиск', callback_data='search_menu')
        btn_profile = types.InlineKeyboardButton('👤 Профиль', callback_data='profile')
        btn_help = types.InlineKeyboardButton('❓ Помощь', callback_data='help')
        markup.add(btn_search, btn_profile, btn_help)
        
        bot.send_message(
            user_id,
            "🤔 *Кажется, ты не в диалоге...*\nХочешь найти собеседника?",
            reply_markup=markup,
            parse_mode="Markdown"
        )

# ======== ОБРАБОТКА КНОПОК ========
@bot.callback_query_handler(func=lambda call: call.data in ['cancel', 'next', 'stop', 'back', 'help', 'stats'])
def handle_basic_buttons(call):
    user_id = call.message.chat.id
    command = call.data
    
    try:
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    
    if command == 'cancel':
        cleanup_user(user_id)
        start(call.message)
        
    elif command == 'next':
        if user_id not in active_pairs:
            bot.send_message(user_id, "❌ У тебя нет активного собеседника.")
            return
        
        partner_id = active_pairs[user_id]
        cleanup_user(user_id)
        bot.send_message(partner_id, "⚠️ *Твой собеседник покинул диалог.*")
        start(call.message)
        
    elif command == 'stop':
        if user_id in active_pairs:
            partner_id = active_pairs[user_id]
            cleanup_user(user_id)
            bot.send_message(partner_id, "❌ *Собеседник завершил диалог.*")
        
        cleanup_user(user_id)
        start(call.message)
        
    elif command == 'back':
        start(call.message)
        
    elif command == 'help':
        bot.send_message(
            user_id,
            "❓ *Помощь*\n\n"
            "✨ *Как пользоваться:*\n"
            "1. Нажми 'Начать поиск'\n"
            "2. Выбери категорию\n"
            "3. Дождись собеседника\n"
            "4. Общайся анонимно\n\n"
            "⚡️ *Команды:*\n"
            "• /start - главное меню\n"
            "• /next - следующий собеседник\n"
            "• /stop - завершить диалог\n\n"
            "💎 *Премиум функции:*\n"
            "• Поиск по полу\n"
            "• Приоритет в очереди\n"
            "• Безлимитный поиск\n\n"
            "🛒 *Магазин:* /shop",
            parse_mode="Markdown"
        )
        
    elif command == 'stats':
        import shelve
        with shelve.open(PROFILES_DB) as db:
            total_users = len(db)
        
        profile = get_user_profile(user_id)
        
        bot.send_message(
            user_id,
            f"📊 *Статистика*\n\n"
            f"👤 *Ваш профиль:*\n"
            f"• Имя: {profile.get('name')}\n"
            f"• Поисков: {profile.get('search_count', 0)}\n"
            f"• Звёзд: {profile.get('stars', 0)}⭐\n"
            f"• Потрачено: {profile.get('total_spent', 0)}⭐\n\n"
            f"🌐 *Общая:*\n"
            f"• Всего пользователей: {total_users}\n"
            f"• В поиске: {len(search_queue)}\n"
            f"• Активных пар: {len(active_pairs)//2}\n\n"
            f"🚀 *Бот работает стабильно!*",
            parse_mode="Markdown"
        )

# ======== ЗАПУСК (ИСПРАВЛЕННЫЙ ДЛЯ RENDER) ========
if __name__ == "__main__":
    print("="*50)
    print("🤖 АНОНИМНЫЙ ЧАТ - TELEGRAM STARS")
    print(f"🕐 Время запуска: {time.strftime('%H:%M:%S')}")
    print("="*50)
    
    # Очистка перед запуском
    cleanup_before_start()
    
    # Запуск фонового поиска
    search_thread = threading.Thread(target=background_search, daemon=True)
    search_thread.start()
    
    # Запуск авто-пинга
    ping_thread = threading.Thread(target=keep_alive, daemon=True)
    ping_thread.start()
    
    print("✅ Все системы запущены!")
    print(f"📊 Статус: В очереди: {len(search_queue)} | Активных пар: {len(active_pairs)//2}")
    print("="*50)
    print("💰 Курс: 100 звёзд = 130 рублей")
    print("💳 Разработчик получает: 70% от суммы")
    print("="*50)
    
    # Запуск бота в отдельном потоке
    def start_bot():
        print("🤖 Запускаем polling бота...")
        while True:
            try:
                bot.polling(
                    none_stop=True,
                    interval=3,
                    timeout=30,
                    skip_pending=True,
                    allowed_updates=["message", "callback_query"]
                )
            except Exception as e:
                print(f"❌ Ошибка polling: {e}")
                print("🔄 Перезапуск через 10 секунд...")
                time.sleep(10)
    
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    
    # Flask должен быть последним и в главном потоке (для Render)
    if app:
        try:
            port = int(os.environ.get("PORT", 10000))
            print(f"🌐 Запуск Flask сервера на порту {port}...")
            app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
        except Exception as e:
            print(f"⚠️ Ошибка Flask: {e}")
            # Удерживаем основной поток
            while True:
                time.sleep(3600)
    else:
        print("⚠️ Flask не установлен")
        # Удерживаем основной поток
        while True:
            time.sleep(3600)


