import os
import shutil
from datetime import datetime
from typing import Tuple
from fastapi import UploadFile, HTTPException
from pathlib import Path
import uuid

from app.config import settings

# Extensiones permitidas
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

def ensure_upload_directory():
    """Crear directorios de uploads si no existen"""
    upload_path = Path(settings.upload_folder)
    upload_path.mkdir(parents=True, exist_ok=True)
    
    # Crear subdirectorios
    (upload_path / "originales").mkdir(exist_ok=True)
    (upload_path / "mapas_atencion").mkdir(exist_ok=True)

def validate_image_file(file: UploadFile) -> None:
    """Validar que el archivo sea una imagen válida"""
    
    # Verificar extensión
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido. Use: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Verificar que el archivo tenga contenido
    if file.size == 0:
        raise HTTPException(
            status_code=400,
            detail="El archivo está vacío"
        )
    
    # Verificar tamaño máximo
    if file.size > settings.max_upload_size:
        max_mb = settings.max_upload_size / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"El archivo es muy grande. Máximo: {max_mb}MB"
        )

async def save_uploaded_image(
    file: UploadFile,
    numero_expediente: str,
    tipo: str = "original"
) -> str:
    """
    Guardar imagen subida
    
    Args:
        file: Archivo subido
        numero_expediente: Número de expediente
        tipo: "original" o "mapa_atencion"
    
    Returns:
        Ruta relativa del archivo guardado
    """
    
    # Validar archivo
    validate_image_file(file)
    
    # Determinar subdirectorio
    if tipo == "original":
        subdir = "originales"
        suffix = ""
    elif tipo == "mapa_atencion":
        subdir = "mapas_atencion"
        suffix = "_mapa"
    else:
        raise ValueError(f"Tipo de archivo no válido: {tipo}")
    
    # Generar nombre de archivo
    file_ext = Path(file.filename).suffix.lower()
    filename = f"{numero_expediente}{suffix}{file_ext}"
    
    # Ruta completa
    file_path = Path(settings.upload_folder) / subdir / filename
    
    # Guardar archivo
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error guardando archivo: {str(e)}"
        )
    finally:
        file.file.close()
    
    # Retornar ruta relativa
    return str(Path(subdir) / filename)

def get_file_path(relative_path: str) -> Path:
    """Obtener ruta absoluta de un archivo"""
    return Path(settings.upload_folder) / relative_path

def delete_file(relative_path: str) -> bool:
    """Eliminar archivo"""
    try:
        file_path = get_file_path(relative_path)
        if file_path.exists():
            file_path.unlink()
            return True
        return False
    except Exception:
        return False

def generate_numero_expediente() -> str:
    """
    Generar número de expediente único
    Formato: YYYYMMDD-XXXX
    """
    fecha = datetime.now().strftime("%Y%m%d")
    unique_id = str(uuid.uuid4())[:4].upper()
    return f"{fecha}-{unique_id}"

# Inicializar directorios al importar
ensure_upload_directory()