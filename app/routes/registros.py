from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form
from datetime import datetime
from typing import Optional, List
from bson import ObjectId
from PIL import Image
import io
import logging

from app.db.models import RegistroResponse
from app.core.auth import get_current_active_especialista
from app.core.utils import save_uploaded_image, generate_numero_expediente, delete_file, get_file_path
from app.db.database import get_database
from app.ai import get_model, generate_medical_explanation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/registros", tags=["Registros"])


# ============================================
# FUNCIÓN DE VALIDACIÓN DE IMAGEN
# ============================================

def validate_image_file(file: UploadFile) -> None:
    """
    Validar que el archivo sea una imagen válida
    
    Verifica:
    - Content-Type
    - Extensión del archivo
    - Que el archivo pueda abrirse como imagen PIL
    
    Raises:
        HTTPException: Si la validación falla
    """
    # 1. Verificar content-type
    allowed_content_types = [
        'image/jpeg',
        'image/jpg', 
        'image/png',
        'image/webp'
    ]
    
    if file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de archivo no permitido: {file.content_type}. "
                   f"Use: JPEG, PNG o WEBP"
        )
    
    # 2. Verificar extensión del archivo
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no tiene nombre"
        )
    
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    file_ext = file.filename.lower().split('.')[-1]
    
    if f".{file_ext}" not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extensión de archivo no permitida: .{file_ext}. "
                   f"Use: .jpg, .jpeg, .png o .webp"
        )
    
    logger.info(f"✅ Archivo validado: {file.filename} ({file.content_type})")


async def validate_and_load_image(file: UploadFile) -> tuple[Image.Image, bytes]:
    """
    Validar y cargar imagen como PIL Image
    
    Returns:
        tuple: (PIL Image, bytes del archivo)
    
    Raises:
        HTTPException: Si hay error al cargar o validar la imagen
    """
    # 1. Validar tipo de archivo
    validate_image_file(file)
    
    # 2. Leer bytes
    try:
        image_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error leyendo archivo: {str(e)}"
        )
    
    # 3. Verificar que no esté vacío
    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío"
        )
    
    # 4. Verificar tamaño (max 10MB por defecto)
    max_size = 10 * 1024 * 1024  # 10MB
    if len(image_bytes) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El archivo es muy grande. Máximo: {max_size / 1024 / 1024}MB"
        )
    
    # 5. Intentar abrir como imagen PIL
    try:
        pil_image = Image.open(io.BytesIO(image_bytes))
        
        # Verificar que sea RGB o convertir
        if pil_image.mode not in ('RGB', 'L'):
            pil_image = pil_image.convert('RGB')
        elif pil_image.mode == 'L':
            # Grayscale a RGB
            pil_image = pil_image.convert('RGB')
        
        # Verificar dimensiones mínimas (opcional)
        min_width, min_height = 100, 100
        if pil_image.width < min_width or pil_image.height < min_height:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Imagen muy pequeña. Mínimo: {min_width}x{min_height}px"
            )
        
        logger.info(f"✅ Imagen cargada: {pil_image.width}x{pil_image.height}, modo: {pil_image.mode}")
        
        return pil_image, image_bytes
        
    except Image.UnidentifiedImageError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no es una imagen válida o está corrupto"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error procesando imagen: {str(e)}"
        )


# ============================================
# ENDPOINTS
# ============================================

@router.post("/analizar", status_code=status.HTTP_200_OK)
async def analizar_imagen_ia(
    imagen: UploadFile = File(...),
    generar_explicacion: bool = Form(True),
    current_especialista: dict = Depends(get_current_active_especialista)
):
    """
    🤖 Analizar imagen con IA (sin guardar registro)
    
    Útil para:
    - Pruebas rápidas del modelo
    - Vista previa antes de guardar
    - Testing del sistema
    
    Returns:
        dict con resultado, confianza, y opcionalmente explicación médica
    """
    logger.info(f"🔬 Analizando imagen: {imagen.filename}")
    
    try:
        # 1. Validar y cargar imagen
        pil_image, _ = await validate_and_load_image(imagen)
        
        # 2. Analizar con modelo ViT
        model = get_model()
        result = model.predict(pil_image, generate_heatmap=generar_explicacion)
        
        logger.info(f"✅ Predicción: {result['resultado']} ({result['confianza']}%)")
        
        # 3. Generar explicación si se solicita
        if generar_explicacion:
            explanation = generate_medical_explanation(
                predicted_class=result["resultado"],
                confidence=result["confianza"],
                combined_image=result.get("heatmap")
            )
            result["explicacion_medica"] = explanation
            
            # Eliminar heatmap del response (muy pesado para JSON)
            if "heatmap" in result:
                del result["heatmap"]
        
        return {
            "success": True,
            "analisis": result,
            "mensaje": "Análisis completado exitosamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en análisis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analizando imagen: {str(e)}"
        )


