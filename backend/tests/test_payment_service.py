from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.clients.bank_api_client import BankAPIClient
from backend.domain.enums import OrderStatus, PaymentStatus, PaymentType
from backend.domain.models import Base, Order, Payment
from backend.domain.schemas import PaymentCreate, PaymentRefund
from backend.exceptions import (BankAPIError, OrderAlreadyPaidError,
                                OrderNotFoundError, PaymentAmountExceededError,
                                PaymentNotFoundError, PaymentServiceError)
from backend.services.bank_sync_service import BankSyncService
from backend.services.payment_service import PaymentProcessor


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
    client = Mock(spec=BankAPIClient)
    client.create_payment = AsyncMock()
    client.check_payment = AsyncMock()
    client.close = AsyncMock()
    return client


class TestPaymentProcessor:
    @pytest.mark.asyncio
    async def test_create_cash_payment_success(self, db_session: Session, sample_order: Order):
        bank_client = Mock(spec=BankAPIClient)
        processor = PaymentProcessor(db_session, bank_client)

        payment_data = PaymentCreate(
            order_id=sample_order.id,
            amount=Decimal("500.00"),
            type=PaymentType.CASH
        )

        payment = await processor.create_payment(payment_data)

        assert payment.id is not None
        assert payment.amount == Decimal("500.00")
        assert payment.type == PaymentType.CASH.value
        assert payment.status == PaymentStatus.COMPLETED.value

        db_session.refresh(sample_order)
        assert sample_order.paid_amount == Decimal("500.00")
        assert sample_order.status == OrderStatus.PARTIALLY_PAID.value

    @pytest.mark.asyncio
    async def test_create_acquiring_payment_success(self, db_session: Session, sample_order: Order, bank_client_mock):
        bank_client_mock.create_payment.return_value = Mock(
            payment_id="bank_123",
            success=True,
            error=None,
            status="pending",
            requires_webhook=True
        )

        processor = PaymentProcessor(db_session, bank_client_mock)

        payment_data = PaymentCreate(
            order_id=sample_order.id,
            amount=Decimal("500.00"),
            type=PaymentType.ACQUIRING
        )

        payment = await processor.create_payment(payment_data)

        assert payment.id is not None
        assert payment.amount == Decimal("500.00")
        assert payment.type == PaymentType.ACQUIRING.value
        assert payment.status == PaymentStatus.PROCESSING.value
        assert payment.bank_payment_id == "bank_123"

        bank_client_mock.create_payment.assert_called_once_with(
            order_id=sample_order.id,
            amount=Decimal("500.00")
        )

    @pytest.mark.asyncio
    async def test_create_payment_order_not_found(self, db_session: Session, bank_client_mock):
        processor = PaymentProcessor(db_session, bank_client_mock)

        payment_data = PaymentCreate(
            order_id=999,
            amount=Decimal("500.00"),
            type=PaymentType.CASH
        )

        with pytest.raises(OrderNotFoundError):
            await processor.create_payment(payment_data)

    @pytest.mark.asyncio
    async def test_create_payment_order_already_paid(self, db_session: Session, sample_order: Order, bank_client_mock):
        sample_order.status = OrderStatus.PAID.value
        sample_order.paid_amount = sample_order.amount
        db_session.commit()

        processor = PaymentProcessor(db_session, bank_client_mock)

        payment_data = PaymentCreate(
            order_id=sample_order.id,
            amount=Decimal("500.00"),
            type=PaymentType.CASH
        )

        with pytest.raises(OrderAlreadyPaidError):
            await processor.create_payment(payment_data)

    @pytest.mark.asyncio
    async def test_create_payment_amount_exceeds_remaining(self, db_session: Session, sample_order: Order,
                                                           bank_client_mock):
        processor = PaymentProcessor(db_session, bank_client_mock)

        payment_data = PaymentCreate(
            order_id=sample_order.id,
            amount=Decimal("1500.00"),
            type=PaymentType.CASH
        )

        with pytest.raises(PaymentAmountExceededError):
            await processor.create_payment(payment_data)

    @pytest.mark.asyncio
    async def test_create_acquiring_payment_bank_error(self, db_session: Session, sample_order: Order,
                                                       bank_client_mock):
        bank_client_mock.create_payment.side_effect = BankAPIError("Bank unavailable")

        processor = PaymentProcessor(db_session, bank_client_mock)

        payment_data = PaymentCreate(
            order_id=sample_order.id,
            amount=Decimal("500.00"),
            type=PaymentType.ACQUIRING
        )

        with pytest.raises(PaymentServiceError, match="Failed to process acquiring payment"):
            await processor.create_payment(payment_data)

        payment = db_session.query(Payment).first()
        assert payment.status == PaymentStatus.FAILED.value
        assert payment.error_message is not None

    @pytest.mark.asyncio
    async def test_refund_payment_success(self, db_session: Session, sample_order: Order):
        payment = Payment(
            order_id=sample_order.id,
            amount=Decimal("500.00"),
            type=PaymentType.CASH.value,
            status=PaymentStatus.COMPLETED.value
        )
        db_session.add(payment)
        sample_order.paid_amount = Decimal("500.00")
        sample_order.status = OrderStatus.PARTIALLY_PAID.value
        db_session.commit()

        bank_client = Mock(spec=BankAPIClient)
        processor = PaymentProcessor(db_session, bank_client)

        refund_data = PaymentRefund(payment_id=payment.id)
        refunded = await processor.refund_payment(refund_data)

        assert refunded.status == PaymentStatus.REFUNDED.value

        db_session.refresh(sample_order)
        assert sample_order.paid_amount == Decimal("0.00")
        assert sample_order.status == OrderStatus.UNPAID.value

    @pytest.mark.asyncio
    async def test_refund_payment_not_found(self, db_session: Session, bank_client_mock):
        processor = PaymentProcessor(db_session, bank_client_mock)

        refund_data = PaymentRefund(payment_id=999)

        with pytest.raises(PaymentNotFoundError):
            await processor.refund_payment(refund_data)

    @pytest.mark.asyncio
    async def test_refund_payment_not_completed(self, db_session: Session, sample_order: Order, bank_client_mock):
        payment = Payment(
            order_id=sample_order.id,
            amount=Decimal("500.00"),
            type=PaymentType.CASH.value,
            status=PaymentStatus.PENDING.value
        )
        db_session.add(payment)
        db_session.commit()

        processor = PaymentProcessor(db_session, bank_client_mock)

        refund_data = PaymentRefund(payment_id=payment.id)

        with pytest.raises(PaymentServiceError):
            await processor.refund_payment(refund_data)


