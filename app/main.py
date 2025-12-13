import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import api_router
from config import RMQ_URL
from db.session import init_db
from rabbitmq import RMQConnection, RMQConsumer, RMQPublisher
from ws import ws_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.rabbit = RMQConnection(RMQ_URL)
    await app.state.rabbit.connect()
    await app.state.rabbit.declare_exchange('messages')
    app.state.message_publisher = RMQPublisher(app.state.rabbit, exchange_name='messages')
    # app.state.message_consumer = RMQConsumer(app.state.rabbit, queue_name='')
    # asyncio.create_task()

    yield

    # await app.state.message_consumer.stop()
    await app.state.rabbit.close()

app = FastAPI(lifespan=lifespan)
app.include_router(api_router)
app.include_router(ws_router)

@app.get('/')
async def read_root():
    return {'Hello': 'World'}
