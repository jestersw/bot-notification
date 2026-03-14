#!/usr/bin/env python3
import logging
import json
import os
import uuid
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ─── Настройки ────────────────────────────────────────────────────────────────
TOKEN = os.getenv("BOT_TOKEN")
MOSCOW_TZ = pytz.timezone("Europe/Moscow")
REMINDERS_FILE = "reminders.json"

START_IMAGE = "AgACAgIAAxkBAAMLabQHgugNMXqeD4qQs_1mKIj_GaEAAqIWaxtA9qFJ5Lmh9wazMK8BAAMCAAN4AAM6BA"   # картинка в приветственном сообщении
FOOD_IMAGE  = "AgACAgIAAxkBAAMNabQHkhmA-2WFy12DvscOUmzt5BEAAqMWaxtA9qFJa6T8Xt6Pgi8BAAMCAAN4AAM6BA"    # картинка в напоминании о еде

# ─── Логирование ──────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Хранилище напоминаний ────────────────────────────────────────────────────
# Структура: { "chat_id": [ {"id": "...", "hour": H, "minute": M}, ... ] }
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
        text = (
            "Привет, Катюша! 🌸\n\n"
            "Не забудь хорошо покушать! :3 \n\n"
            "Твой организм скажет тебе спасибо 💕"
        )
        await app_ref.bot.send_photo(chat_id=chat_id, photo=FOOD_IMAGE, caption=text)
        
        logger.info(f"Напоминание отправлено → chat_id={chat_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки chat_id={chat_id}: {e}")

# ─── Планировщик ─────────────────────────────────────────────────────────────
def schedule_reminder(chat_id: int, hour: int, minute: int, reminder_id: str):
    job_id = f"food_{chat_id}_{reminder_id}"
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
    logger.info(f"Запланировано {hour:02d}:{minute:02d} → chat_id={chat_id}")

def remove_scheduled(chat_id: int, reminder_id: str):
    job_id = f"food_{chat_id}_{reminder_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

# ─── Вспомогательные ─────────────────────────────────────────────────────────
def get_user_reminders(chat_id: int) -> list:
    return reminders.get(str(chat_id), [])

def reminder_list_text(chat_id: int) -> str:
    rems = get_user_reminders(chat_id)
    if not rems:
        return "У тебя пока нет напоминаний. "
    lines = ["Твои напоминания:"]
    for r in rems:
        lines.append(f"  • {r['hour']:02d}:{r['minute']:02d}")
    return "\n".join(lines)

def main_menu_text(chat_id: int) -> str:
    return (
        "Привет, Катюша! 🌸\n\n"
        "Я каждый день буду напоминать тебе вкусно покушать! \n\n"
        + reminder_list_text(chat_id)
    )

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Создать напоминание", callback_data="create")],
        [InlineKeyboardButton("Удалить напоминание",  callback_data="delete_list")],
    ])

async def edit_text(query, text, kb):
    """Редактировать сообщение — учитываем, есть ли фото."""
    if query.message.photo:
        await query.edit_message_caption(caption=text, reply_markup=kb, parse_mode="Markdown")
    else:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

# ─── /start ───────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = main_menu_text(chat_id)
    kb   = main_menu_kb()

    await update.message.reply_photo(
    photo=START_IMAGE, caption=text, reply_markup=kb, parse_mode="Markdown"
)

# ─── Кнопки ───────────────────────────────────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data    = query.data

    # Назад
    if data == "back":
        await edit_text(query, main_menu_text(chat_id), main_menu_kb())

    # Создать — выбор часа
    elif data == "create":
        rows, row = [], []
        for h in range(6, 24):
            row.append(InlineKeyboardButton(f"{h:02d}:__", callback_data=f"hour_{h}"))
            if len(row) == 4:
                rows.append(row); row = []
        if row: rows.append(row)
        rows.append([InlineKeyboardButton("◀️ Назад", callback_data="back")])
        await edit_text(query, "Выбери *час* для напоминания:", InlineKeyboardMarkup(rows))

    # Выбор минут
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
        await edit_text(query, f"Выбран час: *{hour:02d}*\nТеперь выбери *минуты*:", kb)

    # Сохранить
    elif data.startswith("min_"):
        minute = int(data.split("_")[1])
        hour   = context.user_data.get("selected_hour", 12)
        rid    = str(uuid.uuid4())[:8]

        key = str(chat_id)
        reminders.setdefault(key, []).append({"id": rid, "hour": hour, "minute": minute})
        save_reminders(reminders)
        schedule_reminder(chat_id, hour, minute, rid)

        text = (
            f"✅ Готово!\n\n"
            f"Каждый день в *{hour:02d}:{minute:02d}* я напомню тебе покушать! 💕\n\n"
            + reminder_list_text(chat_id)
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить ещё", callback_data="create")],
            [InlineKeyboardButton("◀️ В главное меню",  callback_data="back")],
        ])
        await edit_text(query, text, kb)

    # Список для удаления
    elif data == "delete_list":
        rems = get_user_reminders(chat_id)
        if not rems:
            await edit_text(
                query, "У тебя нет активных напоминаний",
                InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back")]])
            )
            return

        buttons = [
            [InlineKeyboardButton(f"🗑 {r['hour']:02d}:{r['minute']:02d}", callback_data=f"del_{r['id']}")]
            for r in rems
        ]
        buttons.append([InlineKeyboardButton("Удалить все", callback_data="delete_all")])
        buttons.append([InlineKeyboardButton("◀️ Назад",       callback_data="back")])
        await edit_text(query, "Выбери напоминание для удаления:", InlineKeyboardMarkup(buttons))

    # Удалить одно
    elif data.startswith("del_"):
        rid = data[4:]
        key = str(chat_id)
        reminders[key] = [r for r in reminders.get(key, []) if r["id"] != rid]
        save_reminders(reminders)
        remove_scheduled(chat_id, rid)

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Удалить ещё",    callback_data="delete_list")],
            [InlineKeyboardButton("◀️ В главное меню", callback_data="back")],
        ])
        await edit_text(query, "🗑 Напоминание удалено!\n\n" + reminder_list_text(chat_id), kb)

    # Удалить все
    elif data == "delete_all":
        key = str(chat_id)
        for r in reminders.get(key, []):
            remove_scheduled(chat_id, r["id"])
        reminders[key] = []
        save_reminders(reminders)

        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В главное меню", callback_data="back")]])
        await edit_text(query, "🗑 Все напоминания удалены!", kb)

# ─── Инициализация ────────────────────────────────────────────────────────────
async def post_init(application: Application):
    global app_ref
    app_ref = application
    for chat_id_str, rems in reminders.items():
        for r in rems:
            schedule_reminder(int(chat_id_str), r["hour"], r["minute"], r["id"])
    scheduler.start()
    logger.info(f"Планировщик запущен. Пользователей: {len(reminders)}")

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(button_handler))
    logger.info("Бот запущен ")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
