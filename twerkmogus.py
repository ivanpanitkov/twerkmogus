import json
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties

# Настройки
API_TOKEN = '8002121069:AAF-3SKd3w9YOmeIwNZ0KOVQAqT_LAKxCT0'
WEB_APP_URL = 'https://ivanpanitkov.github.io/twerkmogus/'

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# Простая инициализация БД - ВСЕГО ОДНА ТАБЛИЦА
def init_db():
    conn = sqlite3.connect('clicks_simple.db')
    cursor = conn.cursor()
    
    # Одна таблица со всей информацией
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        total_clicks INTEGER DEFAULT 0,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных готова")

# Функция добавления кликов
def add_clicks(user_id: int, username: str, first_name: str, last_name: str, clicks_to_add: int):
    conn = sqlite3.connect('clicks_simple.db')
    cursor = conn.cursor()
    
    # Добавляем или обновляем пользователя
    cursor.execute('''
    INSERT INTO users (user_id, username, first_name, last_name, total_clicks)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET 
        total_clicks = total_clicks + ?,
        username = COALESCE(?, username),
        first_name = COALESCE(?, first_name),
        last_name = COALESCE(?, last_name),
        last_seen = CURRENT_TIMESTAMP
    ''', (
        user_id, username, first_name, last_name, clicks_to_add,  # INSERT
        clicks_to_add, username, first_name, last_name            # UPDATE
    ))
    
    conn.commit()
    
    # Получаем итоговое значение
    cursor.execute('SELECT total_clicks FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    total = result[0] if result else 0
    
    conn.close()
    return total

# Функция получения кликов
def get_user_info(user_id: int):
    conn = sqlite3.connect('clicks_simple.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT username, first_name, last_name, total_clicks 
    FROM users 
    WHERE user_id = ?
    ''', (user_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'username': result[0],
            'first_name': result[1],
            'last_name': result[2],
            'total_clicks': result[3]
        }
    return None

# Функция получения топ 10
def get_top_10():
    conn = sqlite3.connect('clicks_simple.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT 
        user_id,
        COALESCE(first_name, username, 'Аноним') as name,
        username,
        total_clicks 
    FROM users 
    ORDER BY total_clicks DESC 
    LIMIT 10
    ''')
    
    result = cursor.fetchall()
    conn.close()
    return result

# Клавиатура с Web App
web_app_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎮 Открыть кликер", web_app=WebAppInfo(url=WEB_APP_URL))]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Добро пожаловать в кликер!\n\n"
        "Нажмите кнопку ниже, чтобы открыть кликер:",
        reply_markup=web_app_keyboard
    )

# Обработка данных из Web App
@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        user = message.from_user

        print(f"Получил от {user.id}:", data)
        
        # Если пришли клики
        if 'clicks' in data:
            clicks_to_add = int(data['clicks'])
            
            # Сохраняем в БД
            total_clicks = add_clicks(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                clicks_to_add=clicks_to_add
            )
            
            await message.answer(
                f"✅ +{clicks_to_add} кликов добавлено!\n"
                f"📊 Всего: {total_clicks} кликов"
            )
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@dp.message(Command("me"))
async def cmd_me(message: types.Message):
    user_info = get_user_info(message.from_user.id)
    
    if user_info:
        name = user_info['first_name'] or user_info['username'] or "Аноним"
        response = (
            f"👤 <b>{name}</b>\n"
            f"🆔 ID: {message.from_user.id}\n"
            f"📊 Всего кликов: {user_info['total_clicks']:,}"
        )
        
        if user_info['username']:
            response += f"\n📱 @{user_info['username']}"
            
    else:
        response = "У вас пока нет кликов. Начните кликать в Web App!"
    
    await message.answer(response)

@dp.message(Command("top"))
async def cmd_top(message: types.Message):
    top_users = get_top_10()
    
    if not top_users:
        await message.answer("🏆 Топ пока пуст. Будьте первым!")
        return
    
    response = "🏆 <b>Топ 10 кликеров:</b>\n\n"
    
    for i, (user_id, name, username, total_clicks) in enumerate(top_users, 1):
        response += f"{i}. {name}\n"
        response += f"   👆 Кликов: {total_clicks:,}\n"
        
        if username:
            response += f"   📱 @{username}\n"
            
        response += "\n"
    
    await message.answer(response)

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    # Простая статистика
    conn = sqlite3.connect('clicks_simple.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(total_clicks) FROM users')
    total_clicks_all = cursor.fetchone()[0] or 0
    
    conn.close()
    
    response = (
        f"📊 <b>Общая статистика:</b>\n\n"
        f"👥 Всего игроков: {total_users}\n"
        f"👆 Всего кликов: {total_clicks_all:,}\n"
        f"📈 Среднее: {total_clicks_all // max(total_users, 1):,} кликов на игрока"
    )
    
    await message.answer(response)

async def main():
    # Инициализируем БД
    init_db()
    print("🤖 Бот запущен! Отправьте /start")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())