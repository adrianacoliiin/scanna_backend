from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timedelta

from app.db.models import (
    EspecialistaCreate, 
    EspecialistaLogin, 
    Token,
    EspecialistaResponse
)
from app.core.auth import get_password_hash, verify_password, create_access_token, get_current_active_especialista
from app.db.database import get_database
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/registro", response_model=EspecialistaResponse, status_code=status.HTTP_201_CREATED)
async def registrar_especialista(especialista: EspecialistaCreate):
    """Registrar nuevo especialista"""
    db = get_database()
    
    # Verificar si el email ya existe
    existing = await db.especialistas.find_one({"email": especialista.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )
    
    # Verificar cédula profesional si se proporciona
    if especialista.cedula_profesional:
        existing_cedula = await db.especialistas.find_one(
            {"cedulaProfesional": especialista.cedula_profesional}
        )
        if existing_cedula:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cédula profesional ya está registrada"
            )
    
    # Crear documento de especialista
    especialista_doc = {
        "nombre": especialista.nombre,
        "apellido": especialista.apellido,
        "email": especialista.email,
        "password": get_password_hash(especialista.password),
        "area": especialista.area,
        "cedulaProfesional": especialista.cedula_profesional or "",
        "hospital": especialista.hospital or "",
        "telefono": especialista.telefono or "",
        "activo": True,
        "fechaRegistro": datetime.utcnow(),
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    }
    
    # Insertar en la base de datos
    result = await db.especialistas.insert_one(especialista_doc)
    
    # Obtener el especialista creado
    created_especialista = await db.especialistas.find_one({"_id": result.inserted_id})
    
    # Convertir ObjectId a string para la respuesta
    created_especialista["_id"] = str(created_especialista["_id"])
    
    return created_especialista


@router.post("/login", response_model=Token)
async def login(credentials: EspecialistaLogin):
    """Iniciar sesión"""
    db = get_database()
    
    # Buscar especialista por email
    especialista = await db.especialistas.find_one({"email": credentials.email})
    
    # Verificar que existe y la contraseña es correcta
    if not especialista or not verify_password(credentials.password, especialista["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verificar que la cuenta esté activa
    if not especialista.get("activo", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta inactiva. Contacte al administrador"
        )
    
    # Crear token de acceso
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": especialista["email"]},
        expires_delta=access_token_expires
    )
    
    # Actualizar último acceso
    await db.especialistas.update_one(
        {"_id": especialista["_id"]},
        {"$set": {"ultimoAcceso": datetime.utcnow()}}
    )
    
    # Preparar respuesta del especialista
    especialista["_id"] = str(especialista["_id"])
    especialista_response = EspecialistaResponse(**especialista)
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        especialista=especialista_response
    )


@router.post("/verificar-token", response_model=EspecialistaResponse)
async def verificar_token(current_especialista: dict = Depends(get_current_active_especialista)):
    """Verificar si el token es válido y retornar datos del especialista"""
    current_especialista["_id"] = str(current_especialista["_id"])
    return EspecialistaResponse(**current_especialista)