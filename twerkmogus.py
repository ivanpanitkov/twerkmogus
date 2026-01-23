import os
import sqlite3
from pathlib import Path
import logging
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    WebAppInfo, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram.filters import Command
import asyncio

# Настройки
API_TOKEN = '8002121069:AAF-3SKd3w9YOmeIwNZ0KOVQAqT_LAKxCT0'
WEB_APP_URL = 'https://ivanpanitkov.github.io/twerkmogus/'  # URL вашего Web App
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / 'Data'
DB_PATH.mkdir(exist_ok=True)  # Создаем папку data если нет
DB_NAME = DB_PATH / 'clicker.db'

print(f"📁 База данных будет создана: {DB_NAME}")

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация БД
def init_db():
    print(f"🔧 Инициализация БД по пути: {DB_NAME}")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Таблица истории всех игр
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            score INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица лучших результатов (лидерборд)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leaderboard (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            best_score INTEGER DEFAULT 0,
            total_games INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Индексы для быстрого поиска
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON scores(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_score ON scores(score DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_leaderboard_score ON leaderboard(best_score DESC)')
    
    conn.commit()
    
    # Проверяем создание таблиц
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"✅ Созданные таблицы: {[t[0] for t in tables]}")
    
    conn.close()

# Функция для сохранения счета
def save_score(user_id, username, first_name, last_name, score):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # 1. Сохраняем в историю (все игры)
        cursor.execute('''
            INSERT INTO scores (user_id, username, first_name, last_name, score)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name, score))
        
        # 2. Обновляем лидерборд
        cursor.execute('''
            INSERT INTO leaderboard (user_id, username, first_name, last_name, best_score, total_games)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                best_score = MAX(excluded.best_score, leaderboard.best_score),
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                total_games = leaderboard.total_games + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE excluded.best_score > leaderboard.best_score
        ''', (user_id, username, first_name, last_name, score))
        
        conn.commit()
        print(f"💾 Сохранен счет {score} для пользователя {user_id}")
        
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        conn.rollback()
        
    finally:
        conn.close()

# Функция для получения лидерборда
def get_leaderboard(limit=10, user_id=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # Получаем топ игроков
        cursor.execute('''
            SELECT 
                user_id,
                COALESCE(
                    CASE 
                        WHEN first_name IS NOT NULL AND last_name IS NOT NULL 
                        THEN first_name || ' ' || last_name
                        WHEN first_name IS NOT NULL 
                        THEN first_name
                        WHEN username IS NOT NULL 
                        THEN '@' || username
                        ELSE 'Аноним'
                    END,
                    'Аноним'
                ) as name,
                best_score,
                total_games
            FROM leaderboard 
            ORDER BY best_score DESC 
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        
        # Получаем позицию текущего пользователя
        user_position = None
        user_score = 0
        if user_id:
            cursor.execute('''
                SELECT COUNT(*) + 1 FROM leaderboard 
                WHERE best_score > (SELECT best_score FROM leaderboard WHERE user_id = ?)
            ''', (user_id,))
            position_result = cursor.fetchone()
            user_position = position_result[0] if position_result else None
            
            # Получаем данные текущего пользователя
            cursor.execute('''
                SELECT best_score FROM leaderboard WHERE user_id = ?
            ''', (user_id,))
            user_data = cursor.fetchone()
            user_score = user_data[0] if user_data else 0
            
        result = {
            'leaderboard': [
                {
                    'user_id': row[0],
                    'name': row[1],
                    'score': row[2],
                    'games': row[3],
                    'rank': idx + 1
                }
                for idx, row in enumerate(rows)
            ],
            'user_position': user_position,
            'user_score': user_score
        }
        
        return result
        
    except Exception as e:
        print(f"❌ Ошибка загрузки лидерборда: {e}")
        return None
        
    finally:
        conn.close()

# Инициализация БД при запуске
init_db()

# Инициализация бота
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# Главное меню с Web App кнопкой
web_app_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎮 Открыть кликер", web_app=WebAppInfo(url=WEB_APP_URL))]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    await message.answer(
        "👋 Добро пожаловать в Web App кликер!\n\n"
        "Нажмите кнопку ниже, чтобы открыть интерактивный кликер прямо в Telegram:",
        reply_markup=web_app_keyboard
    )
    
    # Или через inline кнопку:
    inline_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🚀 Открыть Web App кликер", 
                web_app=WebAppInfo(url=WEB_APP_URL)
            )]
        ]
    )
    await message.answer("Или откройте через inline кнопку:", reply_markup=inline_keyboard)

