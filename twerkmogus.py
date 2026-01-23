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
from aiogram import F
import asyncio

# Настройки
API_TOKEN = '8002121069:AAF-3SKd3w9YOmeIwNZ0KOVQAqT_LAKxCT0'
WEB_APP_URL = 'https://ivanpanitkov.github.io/twerkmogus/'
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / 'Data'
DB_PATH.mkdir(exist_ok=True)
DB_NAME = DB_PATH / 'clicker.db'

print(f"📁 Путь к БД: {DB_NAME}")
print(f"📁 Существует ли папка Data: {DB_PATH.exists()}")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация БД


def init_db():
    print(f"🔧 Инициализация БД...")

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Основная таблица счетов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_scores (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                total_clicks INTEGER DEFAULT 0,
                current_score INTEGER DEFAULT 0,
                best_score INTEGER DEFAULT 0,
                last_click TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица истории кликов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS click_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                clicks INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Индексы
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_user_scores_score ON user_scores(current_score DESC)')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_click_history_user ON click_history(user_id)')

        conn.commit()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"✅ Созданные таблицы: {[t[0] for t in tables]}")

        conn.close()
        print("✅ БД успешно инициализирована")

    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        import traceback
        traceback.print_exc()

# Функция для добавления кликов


def add_clicks(user_id, username, first_name, last_name, clicks=1):
    """Добавляет клики к счету пользователя"""
    print(f"➕ Добавляем {clicks} кликов для пользователя {user_id}")

    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Получаем текущий счет
        cursor.execute('''
            SELECT current_score, best_score, total_clicks 
            FROM user_scores 
            WHERE user_id = ?
        ''', (user_id,))

        result = cursor.fetchone()

        if result is None:
            # Новый пользователь
            new_score = clicks
            cursor.execute('''
                INSERT INTO user_scores 
                (user_id, username, first_name, last_name, total_clicks, current_score, best_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, clicks, clicks, clicks))
            print(f"✅ Новый пользователь: {clicks} кликов")

        else:
            current_score, best_score, total_clicks = result
            new_score = current_score + clicks
            new_total = total_clicks + clicks
            new_best = max(best_score, new_score)

            cursor.execute('''
                UPDATE user_scores 
                SET current_score = ?,
                    best_score = ?,
                    total_clicks = ?,
                    username = ?,
                    first_name = ?,
                    last_name = ?,
                    updated_at = CURRENT_TIMESTAMP,
                    last_click = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (new_score, new_best, new_total, username, first_name, last_name, user_id))
            print(
                f"✅ Обновлен счет: +{clicks} = {new_score} (было {current_score})")

        # Сохраняем историю кликов
        cursor.execute('''
            INSERT INTO click_history (user_id, clicks)
            VALUES (?, ?)
        ''', (user_id, clicks))

        conn.commit()

        return {
            'current_score': new_score,
            'best_score': new_best if result else clicks,
            'total_clicks': new_total if result else clicks
        }

    except Exception as e:
        print(f"❌ Ошибка добавления кликов: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
        return None

    finally:
        if conn:
            conn.close()

# Функция для получения счета пользователя


def get_user_score(user_id):
    """Получает текущий счет пользователя"""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT current_score, best_score, total_clicks 
            FROM user_scores 
            WHERE user_id = ?
        ''', (user_id,))

        result = cursor.fetchone()

        if result:
            current_score, best_score, total_clicks = result
            return {
                'current_score': current_score,
                'best_score': best_score,
                'total_clicks': total_clicks
            }
        else:
            return {
                'current_score': 0,
                'best_score': 0,
                'total_clicks': 0
            }

    except Exception as e:
        print(f"❌ Ошибка получения счета: {e}")
        return None

    finally:
        if conn:
            conn.close()

# Функция для получения лидерборда


def get_leaderboard(limit=10, user_id=None):
    """Получает таблицу лидеров"""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

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
                current_score,
                total_clicks
            FROM user_scores 
            ORDER BY current_score DESC 
            LIMIT ?
        ''', (limit,))

        rows = cursor.fetchall()

        # Получаем позицию текущего пользователя
        user_position = None
        user_score_data = None

        if user_id:
            # Проверяем есть ли пользователь в таблице
            cursor.execute(
                'SELECT current_score FROM user_scores WHERE user_id = ?', (user_id,))
            user_exists = cursor.fetchone()

            if user_exists:
                cursor.execute('''
                    SELECT COUNT(*) + 1 FROM user_scores 
                    WHERE current_score > (SELECT current_score FROM user_scores WHERE user_id = ?)
                ''', (user_id,))
                position_result = cursor.fetchone()
                user_position = position_result[0] if position_result else 1
            else:
                user_position = None

            # Получаем данные пользователя
            user_score_data = get_user_score(user_id)

        result = {
            'leaderboard': [
                {
                    'user_id': row[0],
                    'name': row[1],
                    'score': row[2],
                    'total_clicks': row[3],
                    'rank': idx + 1
                }
                for idx, row in enumerate(rows)
            ],
            'user_position': user_position,
            'user_data': user_score_data
        }

        return result

    except Exception as e:
        print(f"❌ Ошибка загрузки лидерборда: {e}")
        return None

    finally:
        if conn:
            conn.close()


