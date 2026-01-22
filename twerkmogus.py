import logging
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties

# Настройки
API_TOKEN = 'ВАШ_ТОКЕН'
WEB_APP_URL = 'https://ваш-сайт.com'  # URL вашего Web App

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# Хранилище данных (временное)
user_scores = {}

# Главное меню с Web App кнопкой
web_app_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎮 Открыть кликер", web_app=WebAppInfo(url=WEB_APP_URL))]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
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

# Обработка данных из Web App
@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        user_id = message.from_user.id
        
        if data.get('action') == 'save_score':
            score = data.get('score', 0)
            user_scores[user_id] = score
            
            await message.answer(
                f"✅ Ваш счет сохранен!\n\n"
                f"📊 Текущий счет: {score}\n"
                f"🏆 Лучший счет: {user_scores.get(user_id, 0)}"
            )
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@dp.message(Command("score"))
async def cmd_score(message: types.Message):
    user_id = message.from_user.id
    score = user_scores.get(user_id, 0)
    
    await message.answer(
        f"📊 Ваша статистика:\n"
        f"• Текущий счет: {score}\n"
        f"• ID: {user_id}"
    )

async def main():
    print("🤖 Бот запущен! Отправьте /start чтобы увидеть Web App кнопку")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
    