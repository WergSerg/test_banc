from sqlalchemy import (CheckConstraint, Column, DateTime, ForeignKey, Index,
                        Integer, Numeric, String, Text)
from sqlalchemy.sql import func

from backend.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    paid_amount = Column(Numeric(10, 2), nullable=False, default=0)
    status = Column(String(20), nullable=False, default="unpaid")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        CheckConstraint('amount > 0', name='check_amount_positive'),
        CheckConstraint('paid_amount >= 0', name='check_paid_amount_non_negative'),
        CheckConstraint('paid_amount <= amount', name='check_paid_amount_not_exceed_total'),
        CheckConstraint("status IN ('unpaid', 'partially_paid', 'paid')", name='check_order_status_valid'),
    )


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    bank_payment_id = Column(String(100), nullable=True, index=True)
    bank_status = Column(String(50), nullable=True)
    bank_paid_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        CheckConstraint('amount > 0', name='check_payment_amount_positive'),
        CheckConstraint("type IN ('cash', 'acquiring')", name='check_payment_type_valid'),
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed', 'refunded')",
                        name='check_payment_status_valid'),
    )