# Инициализация БД
init_db()

# Инициализация бота
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# Главное меню с Web App кнопкой
web_app_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎮 Открыть кликер",
                        web_app=WebAppInfo(url=WEB_APP_URL))]
    ],
    resize_keyboard=True
)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user = message.from_user
    print(f"🟢 /start от {user.id}")

    # Создаем запись пользователя если нет
    add_clicks(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        clicks=0
    )

    await message.answer(
        "👋 Добро пожаловать в Twerk Mogus Clicker!\n"
        "Нажмите кнопку ниже, чтобы открыть кликер:",
        reply_markup=web_app_keyboard
    )

# Обработчик данных от Web App


@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    """Обработчик данных от Web App"""
    print(f"🟢 Получены данные от Web App от {message.from_user.id}")
    print(f"📦 Данные: {message.web_app_data.data}")

    try:
        data = json.loads(message.web_app_data.data)
        user = message.from_user

        action = data.get('action')
        print(f"📊 Действие: {action}")

        if action == 'add_clicks':
            # Добавляем клики
            clicks = data.get('clicks', 1)
            result = add_clicks(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                clicks=clicks
            )

            if result:
                print(
                    f"✅ Добавлено {clicks} кликов, новый счет: {result['current_score']}")

                # Отправляем обновленный счет
                await send_response(
                    message,
                    {
                        'action': 'update_score',
                        'score': result['current_score'],
                        'clicks_added': clicks
                    }
                )
            else:
                print(f"❌ Ошибка добавления кликов")
                await send_response(
                    message,
                    {
                        'action': 'error',
                        'message': 'Ошибка сохранения'
                    }
                )

        elif action == 'get_score':
            # Получаем текущий счет
            score_data = get_user_score(user.id)
            if score_data:
                print(f"📊 Запрос счета: {score_data['current_score']}")
                await send_response(
                    message,
                    {
                        'action': 'current_score',
                        'current_score': score_data['current_score'],
                        'best_score': score_data['best_score'],
                        'total_clicks': score_data['total_clicks']
                    }
                )

        elif action == 'get_leaderboard':
            # Получаем лидерборд
            leaderboard_data = get_leaderboard(limit=10, user_id=user.id)
            if leaderboard_data:
                print(
                    f"🏆 Запрос лидерборда: {len(leaderboard_data['leaderboard'])} игроков")
                await send_response(
                    message,
                    {
                        'action': 'leaderboard_data',
                        'leaderboard': leaderboard_data['leaderboard'],
                        'user_position': leaderboard_data['user_position'],
                        'user_data': leaderboard_data['user_data']
                    }
                )
            else:
                await send_response(
                    message,
                    {
                        'action': 'error',
                        'message': 'Лидерборд пуст'
                    }
                )

    except json.JSONDecodeError as e:
        print(f"❌ Ошибка JSON: {e}")
        await message.answer(f"❌ Ошибка формата данных: {str(e)}")
    except Exception as e:
        print(f"❌ Ошибка обработки: {e}")
        import traceback
        traceback.print_exc()
        await message.answer(f"❌ Ошибка обработки: {str(e)}")


