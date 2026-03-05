#!/bin/bash

API_KEY="test-api-key"
BASE_URL="http://localhost:8002"

echo "=== Тестирование Payment Service ==="

echo "1. Получаем список заказов"
curl -s -H "X-API-Key: $API_KEY" $BASE_URL/api/v1/orders | jq .

echo "2. Создаем наличный платеж"
curl -s -X POST $BASE_URL/api/v1/payments \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"order_id": 1, "amount": "500.00", "type": "cash"}' | jq .

echo "3. Создаем банковский платеж"
curl -s -X POST $BASE_URL/api/v1/payments \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"order_id": 1, "amount": "300.00", "type": "acquiring"}' | jq .

echo "4. Ждем 7 секунд для вебхука..."
sleep 7

echo "5. Проверяем статус платежей"
curl -s -H "X-API-Key: $API_KEY" $BASE_URL/api/v1/payments/order/1 | jq .

echo "6. Проверяем статус заказа"
curl -s -H "X-API-Key: $API_KEY" $BASE_URL/api/v1/orders/1 | jq .

echo "=== Тестирование завершено ==="