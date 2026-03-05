import json
import random
import threading
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

import requests


class MockBankHandler(BaseHTTPRequestHandler):
    payments = {}
    webhook_url = "http://localhost:8002/api/v1/webhooks/bank"

    def do_POST(self):
        if self.path == '/acquiring_start':
            self.handle_create_payment()
        elif self.path == '/acquiring_check':
            self.handle_check_payment()
        elif self.path == '/webhook_test':
            self.handle_test_webhook()
        else:
            self.send_error(404)

    def handle_create_payment(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)

        payment_id = str(uuid.uuid4())

        # 70% шанс что платеж требует вебхука, 30% что ответит сразу
        requires_webhook = random.random() < 0.7
        initial_status = "pending" if requires_webhook else "completed"
        paid_at = datetime.now().isoformat() if initial_status == "completed" else None

        self.payments[payment_id] = {
            "order_id": data["order_id"],
            "amount": data["amount"],
            "status": initial_status,
            "created_at": datetime.now().isoformat(),
            "paid_at": paid_at,
            "requires_webhook": requires_webhook
        }

        response = {
            "payment_id": payment_id,
            "success": True,
            "error": None,
            "status": initial_status,
            "requires_webhook": requires_webhook
        }

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

        # Если платеж требует вебхука, запускаем фоновую задачу
        if requires_webhook:
            threading.Timer(5.0, self.send_webhook, args=[payment_id]).start()

    def handle_check_payment(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)

        payment_id = data["bank_payment_id"]

        if payment_id not in self.payments:
            response = {
                "error": "платеж не найден"
            }
            self.send_response(404)
        else:
            payment = self.payments[payment_id]

            # Если платеж все еще в обработке, иногда меняем статус
            if payment["status"] == "pending" and random.random() < 0.3:
                payment["status"] = "completed"
                payment["paid_at"] = datetime.now().isoformat()

            response = {
                "payment_id": payment_id,
                "amount": payment["amount"],
                "status": payment["status"],
                "paid_at": payment.get("paid_at"),
                "error": None
            }
            self.send_response(200)

        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

    def handle_test_webhook(self):
        """Endpoint для тестирования вебхуков"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)

        payment_id = data.get("payment_id")
        if payment_id and payment_id in self.payments:
            self.send_webhook(payment_id)

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "webhook sent"}).encode())

    def send_webhook(self, payment_id):
        """Отправка вебхука в наш сервис"""
        payment = self.payments.get(payment_id)
        if not payment:
            return

        # Меняем статус на случайный
        if payment["status"] == "pending":
            payment["status"] = random.choice(["completed", "failed"])
            if payment["status"] == "completed":
                payment["paid_at"] = datetime.now().isoformat()

        webhook_payload = {
            "payment_id": payment_id,
            "order_id": payment["order_id"],
            "amount": payment["amount"],
            "status": payment["status"],
            "paid_at": payment.get("paid_at"),
            "timestamp": datetime.now().isoformat()
        }

        # Генерируем подпись
        import hashlib
        import hmac
        message = f"{payment_id}{payment['status']}{payment.get('paid_at', '')}"
        signature = hmac.new(
            b"test_secret_key",
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        try:
            requests.post(
                self.webhook_url,
                json=webhook_payload,
                headers={
                    "X-Signature": signature,
                    "X-Timestamp": datetime.now().isoformat()
                },
                timeout=2
            )
            print(f"Webhook sent for payment {payment_id}")
        except Exception as e:
            print(f"Failed to send webhook: {e}")

    def log_message(self, format, *args):
        print(f"{datetime.now().isoformat()} - {format % args}")


if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8001), MockBankHandler)
    print('Mock bank server running on port 8001...')
    print('Webhook URL: http://localhost:8001/webhook_test')
    server.serve_forever()
