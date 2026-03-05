import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from backend.clients.bank_api_client import BankAPIClient
from backend.core.config import settings
from backend.core.database import get_db
from backend.domain.schemas import BankWebhookPayload, BankWebhookResponse
from backend.services.webhook_service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/bank", response_model=BankWebhookResponse)
async def bank_webhook(
        request: Request,
        x_signature: Optional[str] = Header(None),
        x_timestamp: Optional[str] = Header(None),
        db: Session = Depends(get_db)
):

    try:
        payload = await request.json()
        logger.info(f"Received bank webhook: {payload}")

        webhook_service = WebhookService(db)
        result = await webhook_service.process_bank_webhook(payload, x_signature)

        return BankWebhookResponse(
            received=True,
            processed=result,
            message="Webhook successfully"
        )

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return BankWebhookResponse(
            received=True,
            processed=False,
            message=f"Error: {str(e)}"
        )
