from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.database import get_db
from backend.domain.enums import OrderStatus, PaymentStatus, PaymentType
from backend.domain.models import Base, Order, Payment
from backend.main import app

# Создаем тестовую БД
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def auth_headers():
    return {"X-API-Key": "test-api-key"}


@pytest.fixture
def sample_order(client, auth_headers):
    response = client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={"amount": "1000.00"}
    )
    return response.json()


class TestOrdersAPI:
    def test_create_order(self, client, auth_headers):
        response = client.post(
            "/api/v1/orders",
            headers=auth_headers,
            json={"amount": "1500.00"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["amount"] == "1500.00"
        assert data["paid_amount"] == "0.00"
        assert data["status"] == "unpaid"

    def test_get_orders(self, client, auth_headers, sample_order):
        response = client.get("/api/v1/orders", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_get_order_by_id(self, client, auth_headers, sample_order):
        response = client.get(f"/api/v1/orders/{sample_order['id']}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_order["id"]
        assert data["amount"] == "1000.00"

    def test_get_order_not_found(self, client, auth_headers):
        response = client.get("/api/v1/orders/999", headers=auth_headers)
        assert response.status_code == 404

    def test_get_unpaid_orders(self, client, auth_headers, sample_order):
        response = client.get("/api/v1/orders/unpaid/list", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_unauthorized_access(self, client):
        response = client.get("/api/v1/orders")
        assert response.status_code == 403


class TestPaymentsAPI:
    def test_create_cash_payment(self, client, auth_headers, sample_order):
        payment_data = {
            "order_id": sample_order["id"],
            "amount": "500.00",
            "type": PaymentType.CASH.value
        }

        response = client.post("/api/v1/payments", json=payment_data, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["order_id"] == sample_order["id"]
        assert data["amount"] == "500.00"
        assert data["type"] == PaymentType.CASH.value
        assert data["status"] == PaymentStatus.COMPLETED.value

    @patch("backend.services.payment_service.BankAPIClient")
    def test_create_acquiring_payment(self, mock_bank_client, client, auth_headers, sample_order):
        mock_instance = mock_bank_client.return_value
        mock_instance.create_payment = AsyncMock(return_value=Mock(
            payment_id="bank_123",
            success=True,
            error=None,
            status="pending",
            requires_webhook=True
        ))
        mock_instance.close = AsyncMock()

        payment_data = {
            "order_id": sample_order["id"],
            "amount": "500.00",
            "type": PaymentType.ACQUIRING.value
        }

        response = client.post("/api/v1/payments", json=payment_data, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["order_id"] == sample_order["id"]
        assert data["amount"] == "500.00"
        assert data["type"] == PaymentType.ACQUIRING.value
        assert data["status"] == PaymentStatus.PROCESSING.value
        assert data["bank_payment_id"] == "bank_123"

    def test_create_payment_order_not_found(self, client, auth_headers):
        payment_data = {
            "order_id": 999,
            "amount": "500.00",
            "type": PaymentType.CASH.value
        }

        response = client.post("/api/v1/payments", json=payment_data, headers=auth_headers)
        assert response.status_code == 404

    def test_create_payment_exceeds_amount(self, client, auth_headers, sample_order):
        payment_data = {
            "order_id": sample_order["id"],
            "amount": "1500.00",
            "type": PaymentType.CASH.value
        }

        response = client.post("/api/v1/payments", json=payment_data, headers=auth_headers)
        assert response.status_code == 400

    def test_refund_payment(self, client, auth_headers, sample_order):
        # Сначала создаем платеж
        payment_data = {
            "order_id": sample_order["id"],
            "amount": "500.00",
            "type": PaymentType.CASH.value
        }
        payment_response = client.post("/api/v1/payments", json=payment_data, headers=auth_headers)
        payment = payment_response.json()

        # Возвращаем платеж
        refund_data = {"payment_id": payment["id"]}
        response = client.post("/api/v1/payments/refund", json=refund_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == payment["id"]
        assert data["status"] == PaymentStatus.REFUNDED.value

    def test_refund_payment_not_found(self, client, auth_headers):
        refund_data = {"payment_id": 999}
        response = client.post("/api/v1/payments/refund", json=refund_data, headers=auth_headers)
        assert response.status_code == 404

    def test_get_order_payments(self, client, auth_headers, sample_order):
        # Создаем два платежа
        payment1 = client.post("/api/v1/payments", headers=auth_headers, json={
            "order_id": sample_order["id"],
            "amount": "300.00",
            "type": PaymentType.CASH.value
        })
        payment2 = client.post("/api/v1/payments", headers=auth_headers, json={
            "order_id": sample_order["id"],
            "amount": "200.00",
            "type": PaymentType.CASH.value
        })

        response = client.get(f"/api/v1/payments/order/{sample_order['id']}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

    @patch("backend.services.bank_sync_service.BankSyncService")
    def test_sync_bank_payments(self, mock_sync_service, client, auth_headers):
        mock_instance = mock_sync_service.return_value
        mock_instance.sync_payments = AsyncMock(return_value=[])

        response = client.post("/api/v1/payments/sync", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_invalid_api_key(self, client, sample_order):
        payment_data = {
            "order_id": sample_order["id"],
            "amount": "500.00",
            "type": PaymentType.CASH.value
        }

        response = client.post("/api/v1/payments", json=payment_data, headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 403


class TestValidation:
    def test_create_payment_invalid_amount(self, client, auth_headers, sample_order):
        payment_data = {
            "order_id": sample_order["id"],
            "amount": "-100.00",
            "type": PaymentType.CASH.value
        }

        response = client.post("/api/v1/payments", json=payment_data, headers=auth_headers)
        assert response.status_code == 422

    def test_create_payment_invalid_type(self, client, auth_headers, sample_order):
        payment_data = {
            "order_id": sample_order["id"],
            "amount": "500.00",
            "type": "invalid_type"
        }

        response = client.post("/api/v1/payments", json=payment_data, headers=auth_headers)
        assert response.status_code == 422

    def test_create_payment_missing_field(self, client, auth_headers, sample_order):
        payment_data = {
            "order_id": sample_order["id"],
            "amount": "500.00"
        }

        response = client.post("/api/v1/payments", json=payment_data, headers=auth_headers)
        assert response.status_code == 422
