from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings
from app.db.models import TokenData
from app.db.database import get_database

# Configuración de encriptación
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# ============================================
# FUNCIONES DE HASHING
# ============================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verificar contraseña"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashear contraseña"""
    return pwd_context.hash(password)


# ============================================
# FUNCIONES JWT
# ============================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crear token JWT"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    
    return encoded_jwt

def decode_access_token(token: str) -> TokenData:
    """Decodificar token JWT"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        email: str = payload.get("sub")
        
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido"
            )
        
        return TokenData(email=email)
    
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado"
        )


# ============================================
# DEPENDENCIAS DE AUTENTICACIÓN
# ============================================

async def get_current_especialista(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Obtener especialista autenticado desde el token"""
    
    token = credentials.credentials
    token_data = decode_access_token(token)
    
    db = get_database()
    especialista = await db.especialistas.find_one(
        {"email": token_data.email, "activo": True}
    )
    
    if especialista is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Especialista no encontrado o inactivo"
        )
    
    # Actualizar último acceso
    await db.especialistas.update_one(
        {"_id": especialista["_id"]},
        {"$set": {"ultimoAcceso": datetime.utcnow()}}
    )
    
    return especialista


async def get_current_active_especialista(
    current_especialista: dict = Depends(get_current_especialista)
):
    """Verificar que el especialista esté activo"""
    if not current_especialista.get("activo", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta de especialista inactiva"
        )
    return current_especialista