# Noteme

Telegram-бот (aiogram 3.x) + FastAPI: отслеживание важных дат, красивых дат-милестоунов, заметки с тегами. Python 3.12, PostgreSQL, Redis, LangGraph, sqladmin.

## Запуск и тесты

- Запуск: `uv run python -m app`
- Тесты: `uv run python -m pytest -q`
- Тесты с реальной БД падают если PostgreSQL не запущен на 5433 — это нормально, unit-тесты должны проходить
- Пакетный менеджер: uv (не pip, не poetry)
- Dev-порты: PostgreSQL=5433, Redis=6380, App=8000

## GitHub Project — управление задачами

Проект: `ipolotsky/projects/1` (NotADate)
Репозиторий: `ipolotsky/noteme`

### Статусы колонок

- **Agent tasks** — задачи, готовые к работе
- **In progress** — задача взята в работу
- **In review** — PR создан, ждет ревью
- **Done** — задача закрыта

### Лейблы

- `agent` — задача обработана агентом
- `unclear` — есть сомнения, нужна проверка

### Команда "Следующая задача"

Когда пользователь просит взять следующую задачу:

1. Проверить, нет ли открытого PR с лейблом `agent`. Если есть — сообщить и не брать новую.
2. Запросить задачи из GitHub Project через GraphQL (см. ниже). Искать:
   - сначала задачи в "In progress" с лейблом `agent` (незавершенная работа);
   - затем задачи в "Agent tasks".
   - только из репозитория `ipolotsky/noteme`.
3. Отсортировать по приоритету: P0 > P1 > P2 > без приоритета.
4. Показать пользователю задачу и план работы. Дождаться подтверждения.
5. После подтверждения:
   - перевести задачу в "In progress";
   - повесить лейбл `agent`;
   - создать ветку `feature/{number}-{slug}` от main;
   - выполнить работу;
   - прогнать тесты;
   - закоммитить и запушить.
6. Спросить пользователя, создавать ли PR.
7. После подтверждения:
   - создать PR с описанием работы, назначить на `ipolotsky`;
   - если есть сомнения — лейбл `unclear` и пометка в описании PR;
   - перевести задачу в "In review";
   - `Closes #{number}` в теле PR.

### GraphQL-запрос для поиска задач

```graphql
query($owner: String!, $number: Int!) {
  user(login: $owner) {
    projectV2(number: $number) {
      items(first: 100) {
        nodes {
          id
          content {
            ... on Issue {
              number
              title
              body
              repository { nameWithOwner }
              labels(first: 10) { nodes { name } }
            }
          }
          status: fieldValueByName(name: "Status") {
            ... on ProjectV2ItemFieldSingleSelectValue { name }
          }
          priority: fieldValueByName(name: "Priority") {
            ... on ProjectV2ItemFieldSingleSelectValue { name }
          }
        }
      }
    }
  }
}
```

Параметры: `owner = "ipolotsky"`, `number = 1`.

### Project IDs (для мутаций статусов)

- Project ID: `PVT_kwHOAKp2184BO0WQ`
- Status field ID: `PVTSSF_lAHOAKp2184BO0WQzg9aHlw`
- Option IDs:
  - Agent tasks: `80d6ece2`
  - In progress: `47fc9ee4`
  - In review: `df73e18b`
  - Done: `98236657`

### Мутация смены статуса

```graphql
mutation {
  updateProjectV2ItemFieldValue(input: {
    projectId: "PVT_kwHOAKp2184BO0WQ",
    itemId: "<ITEM_ID>",
    fieldId: "PVTSSF_lAHOAKp2184BO0WQzg9aHlw",
    value: { singleSelectOptionId: "<OPTION_ID>" }
  }) { projectV2Item { id } }
}
```
