from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # MongoDB
    mongodb_uri: str
    mongodb_db_name: str = "scanna"
    
    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # File Storage
    upload_folder: str = "./uploads"
    max_upload_size: int = 10485760  # 10MB
    
    # Google Gemini AI
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"  # Mismo modelo que Streamlit
    gemini_enabled: bool = True  # Habilitar/deshabilitar Gemini
    
    # AI Model
    ai_model_path: str = "best_model_vit.pth"
    ai_enabled: bool = True  # Habilitar/deshabilitar análisis con IA
    
    # CORS
    allowed_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()