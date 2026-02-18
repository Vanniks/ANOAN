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

TOKEN = "8320203935:AAHcZbzpis6Gp6cnnon0oeqqlUf_pSTRjgM"
bot = telebot.TeleBot(TOKEN)

# ======== НАСТРОЙКИ АДМИНИСТРАТОРОВ ========
ADMIN_IDS = [8320203935]  # Замените на свой Telegram ID

def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

# ======== ПРОВЕРКА СТАТУСА БОТА ========
def check_bot_status():
    """Проверяет статус бота"""
    try:
        bot_info = bot.get_me()
        logger.info(f"🤖 Бот запущен: @{bot_info.username}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка подключения бота: {e}")
        return False

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
# ВАЖНО: Для Telegram Stars цена указывается в копейках!
# 100 копеек = 1 рубль = 1 звезда

STAR_PACKAGES = {
    10: {"price": 1000, "label": "10 звёзд", "rub_price": 10},     # 1000 копеек = 10₽
    50: {"price": 5000, "label": "50 звёзд", "rub_price": 50},     # 5000 копеек = 50₽
    100: {"price": 10000, "label": "100 звёзд", "rub_price": 100}, # 10000 копеек = 100₽
    250: {"price": 25000, "label": "250 звёзд", "rub_price": 250}, # 25000 копеек = 250₽
    500: {"price": 50000, "label": "500 звёзд", "rub_price": 500}, # 50000 копеек = 500₽
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
        # 1 звезда = 1 рубль
        earned_rub = amount * 0.7
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

# ======== ОЧИСТКА ЗАВИСШИХ ПОЛЬЗОВАТЕЛЕЙ ========
def cleanup_stale_searches():
    """Очищает очередь от пользователей, которые уже не в сети или зависли"""
    while True:
        try:
            current_time = time.time()
            stale_users = []
            
            # Проверяем каждого в очереди
            for item in search_queue:
                # Если пользователь в очереди больше 5 минут - удаляем
                if current_time - item['added_time'] > 300:  # 5 минут
                    stale_users.append(item['user_id'])
                    logger.warning(f"⚠️ User {item['user_id']} removed from queue (stale after 5 min)")
            
            # Удаляем найденных
            if stale_users:
                search_queue[:] = [u for u in search_queue if u['user_id'] not in stale_users]
                
                # Очищаем состояния для этих пользователей
                for user_id in stale_users:
                    if user_id in user_states:
                        del user_states[user_id]
                    
        except Exception as e:
            logger.error(f"❌ Ошибка очистки очереди: {e}")
        
        time.sleep(60)  # Проверяем каждую минуту

# ======== ФУНКЦИЯ ФОНОВОГО ПОИСКА ========
def background_search():
    """Ищет пары в фоне"""
    last_log_time = 0
    while True:
        try:
            # Логируем состояние очереди каждые 30 секунд
            if time.time() - last_log_time > 30:
                logger.info(f"📊 Очередь: {len(search_queue)} пользователей, пар: {len(active_pairs)//2}")
                last_log_time = time.time()
            
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
                        
                        logger.info(f"✅ Соединено: {user1} ↔️ {user2}")
                        
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

# ======== КОМАНДА ДЛЯ ПРОВЕРКИ ОЧЕРЕДИ ========
@bot.message_handler(commands=['queue'])
def show_queue(message):
    """Показывает состояние очереди поиска"""
    user_id = message.chat.id
    
    queue_info = f"📊 *Состояние очереди*\n\n"
    queue_info += f"👥 Всего в очереди: {len(search_queue)}\n"
    queue_info += f"💬 Активных пар: {len(active_pairs)//2}\n\n"
    
    if search_queue:
        queue_info += "*Очередь:*\n"
        for i, item in enumerate(search_queue[:10]):  # Показываем первых 10
            wait_time = int(time.time() - item['added_time'])
            category_name = [k for k, v in CATEGORIES.items() if v == item['category']][0]
            gender_pref = {'any': '👥', 'male': '👨', 'female': '👩'}.get(item['gender_pref'], '👥')
            queue_info += f"{i+1}. {gender_pref} ID:{item['user_id']} | {category_name} | ждёт {wait_time}с\n"
        
        if len(search_queue) > 10:
            queue_info += f"... и ещё {len(search_queue) - 10}\n"
    else:
        queue_info += "❌ Очередь пуста\n"
    
    bot.send_message(user_id, queue_info, parse_mode="Markdown")

# ======== КОМАНДА ДЛЯ ОЧИСТКИ ОЧЕРЕДИ (АДМИН) ========
@bot.message_handler(commands=['clearqueue'])
def clear_queue(message):
    """Очищает очередь поиска (только для админа)"""
    user_id = message.chat.id
    
    if not is_admin(user_id):
        bot.send_message(user_id, "❌ У вас нет прав для этой команды")
        return
    
    old_size = len(search_queue)
    search_queue.clear()
    logger.warning(f"🧹 Очередь очищена администратором {user_id}")
    bot.send_message(user_id, f"✅ Очередь очищена. Удалено {old_size} пользователей")

# ======== КОМАНДА ДЛЯ ПРОВЕРКИ ПЛАТЕЖЕЙ ========
@bot.message_handler(commands=['checkpayments'])
def check_payments(message):
    """Проверяет доступность платежей"""
    user_id = message.chat.id
    
    help_text = (
        "🔍 *Проверка платежей Telegram Stars*\n\n"
        "1. *Проверьте у себя:*\n"
        "   • Откройте @PremiumBot\n"
        "   • Посмотрите, есть ли кнопка '⭐ Stars'\n"
        "   • Если есть — Stars доступны\n\n"
        "2. *В @BotFather:*\n"
        "   • /mybots → выберите бота\n"
        "   • Bot Settings → Payments\n"
        "   • Включите Telegram Stars\n\n"
        "3. *Если Stars недоступны:*\n"
        "   • Они пока в бета-тестировании\n"
        "   • Доступны не во всех странах\n"
        "   • Следите за обновлениями @telegram"
    )
    
    bot.send_message(user_id, help_text, parse_mode="Markdown")

# ======== АДМИН-КОМАНДЫ ========

@bot.message_handler(commands=['adminstats'])
def admin_stats(message):
    """Показывает расширенную статистику (только для админа)"""
    user_id = message.chat.id
    
    if not is_admin(user_id):
        bot.send_message(user_id, "❌ У вас нет прав для этой команды")
        return
    
    with shelve.open(PROFILES_DB) as db:
        total_users = len(db)
        
        # Считаем премиум пользователей
        premium_users = 0
        for user_key in db:
            profile = db[user_key]
            if profile.get('premium_until'):
                try:
                    until = datetime.fromisoformat(profile['premium_until'])
                    if until > datetime.now():
                        premium_users += 1
                except:
                    pass
        
        # Считаем общее количество звёзд
        total_stars = sum(profile.get('stars', 0) for profile in db.values())
        total_spent = sum(profile.get('total_spent', 0) for profile in db.values())
        total_earned = sum(profile.get('total_earned', 0) for profile in db.values())
    
    stats_text = (
        f"📊 *Админ-статистика*\n\n"
        f"👥 *Пользователи:*\n"
        f"• Всего: {total_users}\n"
        f"• Премиум: {premium_users}\n"
        f"• В очереди: {len(search_queue)}\n"
        f"• В диалогах: {len(active_pairs)}\n\n"
        f"⭐ *Звёзды:*\n"
        f"• Всего в системе: {total_stars}\n"
        f"• Потрачено всего: {total_spent}\n"
        f"• Заработано: {total_earned:.2f}₽\n\n"
        f"⚙️ *Команды:*\n"
        f"/broadcast - Рассылка\n"
        f"/clearqueue - Очистить очередь"
    )
    
    bot.send_message(user_id, stats_text, parse_mode="Markdown")

@bot.message_handler(commands=['broadcast'])
def broadcast_start(message):
    """Начинает процесс рассылки (только для админа)"""
    user_id = message.chat.id
    
    if not is_admin(user_id):
        bot.send_message(user_id, "❌ У вас нет прав для этой команды")
        return
    
    bot.send_message(
        user_id,
        "📢 *Режим рассылки*\n\n"
        "Отправьте сообщение, которое хотите разослать всем пользователям.\n"
        "Поддерживаются: текст, фото, видео, документы, стикеры.\n\n"
        "✏️ *Чтобы отменить:* /cancel",
        parse_mode="Markdown"
    )
    
    # Устанавливаем состояние
    user_states[user_id] = {'awaiting': 'broadcast_message'}

@bot.message_handler(commands=['userinfo'])
def user_info(message):
    """Показывает информацию о пользователе по ID (только для админа)"""
    admin_id = message.chat.id
    
    if not is_admin(admin_id):
        bot.send_message(admin_id, "❌ У вас нет прав для этой команды")
        return
    
    try:
        target_id = int(message.text.split()[1])
        profile = get_user_profile(target_id)
        
        info_text = (
            f"👤 *Информация о пользователе*\n\n"
            f"🆔 ID: `{target_id}`\n"
            f"📛 Имя: {profile.get('name', 'Аноним')}\n"
            f"🚻 Пол: {profile.get('gender', 'Не указан')}\n"
            f"🎂 Возраст: {profile.get('age', 'Не указан')}\n"
            f"⭐ Звёзды: {profile.get('stars', 0)}\n"
            f"💰 Куплено: {profile.get('real_stars', 0)}\n"
            f"🔍 Поисков: {profile.get('search_count', 0)}\n"
            f"💎 Премиум: {'✅' if is_premium(target_id) else '❌'}\n"
            f"📅 Создан: {profile.get('created_at', 'Неизвестно')[:10]}"
        )
        
        bot.send_message(admin_id, info_text, parse_mode="Markdown")
        
    except (IndexError, ValueError):
        bot.send_message(admin_id, "Используйте: /userinfo [ID пользователя]")
    except Exception as e:
        bot.send_message(admin_id, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['addstars'])
def add_stars_admin(message):
    """Выдаёт звёзды пользователю (только для админа)"""
    admin_id = message.chat.id
    
    if not is_admin(admin_id):
        bot.send_message(admin_id, "❌ У вас нет прав для этой команды")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.send_message(admin_id, "Используйте: /addstars [user_id] [количество]")
            return
        
        target_id = int(parts[1])
        amount = int(parts[2])
        
        add_stars(target_id, amount, is_real=True)
        
        bot.send_message(
            admin_id,
            f"✅ Выдано {amount} звёзд пользователю {target_id}"
        )
        
        # Уведомляем пользователя
        try:
            bot.send_message(
                target_id,
                f"🎁 *Вам начислено {amount} звёзд!*\n\n"
                f"Спасибо за использование бота!",
                parse_mode="Markdown"
            )
        except:
            pass
        
    except Exception as e:
        bot.send_message(admin_id, f"❌ Ошибка: {e}")

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
    
    # Кнопки покупки звёзд
    btn_buy_10 = types.InlineKeyboardButton('⭐ 10 звёзд - 10₽', callback_data='stars_buy_10')
    btn_buy_50 = types.InlineKeyboardButton('⭐ 50 звёзд - 50₽', callback_data='stars_buy_50')
    btn_buy_100 = types.InlineKeyboardButton('⭐⭐ 100 звёзд - 100₽', callback_data='stars_buy_100')
    btn_buy_250 = types.InlineKeyboardButton('⭐⭐⭐ 250 звёзд - 250₽', callback_data='stars_buy_250')
    btn_buy_500 = types.InlineKeyboardButton('⭐⭐⭐⭐ 500 звёзд - 500₽', callback_data='stars_buy_500')
    
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
    
    stars_rub = stars
    premium_status = "✅ АКТИВЕН" if is_premium(user_id) else "❌ НЕТ"
    
    message = (
        f"🛒 *Магазин Telegram Stars*\n\n"
        f"⭐️ *Ваш баланс:* {stars} звёзд ({stars}₽)\n"
        f"🌟 *Премиум статус:* {premium_status}\n\n"
        f"💫 *Купить звёзды:*\n"
        f"• 10⭐ - 10₽ (курс: 1⭐ = 1₽)\n"
        f"• 50⭐ - 50₽ (70% идёт разработчику)\n"
        f"• 100⭐ - 100₽\n"
        f"• 250⭐ - 250₽\n"
        f"• 500⭐ - 500₽\n\n"
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

# ======== ПОКУПКА ЗВЁЗД ЧЕРЕЗ TELEGRAM STARS ========
@bot.callback_query_handler(func=lambda call: call.data.startswith('stars_buy_'))
def handle_stars_purchase(call):
    user_id = call.message.chat.id
    stars_amount = int(call.data.replace('stars_buy_', ''))
    
    # Получаем информацию о пакете
    price_info = STAR_PACKAGES.get(stars_amount)
    if not price_info:
        price_info = STAR_PACKAGES[100]
    
    logger.info(f"Покупка звёзд: user={user_id}, amount={stars_amount}, price={price_info['price']}")
    
    try:
        # Создаем инвойс
        prices = [types.LabeledPrice(label=f"{stars_amount} звёзд", amount=price_info['price'])]
        
        # ВАЖНО: Для Telegram Stars используем currency="XTR"
        bot.send_invoice(
            chat_id=user_id,
            title=f"⭐ {stars_amount} звёзд",
            description=f"Пополнение баланса в анонимном чате",
            invoice_payload=f"stars_{user_id}_{stars_amount}_{int(time.time())}",
            provider_token="",  # Для Stars оставляем пустым
            currency="XTR",     # Код валюты Telegram Stars
            prices=prices,
            start_parameter=f"stars_{stars_amount}",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False,
            request_timeout=30
        )
        
        logger.info(f"✅ Инвойс отправлен пользователю {user_id}")
        bot.answer_callback_query(call.id, "💫 Открывается окно оплаты...")
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания инвойса: {e}", exc_info=True)
        
        # Предлагаем альтернативу
        markup = types.InlineKeyboardMarkup()
        btn_try_again = types.InlineKeyboardButton('🔄 Попробовать ещё раз', callback_data=f'stars_buy_{stars_amount}')
        btn_support = types.InlineKeyboardButton('👨‍💻 Поддержка', url='https://t.me/durov')
        markup.add(btn_try_again, btn_support)
        
        bot.send_message(
            user_id,
            f"⚠️ *Не удалось открыть оплату*\n\n"
            f"Telegram Stars могут быть временно недоступны.\n\n"
            f"**Попробуйте:**\n"
            f"1. Обновить Telegram до последней версии\n"
            f"2. Проверить, доступны ли Stars в @PremiumBot\n"
            f"3. Попробовать позже\n\n"
            f"Или напишите в поддержку Telegram.",
            reply_markup=markup,
            parse_mode="Markdown"
        )

# ======== ОБРАБОТКА ПРЕДВАРИТЕЛЬНОГО ЗАПРОСА ========
@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout(pre_checkout_query):
    try:
        logger.info(f"📝 Pre-checkout от {pre_checkout_query.from_user.id}")
        bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    except Exception as e:
        logger.error(f"❌ Ошибка pre-checkout: {e}")
        bot.answer_pre_checkout_query(
            pre_checkout_query.id, 
            ok=False, 
            error_message="Произошла ошибка при обработке платежа"
        )

# ======== ОБРАБОТКА УСПЕШНОЙ ОПЛАТЫ ========
@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message):
    try:
        user_id = message.chat.id
        payment = message.successful_payment
        
        logger.info(f"💰 Успешный платёж от {user_id}:")
        logger.info(f"  Сумма: {payment.total_amount}")
        logger.info(f"  Валюта: {payment.currency}")
        logger.info(f"  Payload: {payment.invoice_payload}")
        
        if payment.invoice_payload.startswith('stars_'):
            parts = payment.invoice_payload.split('_')
            if len(parts) >= 3:
                stars_amount = int(parts[2])
                add_stars(user_id, stars_amount, is_real=True)
                
                bot.send_message(
                    user_id,
                    f"🎉 *Оплата успешна!*\n\n"
                    f"💫 Начислено: *{stars_amount} звёзд*\n"
                    f"⭐ Текущий баланс: *{get_user_stars(user_id)} звёзд*\n\n"
                    f"✨ Спасибо за поддержку проекта!\n"
                    f"💰 70% от суммы поступит разработчику.",
                    parse_mode="Markdown"
                )
                
                logger.info(f"✅ Начислено {stars_amount} звёзд пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки платежа: {e}")
        if 'user_id' in locals():
            bot.send_message(user_id, "⚠️ Произошла ошибка при обработке платежа. Обратитесь к администратору.")

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
    except Exception as e:
        logger.error(f"Ошибка показа профиля: {e}")
        bot.send_message(user_id, message, reply_markup=markup, parse_mode="Markdown")

# ======== ОБРАБОТЧИК ВЫБОРА ПОЛА ========
@bot.callback_query_handler(func=lambda call: call.data == 'set_gender')
def set_gender_handler(call):
    user_id = call.message.chat.id
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    btn_male = types.InlineKeyboardButton('👨 Мужской', callback_data='save_gender_male')
    btn_female = types.InlineKeyboardButton('👩 Женский', callback_data='save_gender_female')
    btn_other = types.InlineKeyboardButton('⚧️ Другой', callback_data='save_gender_other')
    btn_back = types.InlineKeyboardButton('🔙 Назад', callback_data='profile')
    markup.add(btn_male, btn_female, btn_other, btn_back)
    
    try:
        bot.edit_message_text(
            "🚻 *Выберите ваш пол:*",
            user_id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка выбора пола: {e}")
        bot.send_message(user_id, "🚻 *Выберите ваш пол:*", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('save_gender_'))
def save_gender(call):
    user_id = call.message.chat.id
    gender = call.data.replace('save_gender_', '')
    
    gender_text = {'male': 'Мужской', 'female': 'Женский', 'other': 'Другой'}
    
    if gender in gender_text:
        update_profile_field(user_id, 'gender', gender_text[gender])
        bot.answer_callback_query(call.id, f"✅ Пол сохранен: {gender_text[gender]}")
        show_profile(call)
    else:
        bot.answer_callback_query(call.id, "❌ Ошибка выбора пола")

@bot.callback_query_handler(func=lambda call: call.data == 'set_age')
def set_age_handler(call):
    user_id = call.message.chat.id
    user_states[user_id] = {'awaiting': 'age'}
    
    try:
        bot.edit_message_text(
            "🎂 *Введите ваш возраст (число от 13 до 99):*",
            user_id,
            call.message.message_id,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка установки возраста: {e}")
        bot.send_message(user_id, "🎂 *Введите ваш возраст (число от 13 до 99):*", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == 'set_name')
def set_name_handler(call):
    user_id = call.message.chat.id
    user_states[user_id] = {'awaiting': 'name'}
    
    try:
        bot.edit_message_text(
            "✏️ *Введите ваше имя (максимум 20 символов):*",
            user_id,
            call.message.message_id,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка установки имени: {e}")
        bot.send_message(user_id, "✏️ *Введите ваше имя (максимум 20 символов):*", parse_mode="Markdown")

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
        f"✨ *Курс:* 1⭐ = 1₽\n"
        f"💳 *Разработчик получает:* 70% от суммы\n\n"
        f"🚀 Спасибо за поддержку проекта!"
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
        logger.error(f"Ошибка показа информации о звёздах: {e}")
        bot.send_message(user_id, message, reply_markup=markup, parse_mode="Markdown")

# ======== ОБРАБОТКА СООБЩЕНИЙ С РАССЫЛКОЙ ========
@bot.message_handler(func=lambda msg: msg.chat.id in user_states and user_states[msg.chat.id].get('awaiting') == 'broadcast_message', content_types=['text', 'photo', 'video', 'document', 'sticker', 'voice', 'audio'])
def handle_broadcast_message(message):
    """Получает сообщение для рассылки и отправляет его всем пользователям"""
    admin_id = message.chat.id
    
    if not is_admin(admin_id):
        return
    
    # Отправляем подтверждение
    confirm_markup = types.InlineKeyboardMarkup(row_width=2)
    btn_confirm = types.InlineKeyboardButton('✅ Подтвердить', callback_data='broadcast_confirm')
    btn_cancel = types.InlineKeyboardButton('❌ Отменить', callback_data='broadcast_cancel')
    confirm_markup.add(btn_confirm, btn_cancel)
    
    bot.send_message(
        admin_id,
        "⚠️ *Подтверждение рассылки*\n\n"
        "Это сообщение будет отправлено ВСЕМ пользователям бота.\n"
        "Вы уверены?",
        reply_markup=confirm_markup,
        parse_mode="Markdown"
    )
    
    # Сохраняем сообщение в состоянии
    user_states[admin_id] = {
        'awaiting': 'broadcast_confirm',
        'broadcast_message': message
    }

@bot.callback_query_handler(func=lambda call: call.data.startswith('broadcast_'))
def handle_broadcast_confirm(call):
    """Обрабатывает подтверждение или отмену рассылки"""
    admin_id = call.message.chat.id
    
    if not is_admin(admin_id):
        bot.answer_callback_query(call.id, "❌ Нет прав")
        return
    
    if call.data == 'broadcast_confirm':
        # Получаем сохраненное сообщение
        state = user_states.get(admin_id, {})
        broadcast_msg = state.get('broadcast_message')
        
        if not broadcast_msg:
            bot.answer_callback_query(call.id, "❌ Ошибка: сообщение не найдено")
            return
        
        bot.answer_callback_query(call.id, "📢 Начинаю рассылку...")
        
        # Собираем всех пользователей из базы
        all_users = []
        with shelve.open(PROFILES_DB) as db:
            all_users = list(db.keys())
        
        bot.send_message(admin_id, f"📊 Начинаю рассылку {len(all_users)} пользователям...")
        
        # Счетчики
        success = 0
        failed = 0
        
        # Отправляем каждому
        for user_key in all_users:
            try:
                target_id = int(user_key)
                
                # Копируем сообщение в зависимости от типа
                if broadcast_msg.text:
                    bot.send_message(target_id, broadcast_msg.text)
                elif broadcast_msg.photo:
                    bot.send_photo(
                        target_id, 
                        broadcast_msg.photo[-1].file_id,
                        caption=broadcast_msg.caption
                    )
                elif broadcast_msg.video:
                    bot.send_video(
                        target_id,
                        broadcast_msg.video.file_id,
                        caption=broadcast_msg.caption
                    )
                elif broadcast_msg.document:
                    bot.send_document(
                        target_id,
                        broadcast_msg.document.file_id,
                        caption=broadcast_msg.caption
                    )
                elif broadcast_msg.sticker:
                    bot.send_sticker(target_id, broadcast_msg.sticker.file_id)
                elif broadcast_msg.voice:
                    bot.send_voice(target_id, broadcast_msg.voice.file_id)
                elif broadcast_msg.audio:
                    bot.send_audio(target_id, broadcast_msg.audio.file_id)
                
                success += 1
                
                # Небольшая задержка чтобы не спамить
                time.sleep(0.05)
                
            except Exception as e:
                failed += 1
                logger.error(f"Ошибка отправки пользователю {user_key}: {e}")
        
        # Отправляем отчет админу
        bot.send_message(
            admin_id,
            f"📊 *Отчет о рассылке*\n\n"
            f"✅ Успешно: {success}\n"
            f"❌ Ошибок: {failed}\n"
            f"👥 Всего: {len(all_users)}",
            parse_mode="Markdown"
        )
        
    elif call.data == 'broadcast_cancel':
        bot.send_message(admin_id, "❌ Рассылка отменена")
    
    # Очищаем состояние
    if admin_id in user_states:
        del user_states[admin_id]
    
    try:
        bot.delete_message(admin_id, call.message.message_id)
    except:
        pass

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

# ======== ЗАПУСК ========
if __name__ == "__main__":
    print("="*50)
    print("🤖 АНОНИМНЫЙ ЧАТ - TELEGRAM STARS")
    print(f"🕐 Время запуска: {time.strftime('%H:%M:%S')}")
    print("="*50)
    
    # Проверяем статус бота
    if not check_bot_status():
        print("❌ Не удалось подключиться к Telegram API")
        exit(1)
    
    # Очистка перед запуском
    cleanup_before_start()
    
    # Запуск фонового поиска
    search_thread = threading.Thread(target=background_search, daemon=True)
    search_thread.start()
    
    # Запуск авто-пинга
    ping_thread = threading.Thread(target=keep_alive, daemon=True)
    ping_thread.start()
    
    # Запуск очистки старых записей
    cleanup_thread = threading.Thread(target=cleanup_stale_searches, daemon=True)
    cleanup_thread.start()
    print("🧹 Запущена очистка очереди (каждую минуту)")
    
    print("✅ Все системы запущены!")
    print(f"📊 Статус: В очереди: {len(search_queue)} | Активных пар: {len(active_pairs)//2}")
    print("="*50)
    print("💰 Курс: 1 звезда = 1 рубль")
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
