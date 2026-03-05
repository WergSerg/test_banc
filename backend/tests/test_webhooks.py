
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.domain.enums import OrderStatus, PaymentStatus, PaymentType
from backend.domain.models import Base, Order, Payment
from backend.services.polling_service import PollingService
from backend.services.webhook_service import WebhookService


SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_order(db_session: Session):
    order = Order(
        amount=Decimal("1000.00"),
        paid_amount=Decimal("0.00"),
        status=OrderStatus.UNPAID.value
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture
def bank_client_mock():
    return Mock()


@pytest.mark.asyncio
async def test_webhook_payment_completed(db_session, sample_order):
    payment = Payment(
        order_id=sample_order.id,
        amount=Decimal("500.00"),
        type=PaymentType.ACQUIRING.value,
        status=PaymentStatus.PROCESSING.value,
        bank_payment_id="bank_123"
    )
    db_session.add(payment)
    db_session.commit()

    webhook_payload = {
        "payment_id": "bank_123",
        "order_id": sample_order.id,
        "amount": "500.00",
        "status": "completed",
        "paid_at": datetime.now().isoformat(),
        "timestamp": datetime.now().isoformat()
    }

    webhook_service = WebhookService(db_session)
    result = await webhook_service.process_bank_webhook(webhook_payload)

    assert result is True

    db_session.refresh(payment)
    assert payment.status == PaymentStatus.COMPLETED.value

    db_session.refresh(sample_order)
    assert sample_order.paid_amount == Decimal("500.00")
    assert sample_order.status == OrderStatus.PARTIALLY_PAID.value


@pytest.mark.asyncio
async def test_webhook_payment_failed(db_session, sample_order):
    payment = Payment(
        order_id=sample_order.id,
        amount=Decimal("500.00"),
        type=PaymentType.ACQUIRING.value,
        status=PaymentStatus.PROCESSING.value,
        bank_payment_id="bank_123"
    )
    db_session.add(payment)
    db_session.commit()

    webhook_payload = {
        "payment_id": "bank_123",
        "order_id": sample_order.id,
        "amount": "500.00",
        "status": "failed",
        "error": "Insufficient funds",
        "timestamp": datetime.now().isoformat()
    }

    webhook_service = WebhookService(db_session)
    result = await webhook_service.process_bank_webhook(webhook_payload)

    assert result is True

    db_session.refresh(payment)
    assert payment.status == PaymentStatus.FAILED.value
    assert payment.error_message == "Insufficient funds"

    db_session.refresh(sample_order)
    assert sample_order.paid_amount == Decimal("0.00")


@pytest.mark.asyncio
async def test_polling_service(db_session, sample_order, bank_client_mock):
    payment = Payment(
        order_id=sample_order.id,
        amount=Decimal("500.00"),
        type=PaymentType.ACQUIRING.value,
        status=PaymentStatus.PROCESSING.value,
        bank_payment_id="bank_123",
        updated_at=datetime(2020, 1, 1)
    )
    db_session.add(payment)
    db_session.commit()

    bank_client_mock.check_payment = AsyncMock(return_value=Mock(
        payment_id="bank_123",
        amount=Decimal("500.00"),
        status="completed",
        paid_at=datetime.now(),
        error=None
    ))

    polling_service = PollingService(db_session, bank_client_mock)
    updated = await polling_service.poll_payments(max_age_minutes=1)

    assert len(updated) == 1
    assert updated[0].status == PaymentStatus.COMPLETED.value

    db_session.refresh(sample_order)
    assert sample_order.paid_amount == Decimal("500.00")


@pytest.mark.asyncio
async def test_poll_specific_payment(db_session, sample_order, bank_client_mock):
    payment = Payment(
        order_id=sample_order.id,
        amount=Decimal("500.00"),
        type=PaymentType.ACQUIRING.value,
        status=PaymentStatus.PROCESSING.value,
        bank_payment_id="bank_123"
    )
    db_session.add(payment)
    db_session.commit()

    bank_client_mock.check_payment = AsyncMock(return_value=Mock(
        payment_id="bank_123",
        amount=Decimal("500.00"),
        status="completed",
        paid_at=datetime.now(),
        error=None
    ))

    polling_service = PollingService(db_session, bank_client_mock)
    updated = await polling_service.poll_specific_payment(payment.id)

    assert updated is not None
    assert updated.status == PaymentStatus.COMPLETED.value
