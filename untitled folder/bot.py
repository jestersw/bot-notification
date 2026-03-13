#!/usr/bin/env python3

import logging
import json
import os
import asyncio
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ─── Настройки ────────────────────────────────────────────────────────────────
TOKEN = os.getenv("BOT_TOKEN", "8665791853:AAGyiGxp5Sbh8AWbqlEHJX17r1wivpUVJP0")
MOSCOW_TZ = pytz.timezone("Europe/Moscow")
REMINDERS_FILE = "reminders.json"

# ─── Логирование ──────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Хранилище напоминаний ────────────────────────────────────────────────────
def load_reminders() -> dict:
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_reminders(data: dict):
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

reminders: dict = load_reminders()
scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)
app_ref: Application | None = None

# ─── Отправка напоминания ─────────────────────────────────────────────────────
async def send_food_reminder(chat_id: int):
    try:
        with open("nyan.jpg", "rb") as photo:
            await app_ref.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=(
                    "Привет, Катюша! 🌸\n\n"
                    "Не забудь хорошо покушать! :3 \n\n"
                    "Твой организм скажет тебе спасибо~"
                ),
            )
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# ─── Планировщик ─────────────────────────────────────────────────────────────
def schedule_reminder(chat_id: int, hour: int, minute: int):
    job_id = f"food_{chat_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(
        send_food_reminder,
        trigger="cron",
        hour=hour,
        minute=minute,
        timezone=MOSCOW_TZ,
        id=job_id,
        args=[chat_id],
        replace_existing=True,
    )
    logger.info(f"Запланировано: chat_id={chat_id} → {hour:02d}:{minute:02d} МСК")

def remove_scheduled(chat_id: int):
    job_id = f"food_{chat_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

# ─── Главное меню ─────────────────────────────────────────────────────────────
def main_menu_text(chat_id: int) -> str:
    base = "Привет, Катюша! 🌸\n\nЯ каждый день буду напоминать тебе вкусно покушать! "
    key = str(chat_id)
    if key in reminders:
        r = reminders[key]
        base += f"\n\n Активное напоминание: *{r['hour']:02d}:{r['minute']:02d}* по МСК"
    else:
        base += "\n\nУ тебя пока нет напоминаний — создай первое! "
    return base

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Создать напоминание", callback_data="create")],
        [InlineKeyboardButton("Удалить напоминание",  callback_data="delete")],
    ])

# ─── /start ───────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        main_menu_text(chat_id),
        reply_markup=main_menu_kb(),
        parse_mode="Markdown",
    )

# ─── Обработчик кнопок ────────────────────────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data

    # ── Назад / главное меню ──────────────────────────────────────────────────
    if data == "back":
        await query.edit_message_text(
            main_menu_text(chat_id),
            reply_markup=main_menu_kb(),
            parse_mode="Markdown",
        )

    # ── Создать: выбор часа ───────────────────────────────────────────────────
    elif data == "create":
        hours = list(range(7, 24))   # 07 – 23
        rows = []
        row = []
        for h in hours:
            row.append(InlineKeyboardButton(f"{h:02d}:__", callback_data=f"hour_{h}"))
            if len(row) == 4:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        rows.append([InlineKeyboardButton("◀️ Назад", callback_data="back")])

        await query.edit_message_text(
            "Выбери *час* для ежедневного напоминания (по МСК):",
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode="Markdown",
        )

    # ── Выбор минут ───────────────────────────────────────────────────────────
    elif data.startswith("hour_"):
        hour = int(data.split("_")[1])
        context.user_data["selected_hour"] = hour

        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{hour:02d}:00", callback_data="min_0"),
                InlineKeyboardButton(f"{hour:02d}:15", callback_data="min_15"),
                InlineKeyboardButton(f"{hour:02d}:30", callback_data="min_30"),
                InlineKeyboardButton(f"{hour:02d}:45", callback_data="min_45"),
            ],
            [InlineKeyboardButton("◀️ Назад", callback_data="create")],
        ])
        await query.edit_message_text(
            f"Выбран час: *{hour:02d}*\nТеперь выбери *минуты*:",
            reply_markup=kb,
            parse_mode="Markdown",
        )

    # ── Сохранить напоминание ─────────────────────────────────────────────────
    elif data.startswith("min_"):
        minute = int(data.split("_")[1])
        hour = context.user_data.get("selected_hour", 12)

        reminders[str(chat_id)] = {"hour": hour, "minute": minute}
        save_reminders(reminders)
        schedule_reminder(chat_id, hour, minute)

        await query.edit_message_text(
            f"✅ Готово!\n\n"
            f"Каждый день в *{hour:02d}:{minute:02d}* я буду напоминать тебе покушать! 💕",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ В главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown",
        )

    # ── Удалить напоминание ───────────────────────────────────────────────────
    elif data == "delete":
        key = str(chat_id)
        if key in reminders:
            del reminders[key]
            save_reminders(reminders)
            remove_scheduled(chat_id)
            text = "🗑 Напоминание удалено!"
        else:
            text = "У тебя нет активных напоминаний."

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ В главное меню", callback_data="back")]
            ]),
        )

# ─── Инициализация при старте ─────────────────────────────────────────────────
async def post_init(application: Application):
    global app_ref
    app_ref = application

    # Восстанавливаем все сохранённые напоминания
    for chat_id_str, r in reminders.items():
        schedule_reminder(int(chat_id_str), r["hour"], r["minute"])

    scheduler.start()
    logger.info(f"Планировщик запущен. Загружено напоминаний: {len(reminders)}")

# ─── Точка входа ──────────────────────────────────────────────────────────────
def main():
    application = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Бот запущен")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
