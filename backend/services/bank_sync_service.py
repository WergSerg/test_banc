import logging
from typing import List

from sqlalchemy.orm import Session

from backend.clients.bank_api_client import BankAPIClient
from backend.domain.enums import BankPaymentStatus, PaymentStatus
from backend.domain.models import Payment
from backend.exceptions import BankAPIError, BankPaymentNotFoundError
from backend.repositories.order_repository import OrderRepository
from backend.repositories.payment_repository import PaymentRepository

logger = logging.getLogger(__name__)


class BankSyncService:
    def __init__(self, db: Session, bank_client: BankAPIClient):
        self.db = db
        self.payment_repo = PaymentRepository(db)
        self.order_repo = OrderRepository(db)
        self.bank_client = bank_client

    async def sync_payments(self) -> List[Payment]:
        payments = self.payment_repo.get_pending_bank_payments()
        synced_payments = []

        for payment in payments:
            try:
                synced_payment = await self._sync_single_payment(payment)
                if synced_payment:
                    synced_payments.append(synced_payment)
            except Exception as e:
                logger.error(f"Failed to sync payment {payment.id}: {e}")
                payment.error_message = f"Sync failed: {str(e)}"
                self.db.add(payment)

        self.db.commit()
        return synced_payments

    async def _sync_single_payment(self, payment: Payment) -> Payment:
        try:
            bank_status = await self.bank_client.check_payment(payment.bank_payment_id)

            old_status = payment.status
            payment.bank_status = bank_status.status

            if bank_status.paid_at:
                payment.bank_paid_at = bank_status.paid_at

            if bank_status.status == BankPaymentStatus.COMPLETED.value:
                payment.status = PaymentStatus.COMPLETED.value
            elif bank_status.status == BankPaymentStatus.FAILED.value:
                payment.status = PaymentStatus.FAILED.value
                payment.error_message = "Payment failed in bank system"

            if old_status != payment.status:
                order = self.order_repo.get(payment.order_id)

                if payment.status == PaymentStatus.COMPLETED.value:
                    order.paid_amount += payment.amount
                elif payment.status == PaymentStatus.FAILED.value and old_status == PaymentStatus.PROCESSING.value:
                    pass

                if order.paid_amount >= order.amount:
                    order.status = "paid"
                elif order.paid_amount > 0:
                    order.status = "partially_paid"

                self.db.add(order)

            self.db.add(payment)
            return payment

        except BankPaymentNotFoundError as e:
            logger.warning(f"Payment {payment.id} not found in bank system: {e}")
            payment.status = PaymentStatus.FAILED.value
            payment.error_message = "Payment not found in bank system"
            self.db.add(payment)
            return payment

        except BankAPIError as e:
            logger.error(f"Bank API error for payment {payment.id}: {e}")
            payment.error_message = f"Bank API error: {str(e)}"
            self.db.add(payment)
            return payment
