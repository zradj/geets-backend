import json
from typing import Any, Optional

import aio_pika

from .connection import RMQConnection

class RMQPublisher:
    def __init__(self, conn: RMQConnection, exchange_name: str ='messages'):
        self.conn = conn
        self.exchange_name = exchange_name
    
    async def ensure_exchange(self) -> aio_pika.Exchange:
        return await self.conn.declare_exchange(self.exchange_name, type='topic', durable=True)
    
    async def publish(
        self,
        routing_key: str,
        payload: dict[str, Any],
        headers: Optional[dict[str, str]] = None
    ) -> None:
        exchange = await self.ensure_exchange()
        body = json.dumps(payload).encode()
        message = aio_pika.Message(body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT, headers=headers or {})
        await exchange.publish(message=message, routing_key=routing_key)