async def send_response(message: types.Message, data: dict):
    """Отправляет ответ пользователю"""
    try:
        response_text = json.dumps(data, ensure_ascii=False, indent=2)
        await message.answer(f"```json\n{response_text}\n```")
        print(f"📤 Отправлен ответ: {data.get('action')}")
    except Exception as e:
        print(f"❌ Ошибка отправки ответа: {e}")


@dp.message(Command("score"))
async def cmd_score(message: types.Message):
    user_id = message.from_user.id
    print(f"📊 /score от {user_id}")

    score_data = get_user_score(user_id)
    if score_data:
        await message.answer(
            f"📊 Ваша статистика:\n"
            f"• Текущий счет: {score_data['current_score']}\n"
            f"• Лучший счет: {score_data['best_score']}\n"
            f"• Всего кликов: {score_data['total_clicks']}\n"
            f"• ID: {user_id}"
        )
    else:
        await message.answer("❌ Статистика не найдена")


@dp.message(Command("leaderboard"))
async def cmd_leaderboard(message: types.Message):
    user_id = message.from_user.id
    print(f"🏆 /leaderboard от {user_id}")

    leaderboard_data = get_leaderboard(limit=10, user_id=user_id)

    if not leaderboard_data or not leaderboard_data['leaderboard']:
        await message.answer("📊 Таблица лидеров пуста\nПопробуйте сыграть в кликере!")
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

    if leaderboard_data['user_position'] and leaderboard_data['user_data']:
        leaderboard_text += f"\n📊 Ваше место: #{leaderboard_data['user_position']}\n"
        leaderboard_text += f"🏅 Ваш счет: {leaderboard_data['user_data']['current_score']}"
    elif leaderboard_data['user_data']:
        leaderboard_text += f"\n📊 Вы еще не в таблице лидеров\n"
        leaderboard_text += f"🏅 Ваш счет: {leaderboard_data['user_data']['current_score']}"

    await message.answer(leaderboard_text)


@dp.message(Command("debug"))
async def cmd_debug(message: types.Message):
    user_id = message.from_user.id
    print(f"🔧 /debug от {user_id}")

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()

        cursor.execute(
            "SELECT COUNT(*) FROM click_history WHERE user_id = ?", (user_id,))
        history_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM user_scores")
        total_users = cursor.fetchone()[0]

        score_data = get_user_score(user_id)

        debug_text = f"🔧 Отладочная информация (user_id: {user_id}):\n\n"
        debug_text += f"📁 Таблицы: {', '.join([t[0] for t in tables])}\n"
        debug_text += f"👥 Всего пользователей: {total_users}\n"
        debug_text += f"📊 Ваших кликов в истории: {history_count}\n"

        if score_data:
            debug_text += f"\n🎯 Текущий счет: {score_data['current_score']}\n"
            debug_text += f"🏆 Лучший счет: {score_data['best_score']}\n"
            debug_text += f"🖱️ Всего кликов: {score_data['total_clicks']}"
        else:
            debug_text += f"\n🎯 Нет данных о счете"

        await message.answer(debug_text)

    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    finally:
        if conn:
            conn.close()


@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    """Сброс счета (только для отладки)"""
    user_id = message.from_user.id
    print(f"🔄 /reset от {user_id}")

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE user_scores 
            SET current_score = 0,
                total_clicks = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (user_id,))

        conn.commit()
        conn.close()

        await message.answer("✅ Счет сброшен")
        print(f"✅ Счет сброшен для {user_id}")

    except Exception as e:
        await message.answer(f"❌ Ошибка сброса: {str(e)}")


async def main():
    print("🤖 Бот запущен!")
    print(f"🔧 Серверная логика счетчика")
    print(f"🌐 Web App URL: {WEB_APP_URL}")
    print("📝 Отправьте /start в Telegram")
    print("🎮 Кликайте в Web App - клики будут сохраняться на сервере")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
