import hashlib
import hmac
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

import httpx
from tenacity import (retry, retry_if_exception_type, stop_after_attempt,
                      wait_exponential)

from backend.core.config import settings
from backend.domain.enums import BankPaymentStatus
from backend.domain.schemas import (BankPaymentCheckResponse,
                                    BankPaymentCreateResponse,
                                    BankWebhookPayload)
from backend.exceptions import BankAPIError, BankPaymentNotFoundError

logger = logging.getLogger(__name__)


class BankAPIClient:
    def __init__(self, base_url: str = settings.BANK_API_BASE_URL, timeout: int = settings.BANK_API_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    @retry(
        stop=stop_after_attempt(settings.BANK_API_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError))
    )
    async def create_payment(self, order_id: int, amount: Decimal) -> BankPaymentCreateResponse:
        """
        Создание платежа в банке
        Банк может ответить сразу (синхронно) или начать обработку (асинхронно)
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/acquiring_start",
                json={"order_id": order_id, "amount": str(amount)}
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("success") and data.get("error"):
                raise BankAPIError(f"Bank API error: {data['error']}")

            return BankPaymentCreateResponse(
                payment_id=data["payment_id"],
                success=data["success"],
                error=data.get("error"),
                status=data.get("status", "pending"),
                requires_webhook=data.get("requires_webhook", True)
            )

        except httpx.TimeoutException as e:
            logger.error(f"Timeout while calling bank API: {e}")
            raise BankAPIError("API timeout")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from bank API: {e}")
            raise BankAPIError(f"API HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Unexpected error calling bank API: {e}")
            raise BankAPIError(f"Unexpected API error: {str(e)}")

    @retry(
        stop=stop_after_attempt(settings.BANK_API_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError))
    )
    async def check_payment(self, bank_payment_id: str) -> BankPaymentCheckResponse:
        try:
            response = await self.client.post(
                f"{self.base_url}/acquiring_check",
                json={"bank_payment_id": bank_payment_id}
            )
            response.raise_for_status()
            data = response.json()

            if data.get("error"):
                if data["error"] == "платеж не найден":
                    raise BankPaymentNotFoundError(f"Payment {bank_payment_id} not found in bank system")
                raise BankAPIError(f"API error: {data['error']}")

            return BankPaymentCheckResponse(
                payment_id=data["payment_id"],
                amount=Decimal(data["amount"]),
                status=data["status"],
                paid_at=datetime.fromisoformat(data["paid_at"]) if data.get("paid_at") else None,
                error=data.get("error")
            )

        except httpx.TimeoutException as e:
            logger.error(f"Timeout while checking bank payment: {e}")
            raise BankAPIError("Bank API timeout")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from API: {e}")
            raise BankAPIError(f"API HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Unexpected error checking bank payment: {e}")
            raise BankAPIError(f"Unexpected API error: {str(e)}")

    @staticmethod
    async def verify_webhook_signature(payload: dict, signature: str, secret: str) -> bool:
        message = f"{payload['payment_id']}{payload['status']}{payload.get('paid_at', '')}"
        expected_signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_signature, signature)

    async def close(self):
        await self.client.aclose()
