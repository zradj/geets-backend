from fastapi.routing import APIRouter

from .auth import router as auth_router
from .conversations import router as conv_router
from .groups import router as group_router
from .users import router as user_router

api_router = APIRouter(prefix='/api')

api_router.include_router(auth_router)
api_router.include_router(conv_router)
api_router.include_router(group_router)
api_router.include_router(user_router)

__all__ = ['api_router']
