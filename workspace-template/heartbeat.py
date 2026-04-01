"""Send heartbeat to platform registry every 30 seconds."""

import asyncio
import time

import httpx


class HeartbeatLoop:
    def __init__(self, platform_url: str, workspace_id: str):
        self.platform_url = platform_url
        self.workspace_id = workspace_id
        self.start_time = time.time()
        self.error_count = 0
        self.request_count = 0
        self.active_tasks = 0
        self.sample_error = ""
        self._task = None

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

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self):
        async with httpx.AsyncClient(timeout=10.0) as client:
            while True:
                try:
                    await client.post(
                        f"{self.platform_url}/registry/heartbeat",
                        json={
                            "workspace_id": self.workspace_id,
                            "error_rate": self.error_rate,
                            "sample_error": self.sample_error,
                            "active_tasks": self.active_tasks,
                            "uptime_seconds": int(time.time() - self.start_time),
                        },
                    )
                except Exception as e:
                    print(f"Heartbeat failed: {e}")

                await asyncio.sleep(30)
