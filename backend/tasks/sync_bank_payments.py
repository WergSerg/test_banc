import asyncio
import logging

from sqlalchemy.orm import Session

from backend.clients.bank_api_client import BankAPIClient
from backend.core.database import SessionLocal
from backend.services.bank_sync_service import BankSyncService

logger = logging.getLogger(__name__)


async def sync_bank_payments_task():
    logger.info("Starting bank payments sync task")

    db = SessionLocal()
    bank_client = BankAPIClient()

    try:
        sync_service = BankSyncService(db, bank_client)
        synced_payments = await sync_service.sync_payments()
        logger.info(f"Synced {len(synced_payments)} bank payments")
    except Exception as e:
        logger.error(f"Error in sync task: {e}")
    finally:
        db.close()
        await bank_client.close()


def run_sync_task():
    asyncio.run(sync_bank_payments_task())


if __name__ == "__main__":
    run_sync_task()
