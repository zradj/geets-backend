import logging
from typing import Callable

import aio_pika

from .connection import RMQConnection

logger = logging.getLogger(__name__)

class RMQConsumer:
    def __init__(
            self,
            conn: RMQConnection,
            queue_name: str,
            routing_keys: list[str],
            exchange_name: str = 'messages',
        ):
        self.conn = conn
        self.queue_name = queue_name
        self.routing_keys = routing_keys
        self.exchange_name = exchange_name
        self._stopping = False
    
    async def start_consuming(self, handler: Callable[[aio_pika.IncomingMessage], None], prefetch: int = 10):
        await self.conn.connect()
        ch = await self.conn.get_channel()
        await ch.set_qos(prefetch_count=prefetch)
        exchange = await self.conn.declare_exchange(self.exchange_name, type='topic')
        queue = await ch.declare_queue(self.queue_name, durable=True)
        for routing_key in self.routing_keys:
            await queue.bind(exchange, routing_key)
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process(requeue=False):
                    try:
                        await handler(message)
                    except Exception:
                        logger.exception('Handler failed')
                if self._stopping:
                    break

    async def stop(self):
        self._stopping = True
