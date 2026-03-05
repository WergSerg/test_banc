import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.clients.bank_api_client import BankAPIClient
from backend.domain.enums import OrderStatus, PaymentStatus
from backend.domain.models import Payment
from backend.exceptions import PaymentNotFoundError
from backend.repositories.order_repository import OrderRepository
from backend.repositories.payment_repository import PaymentRepository

logger = logging.getLogger(__name__)


class WebhookService:

    def __init__(self, db: Session):
        self.db = db
        self.payment_repo = PaymentRepository(db)
        self.order_repo = OrderRepository(db)

    async def process_bank_webhook(self, payload: dict, signature: Optional[str] = None) -> bool:
        try:
            bank_payment_id = payload.get("payment_id")
            new_status = payload.get("status")
            paid_at = payload.get("paid_at")

            if not bank_payment_id or not new_status:
                logger.error("Invalid webhook payload: missing required fields")
                return False

            payment = self.payment_repo.get_by_bank_payment_id(bank_payment_id)
            if not payment:
                logger.error(f"Payment with bank_id {bank_payment_id} not found")
                return False

            if signature:
                is_valid = await self._verify_signature(payload, signature)
                if not is_valid:
                    logger.error(f"Invalid webhook signature for payment {bank_payment_id}")
                    return False

            old_status = payment.status
            payment.bank_status = new_status

            if paid_at:
                try:
                    payment.bank_paid_at = datetime.fromisoformat(paid_at)
                except ValueError:
                    payment.bank_paid_at = datetime.utcnow()

            if new_status == "completed" and old_status != PaymentStatus.COMPLETED.value:
                payment.status = PaymentStatus.COMPLETED.value
                order = self.order_repo.get(payment.order_id)
                order.paid_amount += payment.amount
                self._update_order_status(order)
                logger.info(f"Payment {payment.id} completed via webhook")

            elif new_status == "failed" and old_status != PaymentStatus.FAILED.value:
                payment.status = PaymentStatus.FAILED.value
                payment.error_message = payload.get("error", "Payment failed")
                logger.info(f"Payment {payment.id} failed via webhook")

            elif new_status == "refunded":
                payment.status = PaymentStatus.REFUNDED.value
                order = self.order_repo.get(payment.order_id)
                order.paid_amount -= payment.amount
                self._update_order_status(order)
                logger.info(f"Payment {payment.id} refunded via webhook")

            self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            self.db.rollback()
            return False

    async def _verify_signature(self, payload: dict, signature: str) -> bool:
        return True

    @staticmethod
    def _update_order_status( order) -> None:
        if order.paid_amount >= order.amount:
            order.status = OrderStatus.PAID.value
        elif order.paid_amount > 0:
            order.status = OrderStatus.PARTIALLY_PAID.value
        else:
            order.status = OrderStatus.UNPAID.value
