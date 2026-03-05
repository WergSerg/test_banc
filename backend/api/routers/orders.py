from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.dependencies.auth import verify_api_key
from backend.core.database import get_db
from backend.domain.models import Order
from backend.domain.schemas import OrderCreate, OrderResponse
from backend.exceptions import OrderNotFoundError
from backend.repositories.order_repository import OrderRepository

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderResponse,
             status_code=status.HTTP_201_CREATED)
async def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
) -> Order:
    order_repo = OrderRepository(db)
    order = order_repo.create_order(order_data)
    db.commit()
    return order


@router.get("", response_model=List[OrderResponse])
async def get_orders(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
) -> List[Order]:
    order_repo = OrderRepository(db)
    return order_repo.get_all(skip, limit)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
) -> Order:
    order_repo = OrderRepository(db)
    order = order_repo.get(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@router.get("/unpaid/list", response_model=List[OrderResponse])
async def get_unpaid_orders(
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
) -> List[Order]:
    order_repo = OrderRepository(db)
    return order_repo.get_unpaid_orders()
