"""
Utilidades del core
Funciones helper para validación y gestión de archivos
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional
from fastapi import UploadFile, HTTPException, status
from PIL import Image
import io
import logging

logger = logging.getLogger(__name__)


# ============================================
# CONFIGURACIÓN
# ============================================

UPLOAD_FOLDER = Path("uploads")
ORIGINALES_FOLDER = UPLOAD_FOLDER / "originales"
MAPAS_FOLDER = UPLOAD_FOLDER / "mapas_atencion"

# Tipos de archivo permitidos
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
ALLOWED_CONTENT_TYPES = {
    'image/jpeg',
    'image/jpg',
    'image/png',
    'image/webp'
}

# Tamaños
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MIN_IMAGE_WIDTH = 100
MIN_IMAGE_HEIGHT = 100
MAX_IMAGE_WIDTH = 10000
MAX_IMAGE_HEIGHT = 10000


# ============================================
# INICIALIZACIÓN
# ============================================

def init_folders():
    """Crear carpetas necesarias si no existen"""
    ORIGINALES_FOLDER.mkdir(parents=True, exist_ok=True)
    MAPAS_FOLDER.mkdir(parents=True, exist_ok=True)
    logger.info(f"✅ Carpetas de upload inicializadas")


# Inicializar al importar
init_folders()


# ============================================
# VALIDACIÓN DE IMÁGENES
# ============================================

def validate_file_extension(filename: str) -> bool:
    """
    Validar extensión del archivo
    
    Args:
        filename: Nombre del archivo
    
    Returns:
        bool: True si la extensión es válida
    """
    if not filename:
        return False
    
    file_ext = Path(filename).suffix.lower()
    return file_ext in ALLOWED_EXTENSIONS


def validate_content_type(content_type: str) -> bool:
    """
    Validar content-type del archivo
    
    Args:
        content_type: Content-Type del archivo
    
    Returns:
        bool: True si el content-type es válido
    """
    return content_type in ALLOWED_CONTENT_TYPES


def validate_image_file(file: UploadFile) -> None:
    """
    Validar que el archivo sea una imagen válida
    
    Verifica:
    - Content-Type
    - Extensión del archivo
    - Nombre del archivo
    
    Args:
        file: Archivo a validar
    
    Raises:
        HTTPException: Si la validación falla
    """
    # 1. Verificar que el archivo existe
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se proporcionó ningún archivo"
        )
    
    # 2. Verificar filename
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no tiene nombre"
        )
    
    # 3. Verificar extensión
    if not validate_file_extension(file.filename):
        file_ext = Path(file.filename).suffix
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extensión de archivo no permitida: '{file_ext}'. "
                   f"Extensiones permitidas: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # 4. Verificar content-type
    if not validate_content_type(file.content_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de archivo no permitido: '{file.content_type}'. "
                   f"Tipos permitidos: JPEG, PNG, WEBP"
        )
    
    logger.info(f"✅ Validación de archivo OK: {file.filename} ({file.content_type})")


async def validate_image_content(file: UploadFile) -> tuple[bytes, Image.Image]:
    """
    Validar contenido de la imagen
    
    Verifica:
    - Que el archivo no esté vacío
    - Que no exceda el tamaño máximo
    - Que sea una imagen válida (PIL puede abrirla)
    - Que tenga dimensiones válidas
    
    Args:
        file: Archivo a validar
    
    Returns:
        tuple: (bytes del archivo, PIL Image)
    
    Raises:
        HTTPException: Si la validación falla
    """
    # 1. Leer bytes
    try:
        image_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error leyendo archivo: {str(e)}"
        )
    
    # 2. Verificar que no esté vacío
    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío (0 bytes)"
        )
    
    # 3. Verificar tamaño máximo
    if len(image_bytes) > MAX_FILE_SIZE:
        size_mb = len(image_bytes) / 1024 / 1024
        max_mb = MAX_FILE_SIZE / 1024 / 1024
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El archivo es muy grande ({size_mb:.2f}MB). "
                   f"Tamaño máximo permitido: {max_mb}MB"
        )
    
    # 4. Intentar abrir como imagen
    try:
        pil_image = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El archivo no es una imagen válida o está corrupto: {str(e)}"
        )
    
    # 5. Verificar formato
    if pil_image.format not in ['JPEG', 'PNG', 'WEBP']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de imagen no soportado: {pil_image.format}. "
                   f"Use JPEG, PNG o WEBP"
        )
    
    # 6. Verificar dimensiones mínimas
    if pil_image.width < MIN_IMAGE_WIDTH or pil_image.height < MIN_IMAGE_HEIGHT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Imagen muy pequeña ({pil_image.width}x{pil_image.height}px). "
                   f"Dimensiones mínimas: {MIN_IMAGE_WIDTH}x{MIN_IMAGE_HEIGHT}px"
        )
    
    # 7. Verificar dimensiones máximas
    if pil_image.width > MAX_IMAGE_WIDTH or pil_image.height > MAX_IMAGE_HEIGHT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Imagen muy grande ({pil_image.width}x{pil_image.height}px). "
                   f"Dimensiones máximas: {MAX_IMAGE_WIDTH}x{MAX_IMAGE_HEIGHT}px"
        )
    
    # 8. Convertir a RGB si es necesario
    if pil_image.mode not in ('RGB', 'RGBA'):
        logger.info(f"Convirtiendo imagen de {pil_image.mode} a RGB")
        pil_image = pil_image.convert('RGB')
    elif pil_image.mode == 'RGBA':
        # Convertir RGBA a RGB (fondo blanco)
        background = Image.new('RGB', pil_image.size, (255, 255, 255))
        background.paste(pil_image, mask=pil_image.split()[3])
        pil_image = background
    
    logger.info(
        f"✅ Imagen válida: {pil_image.width}x{pil_image.height}px, "
        f"formato: {pil_image.format}, modo: {pil_image.mode}, "
        f"tamaño: {len(image_bytes)/1024:.2f}KB"
    )
    
    return image_bytes, pil_image


async def validate_and_load_image(file: UploadFile) -> tuple[Image.Image, bytes]:
    """
    Validar completamente un archivo de imagen
    
    Combina todas las validaciones:
    - Validación básica (extensión, content-type)
    - Validación de contenido (tamaño, formato, dimensiones)
    
    Args:
        file: Archivo a validar
    
    Returns:
        tuple: (PIL Image, bytes del archivo)
    
    Raises:
        HTTPException: Si alguna validación falla
    """
    # 1. Validación básica
    validate_image_file(file)
    
    # 2. Validación de contenido
    image_bytes, pil_image = await validate_image_content(file)
    
    return pil_image, image_bytes


# ============================================
# GESTIÓN DE ARCHIVOS
# ============================================

def sanitize_filename(filename: str) -> str:
    """
    Sanitizar nombre de archivo
    
    Remueve caracteres peligrosos y espacios
    
    Args:
        filename: Nombre original del archivo
    
    Returns:
        str: Nombre sanitizado
    """
    # Remover caracteres peligrosos
    filename = re.sub(r'[^\w\s\-\.]', '', filename)
    # Reemplazar espacios por guiones bajos
    filename = re.sub(r'\s+', '_', filename)
    # Remover múltiples puntos
    filename = re.sub(r'\.+', '.', filename)
    # Convertir a minúsculas
    filename = filename.lower()
    
    return filename


async def save_uploaded_image(
    file: UploadFile,
    numero_expediente: str,
    tipo: str = "original"
) -> str:
    """
    Guardar imagen subida en disco
    
    Args:
        file: Archivo a guardar
        numero_expediente: Número de expediente del registro
        tipo: Tipo de imagen ("original" o "mapa_atencion")
    
    Returns:
        str: Ruta relativa del archivo guardado
    
    Raises:
        HTTPException: Si hay error al guardar
    """
    # Validar tipo
    if tipo not in ["original", "mapa_atencion"]:
        raise ValueError(f"Tipo inválido: {tipo}")
    
    # Determinar carpeta
    folder = ORIGINALES_FOLDER if tipo == "original" else MAPAS_FOLDER
    
    # Generar nombre de archivo
    extension = Path(file.filename).suffix.lower()
    if tipo == "original":
        filename = f"{numero_expediente}{extension}"
    else:
        filename = f"{numero_expediente}_mapa{extension}"
    
    # Sanitizar
    filename = sanitize_filename(filename)
    
    # Construir ruta completa
    file_path = folder / filename
    
    # Guardar archivo
    try:
        # Resetear puntero si es necesario
        await file.seek(0)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"💾 Archivo guardado: {file_path}")
        
    except Exception as e:
        logger.error(f"❌ Error guardando archivo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error guardando archivo: {str(e)}"
        )
    
    # Retornar ruta relativa
    relative_path = file_path.relative_to(UPLOAD_FOLDER)
    return str(relative_path)


def get_file_path(relative_path: str) -> Path:
    """
    Obtener ruta completa de un archivo
    
    Args:
        relative_path: Ruta relativa desde uploads/
    
    Returns:
        Path: Ruta completa del archivo
    """
    return UPLOAD_FOLDER / relative_path


def delete_file(relative_path: str) -> bool:
    """
    Eliminar un archivo
    
    Args:
        relative_path: Ruta relativa desde uploads/
    
    Returns:
        bool: True si se eliminó correctamente
    """
    try:
        file_path = get_file_path(relative_path)
        
        if file_path.exists():
            file_path.unlink()
            logger.info(f"🗑️ Archivo eliminado: {file_path}")
            return True
        else:
            logger.warning(f"⚠️ Archivo no existe: {file_path}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error eliminando archivo: {e}")
        return False


# ============================================
# GENERACIÓN DE NÚMERO DE EXPEDIENTE
# ============================================

def generate_numero_expediente() -> str:
    """
    Generar número de expediente único
    
    Formato: YYYYMMDD-XXXX
    Donde XXXX es un hash aleatorio de 4 caracteres
    
    Returns:
        str: Número de expediente
    """
    import random
    import string
    
    # Fecha actual
    fecha = datetime.now().strftime("%Y%m%d")
    
    # 4 caracteres alfanuméricos aleatorios
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(chars, k=4))
    
    return f"{fecha}-{random_part}"


# ============================================
# INFORMACIÓN DE ARCHIVO
# ============================================

def get_file_info(relative_path: str) -> dict:
    """
    Obtener información de un archivo
    
    Args:
        relative_path: Ruta relativa del archivo
    
    Returns:
        dict con información del archivo
    """
    file_path = get_file_path(relative_path)
    
    if not file_path.exists():
        return {
            "exists": False,
            "path": str(relative_path)
        }
    
    stat = file_path.stat()
    
    return {
        "exists": True,
        "path": str(relative_path),
        "full_path": str(file_path),
        "size_bytes": stat.st_size,
        "size_kb": stat.st_size / 1024,
        "size_mb": stat.st_size / 1024 / 1024,
        "created": datetime.fromtimestamp(stat.st_ctime),
        "modified": datetime.fromtimestamp(stat.st_mtime)
    }