@router.post("/", response_model=RegistroResponse, status_code=status.HTTP_201_CREATED)
async def crear_registro(
    paciente_nombre: str = Form(..., min_length=1, max_length=200),
    paciente_edad: int = Form(..., ge=0, le=150),
    paciente_sexo: str = Form(...),
    imagen_original: UploadFile = File(...),
    generar_explicacion: bool = Form(True),
    numero_expediente: Optional[str] = Form(None),
    current_especialista: dict = Depends(get_current_active_especialista)
):
    """
    🤖 Crear un nuevo registro de detección con análisis de IA OBLIGATORIO
    
    El modelo ViT analiza automáticamente cada imagen subida.
    
    Args:
        paciente_nombre: Nombre completo del paciente
        paciente_edad: Edad del paciente (0-150 años)
        paciente_sexo: Sexo del paciente (Masculino/Femenino/Otro)
        imagen_original: Imagen del ojo del paciente (JPG/PNG/WEBP, max 10MB)
        generar_explicacion: Si generar explicación médica con Gemini (default: True)
        numero_expediente: Número de expediente opcional (se genera si no se proporciona)
    
    Returns:
        RegistroResponse con todos los datos del registro creado
    """
    db = get_database()
    
    logger.info(f"📝 Creando registro para: {paciente_nombre}, {paciente_edad} años")
    
    # ========================================
    # 1. VALIDACIONES BÁSICAS
    # ========================================
    
    # Validar sexo
    if paciente_sexo not in ["Masculino", "Femenino", "Otro"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sexo debe ser 'Masculino', 'Femenino' u 'Otro'"
        )
    
    # ========================================
    # 2. VALIDAR Y CARGAR IMAGEN
    # ========================================
    
    try:
        pil_image, image_bytes = await validate_and_load_image(imagen_original)
        # Resetear puntero para guardar después
        await imagen_original.seek(0)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error validando imagen: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error validando imagen: {str(e)}"
        )
    
    # ========================================
    # 3. ANÁLISIS CON IA (OBLIGATORIO)
    # ========================================
    
    logger.info("🤖 Iniciando análisis con IA...")
    
    try:
        # Cargar modelo (singleton, solo se carga una vez)
        model = get_model()
        
        # Predecir
        ia_result = model.predict(pil_image, generate_heatmap=generar_explicacion)
        
        resultado = ia_result["resultado"]  # "Anemia" o "No Anemia"
        confianza = ia_result["confianza"]
        
        logger.info(f"✅ Predicción IA: {resultado} (confianza: {confianza}%)")
        
        # Generar explicación con Gemini (si se solicita)
        ai_summary = None
        imagen_mapa = None
        
        if generar_explicacion:
            logger.info("🧠 Generando explicación con Gemini...")
            
            try:
                ai_summary = generate_medical_explanation(
                    predicted_class=resultado,
                    confidence=confianza,
                    combined_image=ia_result.get("heatmap")
                )
                logger.info("✅ Explicación generada")
            except Exception as e:
                logger.warning(f"⚠️ Error generando explicación: {e}")
                # Continuar sin explicación si Gemini falla
                ai_summary = f"Análisis completado. Resultado: {resultado} (confianza: {confianza}%)"
            
            # Guardar heatmap como archivo temporal
            if ia_result.get("heatmap"):
                try:
                    heatmap_bytes = io.BytesIO()
                    ia_result["heatmap"].save(heatmap_bytes, format='PNG')
                    heatmap_bytes.seek(0)
                    
                    from fastapi import UploadFile as UF
                    imagen_mapa = UF(
                        filename=f"heatmap_{datetime.now().timestamp()}.png",
                        file=heatmap_bytes
                    )
                    logger.info("✅ Heatmap generado")
                except Exception as e:
                    logger.warning(f"⚠️ Error guardando heatmap: {e}")
        
    except Exception as e:
        logger.error(f"❌ Error en análisis de IA: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en análisis de IA: {str(e)}. "
                   "Verifica que el modelo esté correctamente cargado."
        )
    
    # ========================================
    # 4. GENERAR NÚMERO DE EXPEDIENTE
    # ========================================
    
    if not numero_expediente:
        numero_expediente = generate_numero_expediente()
        
        # Verificar unicidad
        max_retries = 10
        retry_count = 0
        while await db.registros.find_one({"numeroExpediente": numero_expediente}):
            numero_expediente = generate_numero_expediente()
            retry_count += 1
            if retry_count >= max_retries:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error generando número de expediente único"
                )
    else:
        # Verificar que no exista
        existing = await db.registros.find_one({"numeroExpediente": numero_expediente})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El número de expediente '{numero_expediente}' ya existe"
            )
    
    logger.info(f"📋 Número de expediente: {numero_expediente}")
    
    # ========================================
    # 5. GUARDAR IMÁGENES EN DISCO
    # ========================================
    
    logger.info("💾 Guardando imágenes...")
    
    try:
        ruta_original = await save_uploaded_image(
            imagen_original,
            numero_expediente,
            tipo="original"
        )
        logger.info(f"✅ Imagen original guardada: {ruta_original}")
    except Exception as e:
        logger.error(f"❌ Error guardando imagen original: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error guardando imagen original: {str(e)}"
        )
    
    # Guardar heatmap si existe
    ruta_mapa = None
    if imagen_mapa:
        try:
            ruta_mapa = await save_uploaded_image(
                imagen_mapa,
                numero_expediente,
                tipo="mapa_atencion"
            )
            logger.info(f"✅ Heatmap guardado: {ruta_mapa}")
        except Exception as e:
            logger.warning(f"⚠️ Error guardando heatmap: {e}")
            # Continuar sin heatmap si falla
            # No eliminar imagen original ya guardada
    
    # ========================================
    # 6. CREAR DOCUMENTO PARA MONGODB
    # ========================================
    
    registro_doc = {
        "numeroExpediente": numero_expediente,
        "paciente": {
            "nombre": paciente_nombre,
            "edad": paciente_edad,
            "sexo": paciente_sexo
        },
        "especialistaId": current_especialista["_id"],
        "imagenes": {
            "rutaOriginal": ruta_original,
            "rutaMapaAtencion": ruta_mapa
        },
        "analisis": {
            "resultado": resultado,
            "aiSummary": ai_summary,
            "confianza": confianza,
            "procesadoConIA": True
        },
        "resultado": resultado,
        "fechaAnalisis": datetime.utcnow(),
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    }
    
    # ========================================
    # 7. INSERTAR EN MONGODB
    # ========================================
    
    logger.info("💾 Guardando en MongoDB...")
    
    try:
        result = await db.registros.insert_one(registro_doc)
        logger.info(f"✅ Registro guardado: {result.inserted_id}")
    except Exception as e:
        logger.error(f"❌ Error guardando en MongoDB: {e}")
        
        # Limpiar archivos guardados si falla la BD
        try:
            delete_file(ruta_original)
            if ruta_mapa:
                delete_file(ruta_mapa)
        except:
            pass
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error guardando registro en base de datos: {str(e)}"
        )
    
    # ========================================
    # 8. OBTENER Y RETORNAR REGISTRO CREADO
    # ========================================
    
    created_registro = await db.registros.find_one({"_id": result.inserted_id})
    
    # Convertir ObjectIds a strings para JSON
    created_registro["_id"] = str(created_registro["_id"])
    created_registro["especialistaId"] = str(created_registro["especialistaId"])
    
    logger.info(f"🎉 Registro completado exitosamente: {numero_expediente}")
    
    return created_registro


