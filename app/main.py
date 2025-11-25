from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from datetime import datetime

from app.config import settings
from app.db.database import connect_to_mongo, close_mongo_connection
from app.routes import (
    auth_router,
    especialistas_router,
    registros_router,
    dashboard_router
)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionar inicio y cierre de la aplicación"""
    # Startup
    logger.info("🚀 Iniciando aplicación SCANNA...")
    await connect_to_mongo()
    logger.info("✅ Aplicación lista")
    
    yield
    
    # Shutdown
    logger.info("🛑 Cerrando aplicación...")
    await close_mongo_connection()
    logger.info("👋 Aplicación cerrada")


# Crear aplicación FastAPI
app = FastAPI(
    title="SCANNA API",
    description="API para detección de anemia mediante análisis de imágenes oculares",
    version="1.0.0",
    lifespan=lifespan
)


# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware para logging de requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"📨 {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"📤 Status: {response.status_code}")
    return response


# Exception handler global
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ Error no manejado: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Error interno del servidor",
            "message": str(exc) if settings.mongodb_uri.startswith("mongodb://localhost") else "Error procesando solicitud"
        }
    )


# Incluir routers
app.include_router(auth_router)
app.include_router(especialistas_router)
app.include_router(registros_router)
app.include_router(dashboard_router)


# Servir archivos estáticos (imágenes subidas)
upload_path = Path(settings.upload_folder)
if upload_path.exists():
    app.mount("/uploads", StaticFiles(directory=str(upload_path)), name="uploads")


# Rutas básicas
@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "message": "SCANNA API - Detección de Anemia",
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from app.db.database import get_database
    
    try:
        db = get_database()
        # Verificar conexión a MongoDB
        await db.command("ping")
        
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e)
            }
        )


@app.get("/api/info")
async def api_info():
    """Información de la API"""
    return {
        "name": "SCANNA API",
        "version": "1.0.0",
        "description": "API para detección de anemia mediante análisis de imágenes oculares",
        "endpoints": {
            "auth": "/auth",
            "especialistas": "/especialistas",
            "registros": "/registros",
            "dashboard": "/dashboard"
        },
        "documentation": "/docs"
    }