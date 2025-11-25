from .auth import router as auth_router
from .especialistas import router as especialistas_router
from .registros import router as registros_router
from .dashboard import router as dashboard_router

__all__ = [
    "auth_router",
    "especialistas_router",
    "registros_router",
    "dashboard_router"
]