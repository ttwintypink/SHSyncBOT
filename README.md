# Discord Role Sync Bot (Linux)

Синхронизация ролей между двумя серверами.

## Логика
- **Приватка**: если у пользователя есть роль `SH` (1454842309421170719)
  - **Паблик**: выдать `SH` (1299444337658171422), снять `FUN SH` (1315028367044513876)
- Если в приватке роли `SH` нет (включая выход/кик/бан)
  - **Паблик**: снять `SH`, выдать `FUN SH`

Есть обработчики событий + периодическая сверка (по умолчанию каждые 10 минут).

## Требования
- Python 3.10+ (желательно 3.11/3.12)
- Права бота в паблике: **Manage Roles**
- В Dev Portal включить: **Privileged Gateway Intents -> Server Members Intent**

ВАЖНО: роль бота в **паблике** должна быть **выше** ролей SH и FUN SH.

## Установка и запуск
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env   # вставь DISCORD_TOKEN

python bot.py
```

## Команды
- `/sync @user` — синхронизировать одного пользователя (нужен Manage Roles)
- `/syncall` — сверка всех кандидатов (у кого SH/FUN SH в паблике)

## systemd (пример)
Смотри файл `role-sync-bot.service.example`.
