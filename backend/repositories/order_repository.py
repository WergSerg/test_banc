from typing import List, Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from backend.domain.enums import OrderStatus
from backend.domain.models import Order
from backend.domain.schemas import OrderCreate
from backend.repositories.base import BaseRepository


class OrderRepository(BaseRepository[Order]):
    def __init__(self, db: Session):
        super().__init__(db, Order)

    def create_order(self, order_data: OrderCreate) -> Order:
        order = Order(
            amount=order_data.amount,
            paid_amount=0,
            status=OrderStatus.UNPAID.value
        )
        self.db.add(order)
        self.db.flush()
        return order

    def get_by_status(self, status: OrderStatus) -> List[Order]:
        stmt = select(Order).where(Order.status == status.value)
        return self.db.execute(stmt).scalars().all()

    def get_unpaid_orders(self) -> List[Order]:
        stmt = select(Order).where(
            and_(
                Order.status.in_([OrderStatus.UNPAID.value, OrderStatus.PARTIALLY_PAID.value]),
                Order.paid_amount < Order.amount
            )
        )
        return self.db.execute(stmt).scalars().all()

    def update_paid_amount(self, order_id: int, amount_delta: float) -> Optional[Order]:
        order = self.get(order_id)
        if order:
            order.paid_amount += amount_delta
            self.db.flush()
        return order
