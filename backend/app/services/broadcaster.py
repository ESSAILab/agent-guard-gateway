"""
实时事件广播器（用于大屏展示）。

维护一组 WebSocket 连接，将护栏检测过程中的关键事件（请求到达、策略开始、
模型调用、顺序检测、最终结果）实时推送给大屏前端。
"""
import asyncio
import json
from typing import Any, Dict, List, Set

from starlette.websockets import WebSocket


class EventBroadcaster:
    """简单的 WebSocket 广播中心，线程/协程安全。"""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)

    async def broadcast(self, event_type: str, payload: Dict[str, Any]) -> None:
        """向所有连接推送一条事件。失败的连接将被移除。"""
        message = json.dumps(
            {"type": event_type, "payload": payload}, ensure_ascii=False
        )
        async with self._lock:
            targets: List[WebSocket] = list(self._connections)
        dead: List[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)


# 全局广播器单例
broadcaster = EventBroadcaster()
