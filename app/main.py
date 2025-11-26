from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import os
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
    
    # Crear directorios para imágenes si no existen
    os.makedirs("originales", exist_ok=True)
    os.makedirs("mapas_atencion", exist_ok=True)
    logger.info("📁 Directorios de imágenes verificados")
    
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
# IMPORTANTE: Los StaticFiles DEBEN montarse DESPUÉS de los routers
# para evitar conflictos de rutas

# 1. Directorio de uploads general (si existe en settings)
upload_path = Path(settings.upload_folder)
if upload_path.exists():
    app.mount("/uploads", StaticFiles(directory=str(upload_path)), name="uploads")
    logger.info(f"📂 Sirviendo /uploads desde {upload_path}")

# 2. Directorio de imágenes originales
originales_path = Path("originales")
if originales_path.exists():
    app.mount("/originales", StaticFiles(directory="originales"), name="originales")
    logger.info(f"📂 Sirviendo /originales")
else:
    logger.warning(f"⚠️ Directorio 'originales' no existe, creándolo...")
    originales_path.mkdir(exist_ok=True)
    app.mount("/originales", StaticFiles(directory="originales"), name="originales")

# 3. Directorio de mapas de atención
mapas_path = Path("mapas_atencion")
if mapas_path.exists():
    app.mount("/mapas_atencion", StaticFiles(directory="mapas_atencion"), name="mapas_atencion")
    logger.info(f"📂 Sirviendo /mapas_atencion")
else:
    logger.warning(f"⚠️ Directorio 'mapas_atencion' no existe, creándolo...")
    mapas_path.mkdir(exist_ok=True)
    app.mount("/mapas_atencion", StaticFiles(directory="mapas_atencion"), name="mapas_atencion")


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
        
        # Verificar directorios de imágenes
        dirs_status = {
            "originales": os.path.exists("originales"),
            "mapas_atencion": os.path.exists("mapas_atencion")
        }
        
        return {
            "status": "healthy",
            "database": "connected",
            "storage": dirs_status,
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
        "static_files": {
            "originales": "/originales",
            "mapas_atencion": "/mapas_atencion",
            "uploads": "/uploads"
        },
        "documentation": "/docs"
    }


# Endpoint de debugging para listar archivos (solo en desarrollo)
if settings.mongodb_uri.startswith("mongodb://localhost"):
    @app.get("/debug/files")
    async def list_files():
        """Listar archivos en directorios de imágenes (solo desarrollo)"""
        try:
            originales = list(Path("originales").glob("*")) if Path("originales").exists() else []
            mapas = list(Path("mapas_atencion").glob("*")) if Path("mapas_atencion").exists() else []
            
            return {
                "originales": [f.name for f in originales if f.is_file()],
                "mapas_atencion": [f.name for f in mapas if f.is_file()],
                "total_originales": len(originales),
                "total_mapas": len(mapas)
            }
        except Exception as e:
            return {"error": str(e)}