@router.post("/{registro_id}/reanalizar", status_code=status.HTTP_200_OK)
async def reanalizar_registro(
    registro_id: str,
    generar_explicacion: bool = Form(True),
    current_especialista: dict = Depends(get_current_active_especialista)
):
    """
    🔄 Re-analizar un registro existente con IA
    
    Útil para:
    - Actualizar análisis con nueva versión del modelo
    - Generar explicación si no se generó originalmente
    - Corregir análisis previos
    """
    db = get_database()
    
    logger.info(f"🔄 Re-analizando registro: {registro_id}")
    
    # Validar ObjectId
    if not ObjectId.is_valid(registro_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de registro inválido"
        )
    
    # Buscar registro
    registro = await db.registros.find_one({
        "_id": ObjectId(registro_id),
        "especialistaId": current_especialista["_id"]
    })
    
    if not registro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro no encontrado"
        )
    
    # Obtener ruta de imagen original
    ruta_original = registro.get("imagenes", {}).get("rutaOriginal")
    if not ruta_original:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registro no tiene imagen original"
        )
    
    # Construir ruta completa
    image_path = get_file_path(ruta_original)
    
    if not image_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo de imagen no encontrado en el servidor"
        )
    
    try:
        # Cargar imagen
        pil_image = Image.open(image_path).convert("RGB")
        
        # Analizar con IA
        model = get_model()
        ia_result = model.predict(pil_image, generate_heatmap=generar_explicacion)
        
        result = {
            "resultado": ia_result["resultado"],
            "confianza": ia_result["confianza"],
            "probabilidades": ia_result["probabilidades"]
        }
        
        logger.info(f"✅ Re-análisis: {result['resultado']} ({result['confianza']}%)")
        
        # Generar explicación
        if generar_explicacion:
            explanation = generate_medical_explanation(
                predicted_class=result["resultado"],
                confidence=result["confianza"],
                combined_image=ia_result.get("heatmap")
            )
            result["explicacion_medica"] = explanation
        
        # Actualizar registro en BD
        await db.registros.update_one(
            {"_id": ObjectId(registro_id)},
            {
                "$set": {
                    "analisis.resultado": result["resultado"],
                    "analisis.aiSummary": result.get("explicacion_medica"),
                    "analisis.confianza": result["confianza"],
                    "resultado": result["resultado"],
                    "updatedAt": datetime.utcnow()
                }
            }
        )
        
        logger.info(f"✅ Registro actualizado: {registro_id}")
        
        return {
            "success": True,
            "analisis_actualizado": result,
            "mensaje": "Registro re-analizado exitosamente"
        }
        
    except Exception as e:
        logger.error(f"❌ Error re-analizando: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error re-analizando registro: {str(e)}"
        )


