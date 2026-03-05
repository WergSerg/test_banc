from decimal import Decimal
from sqlalchemy.orm import Session
from backend.core.database import SessionLocal, engine
from backend.domain.enums import OrderStatus
from backend.domain.models import Base, Order


def init_database():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")


def seed_database():
    db = SessionLocal()

    try:
        orders = [
            Order(amount=Decimal("1500.00"), paid_amount=Decimal("0.00"), status=OrderStatus.UNPAID.value),
            Order(amount=Decimal("2500.00"), paid_amount=Decimal("1000.00"), status=OrderStatus.PARTIALLY_PAID.value),
            Order(amount=Decimal("3000.00"), paid_amount=Decimal("3000.00"), status=OrderStatus.PAID.value),
            Order(amount=Decimal("1200.00"), paid_amount=Decimal("0.00"), status=OrderStatus.UNPAID.value),
        ]

        db.add_all(orders)
        db.commit()
        print(f"Added {len(orders)} sample orders")

    finally:
        db.close()


if __name__ == "__main__":
    init_database()
    seed_database()
