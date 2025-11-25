from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime
from bson import ObjectId

from app.db.models import EspecialistaResponse, EspecialistaUpdate
from app.core.auth import get_current_active_especialista
from app.db.database import get_database

router = APIRouter(prefix="/especialistas", tags=["Especialistas"])


@router.get("/perfil", response_model=EspecialistaResponse)
async def obtener_perfil(current_especialista: dict = Depends(get_current_active_especialista)):
    """Obtener perfil del especialista autenticado"""
    current_especialista["_id"] = str(current_especialista["_id"])
    return EspecialistaResponse(**current_especialista)


@router.put("/perfil", response_model=EspecialistaResponse)
async def actualizar_perfil(
    update_data: EspecialistaUpdate,
    current_especialista: dict = Depends(get_current_active_especialista)
):
    """Actualizar perfil del especialista autenticado"""
    db = get_database()
    
    # Preparar datos para actualizar (solo campos que no son None)
    update_dict = {k: v for k, v in update_data.dict(exclude_unset=True).items() if v is not None}
    
    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay campos para actualizar"
        )
    
    # Agregar timestamp de actualización
    update_dict["updatedAt"] = datetime.utcnow()
    
    # Actualizar en la base de datos
    result = await db.especialistas.update_one(
        {"_id": current_especialista["_id"]},
        {"$set": update_dict}
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se realizaron cambios"
        )
    
    # Obtener especialista actualizado
    updated_especialista = await db.especialistas.find_one(
        {"_id": current_especialista["_id"]}
    )
    
    updated_especialista["_id"] = str(updated_especialista["_id"])
    return EspecialistaResponse(**updated_especialista)


@router.get("/estadisticas")
async def obtener_estadisticas_especialista(
    current_especialista: dict = Depends(get_current_active_especialista)
):
    """Obtener estadísticas del especialista"""
    db = get_database()
    especialista_id = current_especialista["_id"]
    
    # Total de análisis realizados
    total_analisis = await db.registros.count_documents(
        {"especialistaId": especialista_id}
    )
    
    # Análisis positivos
    positivos = await db.registros.count_documents(
        {"especialistaId": especialista_id, "resultado": "Anemia"}
    )
    
    # Análisis negativos
    negativos = await db.registros.count_documents(
        {"especialistaId": especialista_id, "resultado": "No Anemia"}
    )
    
    # Últimos 5 análisis
    ultimos_analisis = await db.registros.find(
        {"especialistaId": especialista_id}
    ).sort("fechaAnalisis", -1).limit(5).to_list(length=5)
    
    # Convertir ObjectIds a strings
    for analisis in ultimos_analisis:
        analisis["_id"] = str(analisis["_id"])
        analisis["especialistaId"] = str(analisis["especialistaId"])
    
    return {
        "total_analisis": total_analisis,
        "positivos": positivos,
        "negativos": negativos,
        "tasa_positividad": round((positivos / total_analisis * 100) if total_analisis > 0 else 0, 2),
        "ultimos_analisis": ultimos_analisis
    }