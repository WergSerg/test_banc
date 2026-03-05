import asyncio
import logging

from sqlalchemy.orm import Session

from backend.clients.bank_api_client import BankAPIClient
from backend.core.database import SessionLocal
from backend.services.polling_service import PollingService

logger = logging.getLogger(__name__)


async def run_polling_task():
    logger.info("Starting polling task for stale payments")

    db = SessionLocal()
    bank_client = BankAPIClient()

    try:
        polling_service = PollingService(db, bank_client)
        updated_payments = await polling_service.poll_payments(max_age_minutes=30)
        logger.info(f"Polling task completed. Updated {len(updated_payments)} payments")
    except Exception as e:
        logger.error(f"Error in polling task: {e}")
    finally:
        db.close()
        await bank_client.close()


async def polling_worker():
    while True:
        await run_polling_task()
        await asyncio.sleep(900)
