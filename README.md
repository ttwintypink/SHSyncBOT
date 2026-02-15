# Role Sync Bot v3

## Почему раньше “нет команд”
Если команды синкались как **global**, Discord может показывать их с задержкой.
В этой версии при старте:
- грузим cog
- делаем `tree.copy_global_to(guild=...)`
- делаем `tree.sync(guild=...)` для двух серверов

В логах после старта должно быть:
`Synced 2 app command(s) to guild ...: sync, syncall`

## Важно
Приглашать бота лучше с scopes:
- `bot`
- `applications.commands`

И интенты:
- Dev Portal -> Bot -> Privileged Gateway Intents -> Server Members Intent (включить)

## Команды
- `/sync @user`
- `/syncall`
