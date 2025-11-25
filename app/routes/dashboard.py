from fastapi import APIRouter, Depends
from datetime import datetime, timedelta
from typing import Dict, List

from app.core.auth import get_current_active_especialista
from app.db.database import get_database
from collections import defaultdict

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/estadisticas")
async def obtener_estadisticas_dashboard(
    current_especialista: dict = Depends(get_current_active_especialista)
):
    """
    Obtener estadísticas para el dashboard principal
    """
    db = get_database()
    especialista_id = current_especialista["_id"]
    
    # Fechas para filtros
    hoy_inicio = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    hoy_fin = hoy_inicio + timedelta(days=1)
    
    semana_inicio = hoy_inicio - timedelta(days=7)
    
    # 1. Detecciones hoy
    detecciones_hoy = await db.registros.count_documents({
        "especialistaId": especialista_id,
        "fechaAnalisis": {"$gte": hoy_inicio, "$lt": hoy_fin}
    })
    
    # 2. Casos positivos (total)
    casos_positivos = await db.registros.count_documents({
        "especialistaId": especialista_id,
        "resultado": "Anemia"
    })
    
    # 3. Total de pacientes únicos (contando nombres únicos)
    # Nota: En producción, considera usar un campo de ID de paciente único
    pipeline_pacientes = [
        {"$match": {"especialistaId": especialista_id}},
        {"$group": {"_id": "$paciente.nombre"}},
        {"$count": "total"}
    ]
    result_pacientes = await db.registros.aggregate(pipeline_pacientes).to_list(length=1)
    total_pacientes = result_pacientes[0]["total"] if result_pacientes else 0
    
    # 4. Detecciones esta semana
    esta_semana = await db.registros.count_documents({
        "especialistaId": especialista_id,
        "fechaAnalisis": {"$gte": semana_inicio}
    })
    
    # 5. Distribución por edad
    distribucion_edad = await calcular_distribucion_edad(db, especialista_id)
    
    # 6. Resumen de detecciones
    total_registros = await db.registros.count_documents({
        "especialistaId": especialista_id
    })
    
    casos_negativos = await db.registros.count_documents({
        "especialistaId": especialista_id,
        "resultado": "No Anemia"
    })
    
    # 7. Confianza promedio (si tienes este dato)
    # Por ahora, usaremos un valor simulado basado en detecciones
    confianza_promedio = 90.0 if total_registros > 100 else 85.0
    
    # 8. Tasa de detección
    tasa_deteccion = round((casos_positivos / total_registros * 100) if total_registros > 0 else 0, 1)
    
    return {
        "detecciones_hoy": detecciones_hoy,
        "casos_positivos": casos_positivos,
        "total_pacientes": total_pacientes,
        "esta_semana": esta_semana,
        "distribucion_edad": distribucion_edad,
        "resumen_detecciones": {
            "total_casos": total_registros,
            "positivos": casos_positivos,
            "negativos": casos_negativos,
            "tasa_deteccion": tasa_deteccion
        },
        "confianza_promedio": confianza_promedio
    }


async def calcular_distribucion_edad(db, especialista_id):
    """
    Calcular distribución de casos por grupo de edad
    """
    # Pipeline de agregación para agrupar por rangos de edad
    pipeline = [
        {"$match": {"especialistaId": especialista_id}},
        {
            "$bucket": {
                "groupBy": "$paciente.edad",
                "boundaries": [0, 11, 21, 31, 41, 51, 61, 200],
                "default": "Otro",
                "output": {
                    "total": {"$sum": 1},
                    "positivos": {
                        "$sum": {
                            "$cond": [{"$eq": ["$resultado", "Anemia"]}, 1, 0]
                        }
                    }
                }
            }
        }
    ]
    
    resultados = await db.registros.aggregate(pipeline).to_list(length=10)
    
    # Mapear resultados a rangos legibles
    rangos_map = {
        0: "0-10",
        11: "11-20",
        21: "21-30",
        31: "31-40",
        41: "41-50",
        51: "51-60",
        61: "61+"
    }
    
    # Construir datos para el gráfico
    datos_grafico = []
    total_casos = 0
    total_positivos = 0
    mayor_grupo = {"rango": "", "total": 0}
    
    for resultado in resultados:
        rango = rangos_map.get(resultado["_id"], "Otro")
        total = resultado["total"]
        positivos = resultado["positivos"]
        
        datos_grafico.append({
            "rango": rango,
            "total": total,
            "positivos": positivos,
            "negativos": total - positivos
        })
        
        total_casos += total
        total_positivos += positivos
        
        if total > mayor_grupo["total"]:
            mayor_grupo = {"rango": rango, "total": total}
    
    return {
        "total_casos": total_casos,
        "positivos": total_positivos,
        "mayor_grupo": mayor_grupo["rango"] if mayor_grupo["rango"] else "N/A",
        "datos_grafico": sorted(datos_grafico, key=lambda x: x["rango"])
    }


@router.get("/actividad-reciente")
async def obtener_actividad_reciente(
    limit: int = 10,
    current_especialista: dict = Depends(get_current_active_especialista)
):
    """
    Obtener actividad reciente del especialista
    """
    db = get_database()
    especialista_id = current_especialista["_id"]
    
    # Obtener ultimos registros
    registros = await db.registros.find({
        "especialistaId": especialista_id
    }).sort("fechaAnalisis", -1).limit(limit).to_list(length=limit)
    
    # Formatear resultados
    actividad = []
    for registro in registros:
        actividad.append({
            "id": str(registro["_id"]),
            "numeroExpediente": registro["numeroExpediente"],
            "paciente": registro["paciente"]["nombre"],
            "resultado": registro["resultado"],
            "fecha": registro["fechaAnalisis"].isoformat()
        })
    
    return actividad


@router.get("/tendencias")
async def obtener_tendencias(
    dias: int = 30,
    current_especialista: dict = Depends(get_current_active_especialista)
):
    """
    Obtener tendencias de detecciones en los últimos N días
    """
    db = get_database()
    especialista_id = current_especialista["_id"]
    
    # Fecha de inicio
    fecha_inicio = datetime.utcnow() - timedelta(days=dias)
    
    # Pipeline de agregación por día
    pipeline = [
        {
            "$match": {
                "especialistaId": especialista_id,
                "fechaAnalisis": {"$gte": fecha_inicio}
            }
        },
        {
            "$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": "$fechaAnalisis"
                    }
                },
                "total": {"$sum": 1},
                "positivos": {
                    "$sum": {
                        "$cond": [{"$eq": ["$resultado", "Anemia"]}, 1, 0]
                    }
                },
                "negativos": {
                    "$sum": {
                        "$cond": [{"$eq": ["$resultado", "No Anemia"]}, 1, 0]
                    }
                }
            }
        },
        {"$sort": {"_id": 1}}
    ]
    
    resultados = await db.registros.aggregate(pipeline).to_list(length=dias)
    
    # Formatear para el frontend
    tendencias = []
    for resultado in resultados:
        tendencias.append({
            "fecha": resultado["_id"],
            "total": resultado["total"],
            "positivos": resultado["positivos"],
            "negativos": resultado["negativos"]
        })
    
    return tendencias