@dp.message(Command("score"))
async def cmd_score(message: types.Message):
    """Показывает статистику пользователя"""
    user_id = message.from_user.id
    
    # Получаем данные из БД
    leaderboard_data = get_leaderboard(user_id=user_id)
    
    if leaderboard_data:
        user_score = leaderboard_data['user_score']
        user_position = leaderboard_data['user_position']
        
        position_text = f"• Позиция в таблице: #{user_position}" if user_position else "• Позиция: не в таблице"
        
        await message.answer(
            f"📊 Ваша статистика:\n"
            f"• Лучший счет: {user_score}\n"
            f"{position_text}\n"
            f"• ID: {user_id}"
        )
    else:
        await message.answer("❌ Не удалось загрузить статистику")

@dp.message(Command("leaderboard"))
async def cmd_leaderboard(message: types.Message):
    """Показывает таблицу лидеров"""
    user_id = message.from_user.id
    leaderboard_data = get_leaderboard(limit=10, user_id=user_id)
    
    if not leaderboard_data or not leaderboard_data['leaderboard']:
        await message.answer("📊 Таблица лидеров пуста")
        return
    
    leaderboard_text = "🏆 Топ 10 игроков:\n\n"
    
    for player in leaderboard_data['leaderboard']:
        medal = ""
        if player['rank'] == 1:
            medal = "🥇 "
        elif player['rank'] == 2:
            medal = "🥈 "
        elif player['rank'] == 3:
            medal = "🥉 "
        
        leaderboard_text += f"{medal}{player['rank']}. {player['name']}: {player['score']} очков\n"
    
    # Добавляем информацию о текущем пользователе
    if leaderboard_data['user_position']:
        leaderboard_text += f"\n📊 Ваше место: #{leaderboard_data['user_position']}\n"
        leaderboard_text += f"🏅 Ваш лучший счет: {leaderboard_data['user_score']}"
    
    await message.answer(leaderboard_text)

@dp.message(lambda message: message.web_app_data)
async def handle_web_app_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        user = message.from_user
        
        if data.get('action') == 'save_score':
            score = data.get('score', 0)
            
            # Сохраняем в БД
            save_score(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                score=score
            )
            
            # Показываем уведомление
            exit_save = data.get('exit_save', False)
            auto_save = data.get('auto_save', False)
            
            if exit_save:
                # Не отправляем сообщение при автосохранении при выходе
                return
            elif auto_save:
                await message.answer(f"📊 Автосохранение: {score} очков")
            else:
                await message.answer(f"✅ Сохранено! Ваш счет: {score}")
                
        elif data.get('action') == 'show_leaderboard':
            # Показываем лидерборд
            leaderboard_data = get_leaderboard(limit=10, user_id=user.id)
            
            if leaderboard_data and leaderboard_data['leaderboard']:
                leaderboard_text = "🏆 Топ 10 игроков:\n\n"
                
                for player in leaderboard_data['leaderboard']:
                    medal = ""
                    if player['rank'] == 1:
                        medal = "🥇 "
                    elif player['rank'] == 2:
                        medal = "🥈 "
                    elif player['rank'] == 3:
                        medal = "🥉 "
                    
                    leaderboard_text += f"{medal}{player['rank']}. {player['name']}: {player['score']} очков\n"
                
                if leaderboard_data['user_position']:
                    leaderboard_text += f"\n📊 Ваше место: #{leaderboard_data['user_position']}\n"
                    leaderboard_text += f"🏅 Ваш лучший счет: {leaderboard_data['user_score']}"
                
                await message.answer(leaderboard_text)
            else:
                await message.answer("📊 Таблица лидеров пуста")
                
    except Exception as e:
        logger.error(f"Ошибка обработки Web App данных: {e}")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Показывает справку"""
    help_text = """
🤖 *Доступные команды:*

/start - Начать работу с ботом
/score - Посмотреть свою статистику
/leaderboard - Таблица лидеров
/help - Показать это сообщение

🎮 *Как играть:*
1. Нажмите кнопку "🎮 Открыть кликер"
2. Игра откроется прямо в Telegram
3. Кликайте по персонажу для набора очков
4. Результат автоматически сохранится
"""
    await message.answer(help_text)

async def main():
    """Основная функция запуска бота"""
    print("🤖 Бот запущен!")
    print("🔧 Используется БД:", DB_NAME)
    print("🌐 Web App URL:", WEB_APP_URL)
    print("📝 Отправьте /start чтобы увидеть Web App кнопку")
    
    # Удаляем вебхук и запускаем поллинг
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")