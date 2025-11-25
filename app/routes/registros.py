from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form
from datetime import datetime
from typing import Optional, List
from bson import ObjectId

from app.db.models import RegistroResponse
from app.core.auth import get_current_active_especialista
from app.core.utils import save_uploaded_image, generate_numero_expediente, delete_file
from app.db.database import get_database

router = APIRouter(prefix="/registros", tags=["Registros"])


@router.post("/", response_model=RegistroResponse, status_code=status.HTTP_201_CREATED)
async def crear_registro(
    paciente_nombre: str = Form(...),
    paciente_edad: int = Form(...),
    paciente_sexo: str = Form(...),
    resultado: str = Form(...),
    ai_summary: Optional[str] = Form(None),
    numero_expediente: Optional[str] = Form(None),
    imagen_original: UploadFile = File(...),
    imagen_mapa: Optional[UploadFile] = File(None),
    current_especialista: dict = Depends(get_current_active_especialista)
):
    """Crear un nuevo registro de detección"""
    db = get_database()
    
    # Validar resultado
    if resultado not in ["Anemia", "No Anemia"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resultado debe ser 'Anemia' o 'No Anemia'"
        )
    
    # Validar sexo
    if paciente_sexo not in ["Masculino", "Femenino", "Otro"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sexo debe ser 'Masculino', 'Femenino' u 'Otro'"
        )
    
    # Generar número de expediente si no se proporciona
    if not numero_expediente:
        numero_expediente = generate_numero_expediente()
        
        # Verificar que sea único
        while await db.registros.find_one({"numeroExpediente": numero_expediente}):
            numero_expediente = generate_numero_expediente()
    else:
        # Verificar que no exista
        existing = await db.registros.find_one({"numeroExpediente": numero_expediente})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El número de expediente {numero_expediente} ya existe"
            )
    
    # Guardar imagen original
    try:
        ruta_original = await save_uploaded_image(
            imagen_original,
            numero_expediente,
            tipo="original"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error guardando imagen original: {str(e)}"
        )
    
    # Guardar mapa de atención si se proporciona
    ruta_mapa = None
    if imagen_mapa:
        try:
            ruta_mapa = await save_uploaded_image(
                imagen_mapa,
                numero_expediente,
                tipo="mapa_atencion"
            )
        except Exception as e:
            # Si falla, eliminar la imagen original
            delete_file(ruta_original)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error guardando mapa de atención: {str(e)}"
            )
    
    # Crear documento de registro
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
            "aiSummary": ai_summary  
        },
        "resultado": resultado,
        "fechaAnalisis": datetime.utcnow(), 
        "createdAt": datetime.utcnow(),  
        "updatedAt": datetime.utcnow()  
    }
    
    # Insertar en la base de datos
    result = await db.registros.insert_one(registro_doc)
    
    # Obtener el registro creado
    created_registro = await db.registros.find_one({"_id": result.inserted_id})
    
    # Convertir ObjectIds a strings
    created_registro["_id"] = str(created_registro["_id"])
    created_registro["especialistaId"] = str(created_registro["especialistaId"])
    
    return created_registro


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
    
    # Construir query
    query = {"especialistaId": especialista_id}
    
    # Filtro por resultado
    if resultado and resultado in ["Anemia", "No Anemia"]:
        query["resultado"] = resultado
    
    # Búsqueda por texto
    if buscar:
        query["$or"] = [
            {"paciente.nombre": {"$regex": buscar, "$options": "i"}},
            {"numeroExpediente": {"$regex": buscar, "$options": "i"}} 
        ]
    
    # Obtener registros
    registros = await db.registros.find(query)\
        .sort("fechaAnalisis", -1)\
        .skip(skip)\
        .limit(limit)\
        .to_list(length=limit)
    
    # Convertir ObjectIds a strings
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
    
    # Convertir ObjectIds a strings
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
    
    # Query con camelCase
    registro = await db.registros.find_one({
        "numeroExpediente": numero_expediente,
        "especialistaId": current_especialista["_id"]
    })
    
    if not registro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro no encontrado"
        )
    
    # Convertir ObjectIds a strings
    registro["_id"] = str(registro["_id"])
    registro["especialistaId"] = str(registro["especialistaId"])
    
    return registro


@router.delete("/{registro_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_registro(
    registro_id: str,
    current_especialista: dict = Depends(get_current_active_especialista)
):
    """Eliminar un registro"""
    db = get_database()
    
    # Validar ObjectId
    if not ObjectId.is_valid(registro_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de registro inválido"
        )
    
    # Verificar con camelCase
    registro = await db.registros.find_one({
        "_id": ObjectId(registro_id),
        "especialistaId": current_especialista["_id"]
    })
    
    if not registro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro no encontrado"
        )
    
    # Eliminar registro
    result = await db.registros.delete_one({"_id": ObjectId(registro_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error eliminando registro"
        )
    
    # Eliminar archivos 
    if registro.get("imagenes", {}).get("rutaOriginal"):
        delete_file(registro["imagenes"]["rutaOriginal"])
    if registro.get("imagenes", {}).get("rutaMapaAtencion"):
        delete_file(registro["imagenes"]["rutaMapaAtencion"])
    
    return None