class TestBankSyncService:
    @pytest.mark.asyncio
    async def test_sync_payments_updates_completed(self, db_session: Session, sample_order: Order, bank_client_mock):
        payment = Payment(
            order_id=sample_order.id,
            amount=Decimal("500.00"),
            type=PaymentType.ACQUIRING.value,
            status=PaymentStatus.PROCESSING.value,
            bank_payment_id="bank_123",
            bank_status="pending"
        )
        db_session.add(payment)
        db_session.commit()

        bank_client_mock.check_payment.return_value = Mock(
            payment_id="bank_123",
            amount=Decimal("500.00"),
            status="completed",
            paid_at=datetime.now(),
            error=None
        )

        sync_service = BankSyncService(db_session, bank_client_mock)
        synced = await sync_service.sync_payments()

        assert len(synced) == 1
        assert synced[0].status == PaymentStatus.COMPLETED.value
        assert synced[0].bank_status == "completed"

        db_session.refresh(sample_order)
        assert sample_order.paid_amount == Decimal("500.00")
        assert sample_order.status == OrderStatus.PARTIALLY_PAID.value

    @pytest.mark.asyncio
    async def test_sync_payments_updates_failed(self, db_session: Session, sample_order: Order, bank_client_mock):
        payment = Payment(
            order_id=sample_order.id,
            amount=Decimal("500.00"),
            type=PaymentType.ACQUIRING.value,
            status=PaymentStatus.PROCESSING.value,
            bank_payment_id="bank_123",
            bank_status="pending"
        )
        db_session.add(payment)
        db_session.commit()

        bank_client_mock.check_payment.return_value = Mock(
            payment_id="bank_123",
            amount=Decimal("500.00"),
            status="failed",
            paid_at=None,
            error=None
        )

        sync_service = BankSyncService(db_session, bank_client_mock)
        synced = await sync_service.sync_payments()

        assert len(synced) == 1
        assert synced[0].status == PaymentStatus.FAILED.value
        assert synced[0].bank_status == "failed"

        db_session.refresh(sample_order)
        assert sample_order.paid_amount == Decimal("0.00")
