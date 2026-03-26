# Бот-напоминалка о еде 

Telegram-бот, который каждый день в выбранное время отправляет напоминание покушать 

Может быть запущен как локально, так и на сервере, чтобы поддерживать работу бота 24/7 (напр. с бесплатной версией от [railway.app](https://railway.app))

Сделан just for fun для моей подруги =)

![telegram-cloud-photo-size-2-5305792591217497763-x](https://github.com/user-attachments/assets/75d8efb9-5719-4403-aae9-26d743b64c2d)

---

## Запуск локально

```bash
pip install -r requirements.txt
export BOT_TOKEN="твой_токен"
python bot.py
```

---

## Деплой на Railway

1. Залей папку на GitHub
2. Зайди на [railway.app](https://railway.app) → **New Project → Deploy from GitHub**
3. В **Variables** добавь `BOT_TOKEN = твой_токен`

---

## Файлы

| Файл | Описание |
|------|----------|
| `bot.py` | Основной код бота |
| `requirements.txt` | Зависимости Python |
| `railway.json` | Конфиг для Railway |
| `food.jpg` | Картинка в напоминании (только локально) |
| `start.jpg` | Картинка в приветствии (только локально) |

---

## Как пользоваться

- `/start` — открыть меню
- **Создать напоминание** — выбрать час и минуты (по МСК)
- **Удалить напоминание** — удалить одно или все сразу
