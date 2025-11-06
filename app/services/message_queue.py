"""Async message queue service for processing Telegram messages."""


import asyncio
from typing import Callable, List, Any

from app.logging_config import logger
from app.models import Message

class MessageQueueService:
    """
    Async message processing queue.
    
    Features:
    - Async message enqueueing
    - Concurrent processing
    - Error handling and retries
    - Queue size tracking
    - Batch processing support
    """
    def __init__(
        self,
        max_queue_size: int = 1000,
        max_concurrent_workers: int = 5,
        worker_timeout: int = 30,
    ):
        """
        Initialize message queue.
        
        Args:
            max_queue_size: Maximum queue size before blocking
            max_concurrent_workers: Max concurrent message processors
            worker_timeout: Timeout per message in seconds
        """
        self.max_queue_size = max_queue_size
        self.max_concurrent_workers = max_concurrent_workers
        self.worker_timeout = worker_timeout

        # Queue for pending messages
        self.queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=max_queue_size)

        # Tracking
        self.processed_count = 0
        self.error_count = 0
        self.is_running = False

        # Processing callbacks
        self.callbacks: List[Callable[[Message], Any]] = []

    async def enqueue_message(self, message: Message) -> None:
        """
        Add message to processing queue.
        
        Args:
            message: Message to process
            
        Raises:
            asyncio.QueueFull: If queue is full (non-blocking mode)
        """
        try:
            # Non-blocking put to check if full
            self.queue.put_nowait(message)
            logger.debug(
                f"Message enqueued: id={message.id}, "
                f"queue_size={self.queue.qsize()}"
            )
        except asyncio.QueueFull:
            logger.error(
                f"Message queue full (max {self.max_queue_size}). "
                f"Dropping message: {message.id}"
            )
            raise

    async def enqueue_messages(self, messages: List[Message]) -> None:
        """
        Add multiple messages to queue.
        
        Args:
            messages: List of messages to enqueue
        """
        for message in messages:
            await self.enqueue_message(message)
        logger.info(f"Enqueued {len(messages)} messages")

    def register_callback(
        self, callback: Callable[[Message], Any]
    ) -> None:
        """
        Register a callback for message processing.
        
        Args:
            callback: Async function (message: Message) -> Any
        """
        self.callbacks.append(callback)
        logger.debug(f"Registered callback: {callback.__name__}")

    async def _process_single_message(self, message: Message) -> bool:
        """
        Process a single message with all callbacks.
        
        Args:
            message: Message to process
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.debug(f"Processing message: id={message.id}")

            # Execute all callbacks
            for callback in self.callbacks:
                try:
                    result = callback(message)
                    # Handle async callbacks
                    if asyncio.iscoroutine(result):
                        await asyncio.wait_for(result, timeout=self.worker_timeout)
                except asyncio.TimeoutError:
                    logger.error(
                        f"Callback timeout for message {message.id}: "
                        f"{callback.__name__}"
                    )
                    self.error_count += 1
                    return False
                except Exception as e:
                    logger.error(
                        f"Callback error for message {message.id}: {e}"
                    )
                    self.error_count += 1
                    return False

            self.processed_count += 1
            logger.debug(f"Message processed successfully: id={message.id}")
            return True

        except Exception as e:
            logger.error(f"Message processing failed: id={message.id}, error={e}")
            self.error_count += 1
            return False

    async def _worker(self, worker_id: int) -> None:
        """
        Worker coroutine for processing messages.
        
        Args:
            worker_id: Worker identifier
        """
        logger.info(f"Worker {worker_id} started")

        while self.is_running:
            try:
                # Get message with timeout
                try:
                    message = await asyncio.wait_for(
                        self.queue.get(), timeout=5
                    )
                except asyncio.TimeoutError:
                    # No message available, continue
                    continue

                # Process message
                await self._process_single_message(message)
                
                # Mark task done
                self.queue.task_done()

            except asyncio.CancelledError:
                logger.info(f"Worker {worker_id} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                continue

        logger.info(f"Worker {worker_id} stopped")

    async def start_workers(self) -> None:
        """
        Start worker tasks for processing queue.
        
        Creates max_concurrent_workers tasks.
        """
        if self.is_running:
            logger.warning("Workers already running")
            return

        self.is_running = True
        self.worker_tasks: List[asyncio.Task] = []

        for i in range(self.max_concurrent_workers):
            task = asyncio.create_task(self._worker(i))
            self.worker_tasks.append(task)

        logger.info(
            f"Started {self.max_concurrent_workers} message processing workers"
        )

    async def stop_workers(self) -> None:
        """
        Stop all worker tasks gracefully.
        
        Waits for queue to empty before stopping.
        """
        if not self.is_running:
            logger.warning("Workers not running")
            return

        logger.info("Stopping workers...")

        # Wait for queue to empty
        try:
            await asyncio.wait_for(self.queue.join(), timeout=60)
            logger.info("Queue empty, stopping workers")
        except asyncio.TimeoutError:
            logger.warning("Queue did not empty within timeout")

        # Stop workers
        self.is_running = False
        
        # Cancel and wait for workers
        for task in self.worker_tasks:
            task.cancel()

        # Wait for all workers to finish
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)

        logger.info("Workers stopped")

    async def process_queue(self) -> None:
        """
        Process all messages in queue.
        
        Blocks until queue is empty.
        """
        if not self.is_running:
            await self.start_workers()

        try:
            await self.queue.join()
            logger.info("All queued messages processed")
        except asyncio.CancelledError:
            logger.info("Queue processing cancelled")

    def get_queue_size(self) -> int:
        """Get current queue size."""
        return self.queue.qsize()

    def get_max_queue_size(self) -> int:
        """Get maximum queue size."""
        return self.max_queue_size

    def is_queue_full(self) -> bool:
        """Check if queue is at capacity."""
        return self.get_queue_size() >= self.max_queue_size

    async def batch_process(self, messages: List[Message]) -> int:
        """
        Process messages in batch.
        
        Args:
            messages: List of messages to process
            
        Returns:
            Number of messages successfully processed
        """
        logger.info(f"Batch processing {len(messages)} messages")

        # Enqueue all
        await self.enqueue_messages(messages)

        # Process until done
        await self.process_queue()

        return self.processed_count

    def get_stats(self) -> dict:
        """
        Get queue statistics.
        
        Returns:
            Dictionary with stats
        """
        return {
            "queue_size": self.get_queue_size(),
            "max_queue_size": self.max_queue_size,
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "is_running": self.is_running,
            "success_rate": (
                (self.processed_count / (self.processed_count + self.error_count))
                if (self.processed_count + self.error_count) > 0
                else 0.0
            ),
            "total_processed": self.processed_count + self.error_count,
        }

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self.processed_count = 0
        self.error_count = 0
        logger.info("Queue statistics reset")


__all__ = ["MessageQueueService"]
