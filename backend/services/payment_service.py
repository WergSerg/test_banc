import logging
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.clients.bank_api_client import BankAPIClient
from backend.domain.enums import OrderStatus, PaymentStatus, PaymentType
from backend.domain.models import Order, Payment
from backend.domain.schemas import PaymentCreate, PaymentRefund
from backend.exceptions import (BankAPIError, InvalidPaymentTypeError,
                                OrderAlreadyPaidError, OrderNotFoundError,
                                PaymentAmountExceededError,
                                PaymentNotFoundError, PaymentServiceError)
from backend.repositories.order_repository import OrderRepository
from backend.repositories.payment_repository import PaymentRepository

logger = logging.getLogger(__name__)


class PaymentProcessor:
    def __init__(self, db: Session, bank_client: BankAPIClient):
        self.db = db
        self.order_repo = OrderRepository(db)
        self.payment_repo = PaymentRepository(db)
        self.bank_client = bank_client

    async def create_payment(self, payment_data: PaymentCreate) -> Payment:
        order = self.order_repo.get(payment_data.order_id)
        if not order:
            raise OrderNotFoundError(f"Order {payment_data.order_id} not found")

        if order.status == OrderStatus.PAID.value:
            raise OrderAlreadyPaidError("Order is already paid")

        remaining = order.amount - order.paid_amount
        if payment_data.amount > remaining:
            raise PaymentAmountExceededError(
                f"Payment amount {payment_data.amount} exceeds remaining {remaining}"
            )

        payment = self.payment_repo.create(
            order_id=payment_data.order_id,
            amount=payment_data.amount,
            type=payment_data.type.value,
            status=PaymentStatus.PENDING.value
        )

        try:
            if payment_data.type == PaymentType.CASH:
                payment = self._process_cash_payment(payment)
            elif payment_data.type == PaymentType.ACQUIRING:
                payment = await self._process_acquiring_payment(payment)
            else:
                raise InvalidPaymentTypeError(f"Unsupported payment type: {payment_data.type}")

            self.db.commit()

            order = self.order_repo.get(order.id)
            self._update_order_status(order)
            self.db.commit()

            return payment

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create payment: {e}")
            raise PaymentServiceError(f"Payment creation failed: {str(e)}")

    async def refund_payment(self, refund_data: PaymentRefund) -> Payment:
        payment = self.payment_repo.get(refund_data.payment_id)
        if not payment:
            raise PaymentNotFoundError(f"Payment {refund_data.payment_id} not found")

        if payment.status not in [PaymentStatus.COMPLETED.value]:
            raise PaymentServiceError("Can only refund completed payments")

        payment.status = PaymentStatus.REFUNDED.value
        self.db.flush()

        order = self.order_repo.get(payment.order_id)
        order.paid_amount -= payment.amount
        self._update_order_status(order)

        self.db.commit()
        return payment

    def _process_cash_payment(self, payment: Payment) -> Payment:
        payment.status = PaymentStatus.COMPLETED.value

        order = self.order_repo.get(payment.order_id)
        order.paid_amount += payment.amount

        return payment

    async def _process_acquiring_payment(self, payment: Payment) -> Payment:
        try:
            bank_response = await self.bank_client.create_payment(
                order_id=payment.order_id,
                amount=payment.amount
            )

            payment.bank_payment_id = bank_response.payment_id
            payment.status = PaymentStatus.PROCESSING.value
            payment.bank_status = "pending"

            return payment

        except BankAPIError as e:
            payment.status = PaymentStatus.FAILED.value
            payment.error_message = str(e)
            logger.error(f"Bank API error for payment {payment.id}: {e}")
            raise PaymentServiceError(f"Failed to process acquiring payment: {e}")

    def _update_order_status(self, order: Order) -> None:
        if order.paid_amount >= order.amount:
            order.status = OrderStatus.PAID.value
        elif order.paid_amount > 0:
            order.status = OrderStatus.PARTIALLY_PAID.value
        else:
            order.status = OrderStatus.UNPAID.value