@router.get("/", response_model=List[RegistroResponse])
async def listar_registros(
    skip: int = 0,
    limit: int = 20,
    resultado: Optional[str] = None,
    buscar: Optional[str] = None,
    current_especialista: dict = Depends(get_current_active_especialista)
):
    """Listar registros del especialista autenticado"""
    db = get_database()
    especialista_id = current_especialista["_id"]
    
    query = {"especialistaId": especialista_id}
    
    if resultado and resultado in ["Anemia", "No Anemia"]:
        query["resultado"] = resultado
    
    if buscar:
        query["$or"] = [
            {"paciente.nombre": {"$regex": buscar, "$options": "i"}},
            {"numeroExpediente": {"$regex": buscar, "$options": "i"}}
        ]
    
    registros = await db.registros.find(query)\
        .sort("fechaAnalisis", -1)\
        .skip(skip)\
        .limit(limit)\
        .to_list(length=limit)
    
    for registro in registros:
        registro["_id"] = str(registro["_id"])
        registro["especialistaId"] = str(registro["especialistaId"])
    
    return registros


@router.get("/{registro_id}", response_model=RegistroResponse)
async def obtener_registro(
    registro_id: str,
    current_especialista: dict = Depends(get_current_active_especialista)
):
    """Obtener detalles de un registro específico"""
    db = get_database()
    
    if not ObjectId.is_valid(registro_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de registro inválido"
        )
    
    registro = await db.registros.find_one({
        "_id": ObjectId(registro_id),
        "especialistaId": current_especialista["_id"]
    })
    
    if not registro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro no encontrado"
        )
    
    registro["_id"] = str(registro["_id"])
    registro["especialistaId"] = str(registro["especialistaId"])
    
    return registro


@router.get("/expediente/{numero_expediente}", response_model=RegistroResponse)
async def obtener_registro_por_expediente(
    numero_expediente: str,
    current_especialista: dict = Depends(get_current_active_especialista)
):
    """Obtener registro por número de expediente"""
    db = get_database()
    
    registro = await db.registros.find_one({
        "numeroExpediente": numero_expediente,
        "especialistaId": current_especialista["_id"]
    })
    
    if not registro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro no encontrado"
        )
    
    registro["_id"] = str(registro["_id"])
    registro["especialistaId"] = str(registro["especialistaId"])
    
    return registro


@router.delete("/{registro_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_registro(
    registro_id: str,
    current_especialista: dict = Depends(get_current_active_especialista)
):
    """Eliminar un registro y sus archivos asociados"""
    db = get_database()
    
    if not ObjectId.is_valid(registro_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de registro inválido"
        )
    
    registro = await db.registros.find_one({
        "_id": ObjectId(registro_id),
        "especialistaId": current_especialista["_id"]
    })
    
    if not registro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro no encontrado"
        )
    
    # Eliminar de MongoDB
    result = await db.registros.delete_one({"_id": ObjectId(registro_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error eliminando registro"
        )
    
    # Eliminar archivos asociados
    if registro.get("imagenes", {}).get("rutaOriginal"):
        delete_file(registro["imagenes"]["rutaOriginal"])
    if registro.get("imagenes", {}).get("rutaMapaAtencion"):
        delete_file(registro["imagenes"]["rutaMapaAtencion"])
    
    logger.info(f"🗑️ Registro eliminado: {registro_id}")
    
    return None