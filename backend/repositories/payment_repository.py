from typing import List, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from backend.domain.enums import PaymentStatus, PaymentType
from backend.domain.models import Payment
from backend.repositories.base import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    def __init__(self, db: Session):
        super().__init__(db, Payment)

    def get_by_order(self, order_id: int) -> List[Payment]:
        stmt = select(Payment).where(Payment.order_id == order_id)
        return self.db.execute(stmt).scalars().all()

    def get_by_bank_payment_id(self, bank_payment_id: str) -> Optional[Payment]:
        stmt = select(Payment).where(Payment.bank_payment_id == bank_payment_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_pending_bank_payments(self) -> List[Payment]:
        stmt = select(Payment).where(
            and_(
                Payment.type == PaymentType.ACQUIRING.value,
                Payment.status.in_([PaymentStatus.PENDING.value, PaymentStatus.PROCESSING.value]),
                Payment.bank_payment_id.isnot(None)
            )
        )
        return self.db.execute(stmt).scalars().all()

    def update_bank_status(self, payment_id: int, bank_status: str, bank_paid_at: Optional[str] = None) -> Optional[Payment]:
        update_data = {"bank_status": bank_status}
        if bank_paid_at:
            update_data["bank_paid_at"] = bank_paid_at
        return self.update(payment_id, **update_data)
