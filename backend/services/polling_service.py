import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.clients.bank_api_client import BankAPIClient
from backend.domain.enums import BankPaymentStatus, OrderStatus, PaymentStatus
from backend.domain.models import Payment
from backend.exceptions import BankAPIError, BankPaymentNotFoundError
from backend.repositories.order_repository import OrderRepository
from backend.repositories.payment_repository import PaymentRepository

logger = logging.getLogger(__name__)


class PollingService:
    def __init__(self, db: Session, bank_client: BankAPIClient):
        self.db = db
        self.payment_repo = PaymentRepository(db)
        self.order_repo = OrderRepository(db)
        self.bank_client = bank_client

    async def poll_payments(self, max_age_minutes: int = 60) -> List[Payment]:
        cutoff_time = datetime.utcnow() - timedelta(minutes=max_age_minutes)

        payments = self.db.query(Payment).filter(
            Payment.type == "acquiring",
            Payment.status.in_([PaymentStatus.PENDING.value, PaymentStatus.PROCESSING.value]),
            Payment.bank_payment_id.isnot(None),
            Payment.updated_at < cutoff_time
        ).all()

        logger.info(f"Found {len(payments)} payments to poll")

        updated_payments = []
        for payment in payments:
            try:
                updated = await self._poll_single_payment(payment)
                if updated:
                    updated_payments.append(updated)
            except Exception as e:
                logger.error(f"Error polling payment {payment.id}: {e}")

        self.db.commit()
        return updated_payments

    async def poll_specific_payment(self, payment_id: int) -> Optional[Payment]:
        payment = self.payment_repo.get(payment_id)
        if not payment or payment.type != "acquiring":
            return None

        return await self._poll_single_payment(payment)

    async def _poll_single_payment(self, payment: Payment) -> Optional[Payment]:
        try:
            bank_status = await self.bank_client.check_payment(payment.bank_payment_id)

            old_status = payment.status
            payment.bank_status = bank_status.status
            payment.updated_at = datetime.utcnow()

            if bank_status.paid_at:
                payment.bank_paid_at = bank_status.paid_at

            if bank_status.status == BankPaymentStatus.COMPLETED.value:
                if old_status != PaymentStatus.COMPLETED.value:
                    payment.status = PaymentStatus.COMPLETED.value
                    order = self.order_repo.get(payment.order_id)
                    order.paid_amount += payment.amount
                    self._update_order_status(order)
                    logger.info(f"Payment {payment.id} completed via polling")

            elif bank_status.status == BankPaymentStatus.FAILED.value:
                if old_status != PaymentStatus.FAILED.value:
                    payment.status = PaymentStatus.FAILED.value
                    payment.error_message = "Payment failed in bank system"
                    logger.info(f"Payment {payment.id} failed via polling")

            self.db.add(payment)
            return payment

        except BankPaymentNotFoundError:
            logger.warning(f"Payment {payment.id} not found in bank system")
            payment.status = PaymentStatus.FAILED.value
            payment.error_message = "Payment not found in bank system"
            self.db.add(payment)
            return payment

        except BankAPIError as e:
            logger.error(f"Bank API error for payment {payment.id}: {e}")
            payment.error_message = f"Bank API error: {str(e)}"
            self.db.add(payment)
            return payment

    def _update_order_status(self, order) -> None:
        if order.paid_amount >= order.amount:
            order.status = OrderStatus.PAID.value
        elif order.paid_amount > 0:
            order.status = OrderStatus.PARTIALLY_PAID.value
        else:
            order.status = OrderStatus.UNPAID.value
