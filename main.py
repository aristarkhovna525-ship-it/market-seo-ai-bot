import os
import asyncio
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart
from openai import AsyncOpenAI

# Загружаем переменные из файла .env
load_dotenv()

TELEGRAM_TOKEN = os.getenv("8896274098:AAH64u5VslKpQ-mifCNtSEBHlcT0aVbkTPw")
OPENAI_API_KEY = os.getenv("sk-m9lOY4D36GN2Ibv1GiHe8LLF0ovCwjLl")
ADMIN_ID = int(os.getenv("947653274", 0))
CARD_NUMBER = os.getenv("2200702158581749")
BANK_NAME = os.getenv("Т-Банк")
RECEIVER_NAME = os.getenv("Кристина В.")

# Инициализируем бота и диспетчер
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Инициализируем ИИ-клиент с правильным техническим адресом ProxyAPI
ai_client = AsyncOpenAI(
    api_key=OPENAI_API_KEY.strip(), 
    base_url="https://proxyapi.ru"
)

# База данных лимитов в памяти телефона
user_limits = {}
FREE_LIMIT = 2  # Настроено на 2 бесплатные генерации

logging.basicConfig(level=logging.INFO)

@dp.message(CommandStart())
async def start_command(message: Message):
    user_id = message.from_user.id
    
    if user_id not in user_limits:
        user_limits[user_id] = FREE_LIMIT
        
    if isinstance(user_limits[user_id], dict) and user_limits[user_id].get("status") == "premium":
        expire_date_str = user_limits[user_id]["expires"].strftime("%d.%m.%Y")
        status_text = f"👑 У вас активирован *Премиум на месяц*! \n📅 Действует до: **{expire_date_str}**"
    else:
        if isinstance(user_limits[user_id], dict):
            user_limits[user_id] = 0
        status_text = f"🎁 Тебе доступно бесплатно: *{user_limits[user_id]}* генераций."

    await message.answer(
        f"👋 Привет! Я твой ИИ-копирайтер для маркетплейсов.\n\n"
        f"Отправь мне характеристики товара, и я создам SEO-описание.\n\n"
        f"{status_text}",
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "buy_premium")
async def process_buy_premium(callback_query: types.CallbackQuery):
    await callback_query.answer()
    
    payment_text = (
        f"💳 **Подписка на 1 месяц (Премиум):**\n\n"
        f"Для оплаты переведите **490 руб.** на карту:\n"
        f"`{CARD_NUMBER}` ({BANK_NAME})\n"
        f"Получатель: {RECEIVER_NAME}\n\n"
        f"⚠️ **ВАЖНО:** После перевода обязательно пришлите в этот чат **скриншот чека**! "
        f"Администратор проверит его и активирует доступ на 30 дней."
    )
    await callback_query.message.answer(payment_text, parse_mode="Markdown")

@dp.message(F.photo)
async def handle_payment_screenshot(message: types.Message):
    await message.answer("⌛ Ваш чек отправлен на проверку администратору. Обычно это занимает до 15 минут.")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"pay_accept_{message.from_user.id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"pay_decline_{message.from_user.id}")
        ]
    ])
    
    user_info = f"🔔 **Новый чек на проверку (490 руб. / Месяц)**\nОт: @{message.from_user.username or 'без_юзернейма'} (ID: `{message.from_user.id}`)"
    await message.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=message.photo[-1].file_id,
        caption=user_info,
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("pay_"))
async def process_admin_decision(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("Вы не администратор!", show_alert=True)
        return
        
    await callback_query.answer()
    
    data_parts = callback_query.data.split("_")
    action = data_parts[1]
    user_id = int(data_parts[2])
    
    if action == "accept":
        expire_date = datetime.now() + timedelta(days=30)
        expire_date_str = expire_date.strftime("%d.%m.%Y")
        
        user_limits[user_id] = {"status": "premium", "expires": expire_date}
        
        await callback_query.bot.send_message(
            chat_id=user_id,
            text=f"🎉 Оплата успешно подтверждена! Вам предоставлен Премиум-доступ на 1 месяц.\n📅 Подписка активна до: **{expire_date_str}**",
            parse_mode="Markdown"
        )
        await callback_query.message.edit_caption(
            caption=callback_query.message.caption + f"\n\n🟢 **Одобрено! Доступ выдан до {expire_date_str}.**",
            reply_markup=None,
            parse_mode="Markdown"
        )
    elif action == "decline":
        await callback_query.bot.send_message(
            chat_id=user_id,
            text="❌ Оплата не подтверждена. Если произошла ошибка, пожалуйста, свяжитесь с поддержкой."
        )
        await callback_query.message.edit_caption(
            caption=callback_query.message.caption + "\n\n🔴 **Отклонено.**",
            reply_markup=None,
            parse_mode="Markdown"
        )

@dp.message(F.text)
async def generate_seo_description(message: Message):
    user_id = message.from_user.id
    user_input = message.text
    
    is_premium = False
    if user_id in user_limits and isinstance(user_limits[user_id], dict):
        if user_limits[user_id].get("status") == "premium":
            if datetime.now() < user_limits[user_id]["expires"]:
                is_premium = True
            else:
                user_limits[user_id] = 0
                
    if not is_premium:
        if user_id not in user_limits:
            user_limits[user_id] = FREE_LIMIT
            
        if isinstance(user_limits[user_id], int) and user_limits[user_id] <= 0:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Купить безлимит за 490₽", callback_data="buy_premium")]
            ])
            await message.answer(
                "⚠️ *У вас закончились бесплатные генерации!*\n\nЧтобы продолжить пользоваться ботом без ограничений, приобретите Премиум-доступ.",
                reply_markup=kb,
                parse_mode="Markdown"
            )
            return

    prompt = (
        f"Напиши продающее SEO-описание товара на основе данных: {user_input}. "
        f"Используй ключевые слова, разбей на абзацы, добавь преимущества и эмодзи. Язык: русский."
    )
    
    try:
        response = await ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.7
        )
        
        if not is_premium:
            user_limits[user_id] -= 1
            status_limit_text = f"\n\n_Осталось бесплатных генераций: {user_limits[user_id]}_"
        else:
            status_limit_text = "\n\n_👑 Действует Премиум-подписка_"
            
        result_text = response.choices[0].message.content
        result_text += status_limit_text
        
        await message.answer(result_text, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Ошибка ИИ: {e}")
        await message.answer(
            "❌ Ошибка сети или неверный API-ключ.\nПожалуйста, проверьте баланс в личном кабинете прокси-сервиса"
        )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен")
