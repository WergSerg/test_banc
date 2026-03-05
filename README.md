# Payment Service

Сервис для работы с платежами по заказам. Поддерживает наличные и банковские платежи (эквайринг), синхронизацию статусов с внешним API банка.

## Содержание
- [Архитектура](#архитектура)
- [Схема базы данных](#схема-базы-данных)
- [API Endpoints](#api-endpoints)
- [Установка и запуск](#установка-и-запуск)
- [Тестирование](#тестирование)
- [Docker](#docker)

## Архитектура

Проект построен с использованием чистой архитектуры и разделен на слои:
```
backend/
├── api/              # HTTP слой (роутеры, зависимости)
├── clients/          # Клиенты для внешних сервисов
├── core/             # Конфигурация, подключение к БД
├── domain/           # Модели, схемы, enums
├── exceptions/       # Кастомные исключения
├── middleware/       # Middleware компоненты
├── repositories/     # Слой доступа к данным
├── services/         # Бизнес-логика
├── tasks/            # Фоновые задачи
├── tests/            # Тесты
└── utils/            # Утилиты
```

### Ключевые паттерны:
- **Repository Pattern** - абстракция доступа к данным
- **Strategy Pattern** - разные процессоры для типов платежей
- **Dependency Injection** - слабая связанность компонентов

### Механизмы синхронизации с банком

Сервис поддерживает два механизма синхронизации статусов платежей с банком:

1. **Webhook** (основной) - банк сам присылает уведомления об изменении статуса
2. **Polling** (резервный) - мы периодически опрашиваем банк на случай пропущенных вебхуков


## Схема базы данных


### Таблица orders
| Поле | Тип | Описание | Ограничения |
|------|-----|----------|-------------|
| id | INTEGER | Первичный ключ | PRIMARY KEY |
| amount | DECIMAL(10,2) | Сумма заказа | > 0 |
| paid_amount | DECIMAL(10,2) | Оплаченная сумма | >= 0, <= amount |
| status | VARCHAR(20) | Статус заказа | 'unpaid', 'partially_paid', 'paid' |
| created_at | TIMESTAMP | Дата создания | DEFAULT now() |
| updated_at | TIMESTAMP | Дата обновления | on update |

### Таблица payments
| Поле | Тип | Описание | Ограничения |
|------|-----|----------|-------------|
| id | INTEGER | Первичный ключ | PRIMARY KEY |
| order_id | INTEGER | ID заказа | FOREIGN KEY |
| amount | DECIMAL(10,2) | Сумма платежа | > 0 |
| type | VARCHAR(20) | Тип платежа | 'cash', 'acquiring' |
| status | VARCHAR(20) | Статус платежа | 'pending', 'processing', 'completed', 'failed', 'refunded' |
| bank_payment_id | VARCHAR(100) | ID в системе банка | NULL |
| bank_status | VARCHAR(50) | Статус в банке | NULL |
| bank_paid_at | TIMESTAMP | Дата оплаты в банке | NULL |
| error_message | TEXT | Сообщение об ошибке | NULL |
| created_at | TIMESTAMP | Дата создания | DEFAULT now() |
| updated_at | TIMESTAMP | Дата обновления | on update |

### Связи
- Order (1) -> (∞) Payment (один заказ может иметь много платежей)
- При удалении заказа каскадное удаление платежей

### Индексы
- `ix_orders_status` - для быстрого поиска по статусу
- `ix_payments_order_id` - для связи с заказами
- `ix_payments_bank_payment_id` - для поиска по ID банка
- `ix_payments_status` - для фильтрации по статусу

## API Endpoints

### Заказы

#### GET /api/v1/orders
Получение списка заказов
```bash
curl -H "X-API-Key: test-api-key" http://localhost:8000/api/v1/orders?skip=0&limit=100
```

#### GET /api/v1/orders/{order_id}
Получение заказа по ID
```bash
curl -H "X-API-Key: test-api-key" http://localhost:8000/api/v1/orders/1
```

#### GET /api/v1/orders/unpaid/list
Получение неоплаченных заказов
```bash
curl -H "X-API-Key: test-api-key" http://localhost:8000/api/v1/orders/unpaid/list
```

### Платежи

#### POST /api/v1/payments
Создание нового платежа
```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "X-API-Key: test-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": 1,
    "amount": "500.00",
    "type": "cash"
  }'
```

#### POST /api/v1/payments/refund
Возврат платежа
```bash
curl -X POST http://localhost:8000/api/v1/payments/refund \
  -H "X-API-Key: test-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "payment_id": 1
  }'
```

#### GET /api/v1/payments/order/{order_id}
Получение всех платежей заказа
```bash
curl -H "X-API-Key: test-api-key" http://localhost:8000/api/v1/payments/order/1
```

#### POST /api/v1/payments/sync
Синхронизация с банком (обновление статусов)
```bash
curl -X POST http://localhost:8000/api/v1/payments/sync \
  -H "X-API-Key: test-api-key"
```

### Вебхуки

#### POST /api/v1/webhooks/bank
Прием вебхуков от банка об изменении статуса платежа
```bash
curl -X POST http://localhost:8000/api/v1/webhooks/bank \
  -H "X-Signature: <signature>" \
  -H "Content-Type: application/json" \
  -d '{
    "payment_id": "bank_123",
    "order_id": 1,
    "amount": "500.00",
    "status": "completed",
    "paid_at": "2024-01-01T12:00:00",
    "timestamp": "2024-01-01T12:00:00"
  }'
```

## Polling endpoints

### POST /api/v1/payments/{payment_id}/poll
Принудительный опрос конкретного платежа

```bash
curl -X POST http://localhost:8000/api/v1/payments/1/poll \
  -H "X-API-Key: test-api-key"
POST /api/v1/payments/poll/stale
Опрос всех "зависших" платежей (старше 30 минут)

bash
curl -X POST http://localhost:8000/api/v1/payments/poll/stale \
  -H "X-API-Key: test-api-key"
```

## Установка и запуск

### Локальный запуск

1. Клонировать репозиторий:
```bash
git clone <repository-url>
cd payment-service
```

2. Создать виртуальное окружение:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Установить зависимости:
```bash
pip install -r requirements.txt
```

4. Настроить переменные окружения:
```bash
cp .env.example .env
# Отредактировать .env файл
```

5. Запустить PostgreSQL:
```bash
# Через Docker
docker run -d \
  --name payment-postgres \
  -e POSTGRES_USER=payment_user \
  -e POSTGRES_PASSWORD=payment_pass \
  -e POSTGRES_DB=payment_db \
  -p 5432:5432 \
  postgres:15
```

6. Инициализировать базу данных:
```bash
python backend/scripts/init_db.py
```

7. Запустить сервер:
```bash
uvicorn backend.main:app --reload
```

8. Запустить мок-сервер банка (в отдельном терминале):
```bash
cd mock_bank
python server.py
```

Сервис будет доступен по адресу: http://localhost:8000
Документация Swagger: http://localhost:8000/docs

### Переменные окружения

```env
# .env
DATABASE_URL=postgresql://payment_user:payment_pass@localhost:5432/payment_db
BANK_API_BASE_URL=http://localhost:8001
BANK_API_TIMEOUT=30
BANK_API_MAX_RETRIES=3
SYNC_BANK_PAYMENTS_INTERVAL=300
```

## Тестирование

### Запуск тестов

```bash
# Все тесты
pytest

# С coverage отчетом
pytest --cov=backend tests/

# Конкретный файл
pytest tests/test_payment_service.py -v

# Конкретный тест
pytest tests/test_payment_service.py::TestPaymentProcessor::test_create_cash_payment_success -v
```

### Структура тестов

- **test_payment_service.py** - тесты бизнес-логики
  - TestPaymentProcessor - тесты создания и возврата платежей
  - TestBankSyncService - тесты синхронизации с банком

- **test_api.py** - тесты API endpoints
  - TestOrdersAPI - тесты работы с заказами
  - TestPaymentsAPI - тесты работы с платежами
  - TestValidation - тесты валидации

### Мок-сервер банка

Для тестирования используется мок-сервер банка (`mock_bank/server.py`), который эмулирует:

- Создание платежа (`POST /acquiring_start`)
- Проверку статуса (`POST /acquiring_check`)
- Случайные изменения статусов (30% вероятность завершения)

## Тестирование вебхуков
### Автоматические тесты:

```bash
pytest tests/test_webhooks.py -v
```

### Ручное тестирование с мок-банком:

Мок-банк поддерживает отправку вебхуков:

* При создании платежа (70% шанс)
* Через тестовый endpoint

```bash
# Создать платеж (будет отправлен webhook через 5 сек)
curl -X POST http://localhost:8000/api/v1/payments \
  -H "X-API-Key: test-api-key" \
  -d '{"order_id": 1, "amount": "500.00", "type": "acquiring"}'

# Принудительно отправить webhook для существующего платежа
curl -X POST http://localhost:8001/webhook_test \
  -d '{"payment_id": "bank_123"}'
```

## Docker

### Запуск через Docker Compose

```bash
# Сборка и запуск всех сервисов
docker-compose up --build

# Запуск в фоне
docker-compose up -d

# Остановка
docker-compose down

# Просмотр логов
docker-compose logs -f app
```

### Docker Compose сервисы

1. **postgres** - база данных PostgreSQL
2. **app** - основное приложение
3. **mock-bank** - мок-сервер банка

### Полезные команды Docker

```bash
# Вход в контейнер приложения
docker-compose exec app bash

# Просмотр логов БД
docker-compose logs -f postgres

# Пересборка конкретного сервиса
docker-compose up -d --no-deps --build app

# Очистка всех контейнеров и томов
docker-compose down -v
```

## Мониторинг и логирование

### Webhook мониторинг

```bash
# Проверить, что вебхуки принимаются
curl -X POST http://localhost:8000/api/v1/webhooks/bank \
  -H "Content-Type: application/json" \
  -d '{"test": "connection"}'
# Ответ: {"received": true, "processed": false, "message": "Error: ...
```

### Health Check
```bash
curl http://localhost:8000/health
# Ответ: {"status": "healthy"}
```

### Логирование
- Все запросы логируются с временем выполнения
- Ошибки сохраняются в БД с детальным описанием
- Логи синхронизации с банком

## Примеры использования

### Полный цикл оплаты заказа

```python
import httpx
import asyncio

async def payment_flow():
    client = httpx.AsyncClient()
    headers = {"X-API-Key": "test-api-key"}
    
    # 1. Получить список неоплаченных заказов
    response = await client.get(
        "http://localhost:8000/api/v1/orders/unpaid/list",
        headers=headers
    )
    orders = response.json()
    order_id = orders[0]["id"]
    
    # 2. Создать платеж
    payment = await client.post(
        "http://localhost:8000/api/v1/payments",
        headers=headers,
        json={
            "order_id": order_id,
            "amount": "500.00",
            "type": "acquiring"
        }
    )
    payment_data = payment.json()
    
    # 3. Проверить статус через некоторое время
    await asyncio.sleep(5)
    
    # 4. Синхронизировать с банком
    sync = await client.post(
        "http://localhost:8000/api/v1/payments/sync",
        headers=headers
    )
    
    # 5. Получить обновленный статус
    payments = await client.get(
        f"http://localhost:8000/api/v1/payments/order/{order_id}",
        headers=headers
    )
    
    await client.aclose()

asyncio.run(payment_flow())
```

## Возможные улучшения

1. **Кэширование** - добавить Redis для кэширования часто запрашиваемых заказов
2. **Очереди** - использовать Celery для фоновой синхронизации с банком
3. **Метрики** - добавить Prometheus метрики для мониторинга
4. **Rate limiting** - защита API от чрезмерных запросов
5. **Webhooks** - уведомления о смене статуса платежей
6. **Audit log** - логирование всех изменений для compliance

## Лицензия

Разработано Мацко Сергеем в рамках тестового задания
