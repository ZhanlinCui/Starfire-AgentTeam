"""Send heartbeat to platform registry every 30 seconds.

Resilient: recreates HTTP client on failure, never crashes the event loop.
"""

import asyncio
import logging
import time

import httpx

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 30  # seconds
MAX_CONSECUTIVE_FAILURES = 10  # log warning after this many failures


class HeartbeatLoop:
    def __init__(self, platform_url: str, workspace_id: str):
        self.platform_url = platform_url
        self.workspace_id = workspace_id
        self.start_time = time.time()
        self.error_count = 0
        self.request_count = 0
        self.active_tasks = 0
        self.current_task = ""
        self.sample_error = ""
        self._task = None
        self._consecutive_failures = 0

    @property
    def error_rate(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.error_count / self.request_count

    def record_error(self, error: str):
        self.error_count += 1
        self.request_count += 1
        self.sample_error = error

    def record_success(self):
        self.request_count += 1

    def start(self):
        self._task = asyncio.create_task(self._loop())
        # Prevent silent task death — log unhandled exceptions
        self._task.add_done_callback(self._on_done)

    def _on_done(self, task):
        if not task.cancelled() and task.exception():
            logger.error("Heartbeat loop died: %s — restarting", task.exception())
            # Restart the loop
            self._task = asyncio.create_task(self._loop())
            self._task.add_done_callback(self._on_done)

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self):
        while True:
            client = None
            try:
                client = httpx.AsyncClient(timeout=10.0)
                while True:
                    try:
                        await client.post(
                            f"{self.platform_url}/registry/heartbeat",
                            json={
                                "workspace_id": self.workspace_id,
                                "error_rate": self.error_rate,
                                "sample_error": self.sample_error,
                                "active_tasks": self.active_tasks,
                                "current_task": self.current_task,
                                "uptime_seconds": int(time.time() - self.start_time),
                            },
                        )
                        # Reset counters after successful heartbeat
                        self.error_count = 0
                        self.request_count = 0
                        self._consecutive_failures = 0
                    except Exception as e:
                        self._consecutive_failures += 1
                        if self._consecutive_failures <= 3 or self._consecutive_failures % MAX_CONSECUTIVE_FAILURES == 0:
                            logger.warning("Heartbeat failed (%d consecutive): %s", self._consecutive_failures, e)
                        if self._consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                            # Recreate client — connection may be stale
                            logger.info("Heartbeat: recreating HTTP client after %d failures", self._consecutive_failures)
                            try:
                                await client.aclose()
                            except Exception:
                                pass
                            break  # Break inner loop to recreate client

                    await asyncio.sleep(HEARTBEAT_INTERVAL)

            except asyncio.CancelledError:
                raise  # Propagate cancellation
            except Exception as e:
                logger.error("Heartbeat loop error: %s — retrying in 30s", e)
                await asyncio.sleep(HEARTBEAT_INTERVAL)
            finally:
                if client:
                    try:
                        await client.aclose()
                    except Exception:
                        pass
