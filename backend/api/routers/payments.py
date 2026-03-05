from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.dependencies.auth import verify_api_key
from backend.clients.bank_api_client import BankAPIClient
from backend.core.database import get_db
from backend.domain.models import Payment
from backend.domain.schemas import (PaymentCreate, PaymentRefund,
                                    PaymentResponse)
from backend.exceptions import (OrderAlreadyPaidError, OrderNotFoundError,
                                PaymentAmountExceededError,
                                PaymentNotFoundError, PaymentServiceError)
from backend.repositories.payment_repository import PaymentRepository
from backend.services.payment_service import PaymentProcessor
from backend.services.polling_service import PollingService

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
        payment_data: PaymentCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        api_key: str = Depends(verify_api_key)
) -> Payment:
    bank_client = BankAPIClient()
    payment_processor = PaymentProcessor(db, bank_client)

    try:
        payment = await payment_processor.create_payment(payment_data)

        if payment.type == "acquiring" and payment.status == "processing":
            background_tasks.add_task(
                poll_payment_after_creation,
                payment.id,
                db
            )

        return payment
    except OrderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except OrderAlreadyPaidError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PaymentAmountExceededError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PaymentServiceError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    finally:
        await bank_client.close()


@router.post("/refund", response_model=PaymentResponse)
async def refund_payment(
        refund_data: PaymentRefund,
        db: Session = Depends(get_db),
        api_key: str = Depends(verify_api_key)
) -> Payment:
    bank_client = BankAPIClient()
    payment_processor = PaymentProcessor(db, bank_client)

    try:
        payment = await payment_processor.refund_payment(refund_data)
        return payment
    except PaymentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PaymentServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    finally:
        await bank_client.close()


@router.get("/order/{order_id}", response_model=List[PaymentResponse])
async def get_order_payments(
        order_id: int,
        db: Session = Depends(get_db),
        api_key: str = Depends(verify_api_key)
) -> List[Payment]:
    payment_repo = PaymentRepository(db)
    return payment_repo.get_by_order(order_id)


@router.post("/{payment_id}/poll", response_model=PaymentResponse)
async def poll_payment(
        payment_id: int,
        db: Session = Depends(get_db),
        api_key: str = Depends(verify_api_key)
) -> Payment:
    bank_client = BankAPIClient()
    polling_service = PollingService(db, bank_client)

    try:
        payment = await polling_service.poll_specific_payment(payment_id)
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found or not acquirable")
        return payment
    finally:
        await bank_client.close()


@router.post("/poll/stale", response_model=List[PaymentResponse])
async def poll_stale_payments(
        db: Session = Depends(get_db),
        api_key: str = Depends(verify_api_key)
) -> List[Payment]:
    bank_client = BankAPIClient()
    polling_service = PollingService(db, bank_client)

    try:
        payments = await polling_service.poll_payments()
        return payments
    finally:
        await bank_client.close()


async def poll_payment_after_creation(payment_id: int, db: Session):

    bank_client = BankAPIClient()
    polling_service = PollingService(db, bank_client)

    try:
        await polling_service.poll_specific_payment(payment_id)
    finally:
        await bank_client.close()
