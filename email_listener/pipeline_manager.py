"""
Pipeline Manager – Async queue-based pipeline for invoice processing.

Stages:
  1. parse_queue  → parsing worker  → calls parse_func(file_path)
  2. notify_queue → notify worker   → calls notify_func(invoice_data)
  3. product_queue→ product worker  → calls add_func(invoice_data)  (after user approval)

Callbacks:
  pipeline.on_parsed  – called after successful parse
  pipeline.on_failed  – called after all retries exhausted
"""

import asyncio
import logging
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class FileStatus(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"
    PARSED = "parsed"
    NOTIFYING = "notifying"
    NOTIFIED = "notified"
    ADDING_PRODUCTS = "adding_products"
    DONE = "done"
    FAILED = "failed"


class AsyncPipeline:
    """
    Three-stage async pipeline: parse → notify → add_products.

    Usage:
        pipeline = AsyncPipeline(max_parsing_workers=1, max_product_workers=1)
        pipeline.on_parsed = my_on_parsed_cb
        pipeline.on_failed = my_on_failed_cb

        asyncio.create_task(pipeline.start_parsing_worker(parse_func, ...))
        asyncio.create_task(pipeline.start_notification_worker(notify_func))
        asyncio.create_task(pipeline.start_product_worker(add_func))

        # To queue a file for processing:
        await pipeline.enqueue_file("/path/to/invoice.pdf", metadata={...})
    """

    def __init__(self, max_parsing_workers: int = 1, max_product_workers: int = 1):
        self.max_parsing_workers = max_parsing_workers
        self.max_product_workers = max_product_workers

        # Internal queues
        self.parse_queue: asyncio.Queue = asyncio.Queue()
        self.notify_queue: asyncio.Queue = asyncio.Queue()
        self.product_queue: asyncio.Queue = asyncio.Queue()

        # Optional callbacks set by the caller
        self.on_parsed: Optional[Callable] = None
        self.on_failed: Optional[Callable] = None

    # ── Public API ────────────────────────────────────────────────────────────

    async def enqueue_file(self, file_path: str, metadata: Optional[dict] = None):
        """Add a file to the head of the pipeline (parse queue)."""
        await self.parse_queue.put({
            "file_path": file_path,
            "metadata": metadata or {},
            "retries": 0,
        })
        logger.debug(f"Enqueued for parsing: {file_path}")

    async def enqueue_approved_invoice(self, invoice_data: dict):
        """
        Skip parse/notify stages and send an already-approved invoice
        directly to the product worker.
        """
        await self.product_queue.put(invoice_data)
        logger.debug(f"Enqueued approved invoice: {invoice_data.get('invoice_number')}")

    # ── Workers ───────────────────────────────────────────────────────────────

    async def start_parsing_worker(
        self,
        parse_func: Callable,
        retry_backoff_seconds: int = 60,
        max_retries: int = 3,
    ):
        """
        Continuously pull items from parse_queue, call parse_func(file_path),
        and push results to notify_queue.  Retries on failure with exponential backoff.
        """
        logger.info("🔄 Parsing worker started")
        while True:
            item: dict = await self.parse_queue.get()
            file_path: str = item["file_path"]
            metadata: dict = item.get("metadata", {})
            retries: int = item.get("retries", 0)

            try:
                logger.info(f"Parsing [{retries + 1}]: {file_path}")
                result: Any = await parse_func(file_path)

                if result is None:
                    raise ValueError(f"parse_func returned None for {file_path}")

                # Attach pipeline metadata and forward to notify stage
                result["_file_path"] = file_path
                result["_metadata"] = metadata
                await self.notify_queue.put(result)

                if self.on_parsed:
                    try:
                        await self.on_parsed(file_path, result)
                    except Exception as cb_err:
                        logger.warning(f"on_parsed callback error: {cb_err}")

            except Exception as exc:
                if retries < max_retries:
                    backoff = retry_backoff_seconds * (retries + 1)
                    logger.warning(
                        f"⚠️  Parse failed (attempt {retries + 1}/{max_retries}), "
                        f"retrying in {backoff}s: {file_path} — {exc}"
                    )
                    async def _requeue_later() -> None:
                        await asyncio.sleep(backoff)
                        item["retries"] = retries + 1
                        await self.parse_queue.put(item)

                    asyncio.create_task(_requeue_later())
                else:
                    logger.error(f"❌ Parsing permanently failed after {max_retries} retries: {file_path}")
                    if self.on_failed:
                        try:
                            await self.on_failed(file_path, exc)
                        except Exception as cb_err:
                            logger.warning(f"on_failed callback error: {cb_err}")
            finally:
                self.parse_queue.task_done()

    async def start_notification_worker(self, notify_func: Callable):
        """
        Continuously pull parsed invoices from notify_queue, call notify_func(invoice_data),
        then forward to product_queue ONLY if invoice creation succeeds.
        """
        logger.info("🔔 Notification worker started")
        while True:
            invoice_data: dict = await self.notify_queue.get()
            try:
                success = await notify_func(invoice_data)
                # Only queue products if invoice was successfully created
                if success:
                    await self.product_queue.put(invoice_data)
                else:
                    logger.warning(f"⚠️  Skipping product queue for {invoice_data.get('invoice_number')} — invoice creation failed")
            except Exception as exc:
                logger.error(f"❌ Notification error for {invoice_data.get('invoice_number')}: {exc}")
            finally:
                self.notify_queue.task_done()

    async def start_product_worker(self, add_func: Callable):
        """
        Continuously pull approved invoices from product_queue and call add_func(invoice_data).
        Items reach this queue either from the notify stage or via enqueue_approved_invoice().
        """
        logger.info("📦 Product worker started")
        while True:
            invoice_data: dict = await self.product_queue.get()
            try:
                await add_func(invoice_data)
            except Exception as exc:
                logger.error(f"❌ Product add error for {invoice_data.get('invoice_number')}: {exc}")
            finally:
                self.product_queue.task_done()