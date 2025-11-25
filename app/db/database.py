from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class MongoDB:
    client: AsyncIOMotorClient = None
    db = None

mongodb = MongoDB()

async def connect_to_mongo():
    """Conectar a MongoDB Atlas"""
    try:
        mongodb.client = AsyncIOMotorClient(settings.mongodb_uri)
        mongodb.db = mongodb.client[settings.mongodb_db_name]
        
        # Verificar conexión
        await mongodb.client.admin.command('ping')
        logger.info("✅ Conectado exitosamente a MongoDB Atlas")
        
    except Exception as e:
        logger.error(f"❌ Error conectando a MongoDB: {e}")
        raise

async def close_mongo_connection():
    """Cerrar conexión a MongoDB"""
    if mongodb.client:
        mongodb.client.close()
        logger.info("🔌 Conexión a MongoDB cerrada")

def get_database():
    """Obtener instancia de la base de datos"""
    return mongodb.db