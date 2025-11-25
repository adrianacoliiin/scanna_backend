from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, Literal
from datetime import datetime
from bson import ObjectId

# Helper para ObjectId
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


# ============================================
# MODELOS DE ESPECIALISTAS
# ============================================

class EspecialistaCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    apellido: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    area: Literal["Medicina General", "Hematología", "Medicina Interna", "Pediatría", "Ginecología", "Otro"]
    cedula_profesional: Optional[str] = Field(None, alias="cedulaProfesional")
    hospital: Optional[str] = None
    telefono: Optional[str] = None

class EspecialistaLogin(BaseModel):
    email: EmailStr
    password: str

class EspecialistaUpdate(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    telefono: Optional[str] = None
    hospital: Optional[str] = None
    area: Optional[Literal["Medicina General", "Hematología", "Medicina Interna", "Pediatría", "Ginecología", "Otro"]] = None

class EspecialistaResponse(BaseModel):
    id: str = Field(alias="_id")
    nombre: str
    apellido: str
    email: EmailStr
    area: str
    cedula_profesional: Optional[str] = Field(None, alias="cedulaProfesional")
    hospital: Optional[str] = None
    telefono: Optional[str] = None
    activo: bool
    fecha_registro: datetime = Field(alias="fechaRegistro")
    ultimo_acceso: Optional[datetime] = Field(None, alias="ultimoAcceso")

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


# ============================================
# MODELOS DE PACIENTES Y REGISTROS
# ============================================

class PacienteData(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=200)
    edad: int = Field(..., ge=0, le=150)
    sexo: Literal["Masculino", "Femenino", "Otro"]

class ImagenesData(BaseModel):
    """
    Modelo para datos de imágenes
    Usa alias para mapear entre snake_case (Python) y camelCase (MongoDB)
    """
    ruta_original: str = Field(..., alias="rutaOriginal")
    ruta_mapa_atencion: Optional[str] = Field(None, alias="rutaMapaAtencion")
    
    class Config:
        populate_by_name = True

class AnalisisData(BaseModel):
    """
    Modelo para datos de análisis
    Usa alias para mapear entre snake_case (Python) y camelCase (MongoDB)
    """
    resultado: Literal["Anemia", "No Anemia"]
    ai_summary: Optional[str] = Field(None, alias="aiSummary")
    
    class Config:
        populate_by_name = True

class RegistroCreate(BaseModel):
    paciente: PacienteData
    numero_expediente: Optional[str] = Field(None, alias="numeroExpediente")
    
    class Config:
        populate_by_name = True
    
class RegistroResponse(BaseModel):
    """
    Modelo de respuesta para registros
    Usa alias para mapear entre snake_case (Python) y camelCase (MongoDB)
    """
    id: str = Field(alias="_id")
    numero_expediente: str = Field(alias="numeroExpediente")
    paciente: PacienteData
    especialista_id: str = Field(alias="especialistaId")
    imagenes: ImagenesData
    analisis: AnalisisData
    resultado: str
    fecha_analisis: datetime = Field(alias="fechaAnalisis")

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


# ============================================
# MODELOS DE AUTENTICACIÓN
# ============================================

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    especialista: EspecialistaResponse

class TokenData(BaseModel):
    email: Optional[str] = None


# ============================================
# MODELOS DE DASHBOARD
# ============================================

class DashboardStats(BaseModel):
    detecciones_hoy: int
    casos_positivos: int
    total_pacientes: int
    esta_semana: int
    distribucion_edad: dict
    resumen_detecciones: dict
    confianza_promedio: float

class DistribucionEdad(BaseModel):
    total_casos: int
    positivos: int
    mayor_grupo: str
    datos_grafico: list