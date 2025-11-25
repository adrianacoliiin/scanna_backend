"""
Script para inicializar la base de datos MongoDB con índices y validaciones
Ejecutar una vez después de crear la base de datos en Atlas
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_indexes():
    """Crear todos los índices necesarios"""
    
    # Conectar a MongoDB
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]
    
    logger.info("🔧 Creando índices en MongoDB...")
    
    try:
        # ============================================
        # ÍNDICES PARA ESPECIALISTAS
        # ============================================
        logger.info("📝 Creando índices para 'especialistas'...")
        
        await db.especialistas.create_index("email", unique=True)
        await db.especialistas.create_index("cedula_profesional", unique=True, sparse=True)
        await db.especialistas.create_index("activo")
        await db.especialistas.create_index("hospital_id")
        
        logger.info("✅ Índices de especialistas creados")
        
        # ============================================
        # ÍNDICES PARA REGISTROS
        # ============================================
        logger.info("📝 Creando índices para 'registros'...")
        
        await db.registros.create_index("numero_expediente", unique=True)
        await db.registros.create_index("especialista_id")
        await db.registros.create_index("fecha_analisis", expireAfterSeconds=-1)  # -1 = no expira
        await db.registros.create_index("resultado")
        await db.registros.create_index("paciente.nombre", name="paciente_nombre_text")
        
        # Índice compuesto para queries frecuentes
        await db.registros.create_index([
            ("especialista_id", 1),
            ("fecha_analisis", -1)
        ])
        
        logger.info("✅ Índices de registros creados")
        
        # ============================================
        # ÍNDICES PARA HOSPITALES (futuro)
        # ============================================
        logger.info("📝 Creando índices para 'hospitales'...")
        
        await db.hospitales.create_index("nombre")
        await db.hospitales.create_index("activo")
        await db.hospitales.create_index("direccion.estado")
        await db.hospitales.create_index("direccion.ciudad")
        
        logger.info("✅ Índices de hospitales creados")
        
        # ============================================
        # VALIDACIONES DE ESQUEMA
        # ============================================
        logger.info("📝 Aplicando validaciones de esquema...")
        
        # Validación para especialistas
        especialistas_validator = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["nombre", "apellido", "email", "password", "area", "fecha_registro", "activo"],
                "properties": {
                    "nombre": {"bsonType": "string"},
                    "apellido": {"bsonType": "string"},
                    "email": {
                        "bsonType": "string",
                        "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
                    },
                    "password": {"bsonType": "string"},
                    "area": {
                        "bsonType": "string",
                        "enum": ["Medicina General", "Hematología", "Medicina Interna", "Pediatría", "Ginecología", "Otro"]
                    },
                    "activo": {"bsonType": "bool"}
                }
            }
        }
        
        # Validación para registros
        registros_validator = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["numero_expediente", "paciente", "especialista_id", "resultado", "fecha_analisis"],
                "properties": {
                    "numero_expediente": {"bsonType": "string"},
                    "paciente": {
                        "bsonType": "object",
                        "required": ["nombre", "edad", "sexo"],
                        "properties": {
                            "nombre": {"bsonType": "string"},
                            "edad": {
                                "bsonType": "int",
                                "minimum": 0,
                                "maximum": 150
                            },
                            "sexo": {
                                "bsonType": "string",
                                "enum": ["Masculino", "Femenino", "Otro"]
                            }
                        }
                    },
                    "especialista_id": {"bsonType": "objectId"},
                    "resultado": {
                        "bsonType": "string",
                        "enum": ["Anemia", "No Anemia"]
                    }
                }
            }
        }
        
        # Aplicar validadores (requiere permisos en Atlas)
        try:
            await db.command({
                "collMod": "especialistas",
                "validator": especialistas_validator
            })
            logger.info("✅ Validación de especialistas aplicada")
        except Exception as e:
            logger.warning(f"⚠️  No se pudo aplicar validación de especialistas: {e}")
        
        try:
            await db.command({
                "collMod": "registros",
                "validator": registros_validator
            })
            logger.info("✅ Validación de registros aplicada")
        except Exception as e:
            logger.warning(f"⚠️  No se pudo aplicar validación de registros: {e}")
        
        # ============================================
        # VERIFICACIÓN
        # ============================================
        logger.info("🔍 Verificando índices creados...")
        
        especialistas_indexes = await db.especialistas.index_information()
        registros_indexes = await db.registros.index_information()
        hospitales_indexes = await db.hospitales.index_information()
        
        logger.info(f"  - Especialistas: {len(especialistas_indexes)} índices")
        logger.info(f"  - Registros: {len(registros_indexes)} índices")
        logger.info(f"  - Hospitales: {len(hospitales_indexes)} índices")
        
        logger.info("✅ Base de datos inicializada correctamente")
        
    except Exception as e:
        logger.error(f"❌ Error inicializando base de datos: {e}")
        raise
    
    finally:
        client.close()


async def create_test_data():
    """Crear datos de prueba (opcional)"""
    
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]
    
    logger.info("🧪 Creando datos de prueba...")
    
    try:
        # Verificar si ya existen datos
        count = await db.especialistas.count_documents({})
        if count > 0:
            logger.info("⚠️  Ya existen datos. Saltando creación de datos de prueba.")
            return
        
        # Crear especialista de prueba
        from auth import get_password_hash
        from datetime import datetime
        
        test_especialista = {
            "nombre": "Dr. Juan",
            "apellido": "Pérez",
            "email": "test@scanna.com",
            "password": get_password_hash("test123456"),
            "area": "Medicina General",
            "cedula_profesional": "1234567",
            "hospital": "Hospital General de Durango",
            "telefono": "+52 618 123 4567",
            "activo": True,
            "fecha_registro": datetime.utcnow(),
            "ultimo_acceso": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "deleted_at": None
        }
        
        result = await db.especialistas.insert_one(test_especialista)
        logger.info(f"✅ Especialista de prueba creado (email: test@scanna.com, password: test123456)")
        logger.info(f"   ID: {result.inserted_id}")
        
    except Exception as e:
        logger.error(f"❌ Error creando datos de prueba: {e}")
    
    finally:
        client.close()


async def main():
    """Función principal"""
    logger.info("=" * 60)
    logger.info("SCANNA - Inicialización de Base de Datos")
    logger.info("=" * 60)
    
    # Crear índices
    await create_indexes()
    
    # Preguntar si crear datos de prueba
    logger.info("\n" + "=" * 60)
    create_test = input("¿Deseas crear datos de prueba? (s/n): ").lower()
    
    if create_test == 's':
        await create_test_data()
    
    logger.info("\n" + "=" * 60)
    logger.info("🎉 Inicialización completada")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())