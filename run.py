#!/usr/bin/env python3
"""
SCANNA Backend - Script de inicio
Ejecutar este archivo para iniciar el servidor
"""

import uvicorn
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 SCANNA Backend - Iniciando servidor...")
    print("=" * 60)
    print()
    print("📍 URL: http://localhost:8000")
    print("📚 Documentación: http://localhost:8000/docs")
    print("🔧 Health Check: http://localhost:8000/health")
    print()
    print("Presiona Ctrl+C para detener el servidor")
    print("=" * 60)
    print()
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )