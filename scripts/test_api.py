"""
Script de prueba para la API de SCANNA
Ejecutar después de iniciar el servidor: python main.py
"""

import requests
import json
from pathlib import Path

# Configuración
BASE_URL = "http://localhost:8000"
TEST_EMAIL = "test@scanna.com"
TEST_PASSWORD = "test123456"

# Variable global para almacenar el token
TOKEN = None


def print_response(response, title="Response"):
    """Imprimir respuesta formateada"""
    print(f"\n{'=' * 60}")
    print(f"{title}")
    print(f"{'=' * 60}")
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    except:
        print(f"Response: {response.text}")
    print(f"{'=' * 60}\n")


def test_health():
    """Test 1: Health check"""
    print("🔍 TEST 1: Health Check")
    response = requests.get(f"{BASE_URL}/health")
    print_response(response, "Health Check")
    return response.status_code == 200


def test_registro():
    """Test 2: Registro de especialista"""
    print("🔍 TEST 2: Registro de Especialista")
    
    data = {
        "nombre": "Ana",
        "apellido": "Martínez",
        "email": "ana@ejemplo.com",
        "password": "password123",
        "area": "Hematología",
        "cedula_profesional": "9876543",
        "hospital": "Hospital Central",
        "telefono": "+52 618 987 6543"
    }
    
    response = requests.post(f"{BASE_URL}/auth/registro", json=data)
    print_response(response, "Registro")
    return response.status_code in [200, 201, 400]  # 400 si ya existe


def test_login():
    """Test 3: Login"""
    global TOKEN
    
    print("🔍 TEST 3: Login")
    
    data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    response = requests.post(f"{BASE_URL}/auth/login", json=data)
    print_response(response, "Login")
    
    if response.status_code == 200:
        TOKEN = response.json().get("access_token")
        print(f"✅ Token obtenido: {TOKEN[:50]}...")
        return True
    
    return False


def test_perfil():
    """Test 4: Obtener perfil"""
    print("🔍 TEST 4: Obtener Perfil")
    
    if not TOKEN:
        print("❌ No hay token disponible")
        return False
    
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.get(f"{BASE_URL}/especialistas/perfil", headers=headers)
    print_response(response, "Perfil")
    return response.status_code == 200


def test_actualizar_perfil():
    """Test 5: Actualizar perfil"""
    print("🔍 TEST 5: Actualizar Perfil")
    
    if not TOKEN:
        print("❌ No hay token disponible")
        return False
    
    headers = {"Authorization": f"Bearer {TOKEN}"}
    data = {
        "telefono": "+52 618 111 2222",
        "hospital": "Hospital General Actualizado"
    }
    
    response = requests.put(f"{BASE_URL}/especialistas/perfil", json=data, headers=headers)
    print_response(response, "Actualizar Perfil")
    return response.status_code == 200


def test_dashboard_estadisticas():
    """Test 6: Estadísticas del dashboard"""
    print("🔍 TEST 6: Estadísticas Dashboard")
    
    if not TOKEN:
        print("❌ No hay token disponible")
        return False
    
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.get(f"{BASE_URL}/dashboard/estadisticas", headers=headers)
    print_response(response, "Estadísticas Dashboard")
    return response.status_code == 200


def test_crear_registro():
    """Test 7: Crear registro"""
    print("🔍 TEST 7: Crear Registro")
    
    if not TOKEN:
        print("❌ No hay token disponible")
        return False
    
    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    # Datos del formulario
    data = {
        "paciente_nombre": "María García",
        "paciente_edad": "35",
        "paciente_sexo": "Femenino",
        "resultado": "Anemia",
        "ai_summary": "Análisis detectó palidez significativa en la conjuntiva ocular..."
    }
    
    # Crear imagen de prueba (1x1 pixel PNG)
    import io
    from PIL import Image
    
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    files = {
        "imagen_original": ("test.png", img_bytes, "image/png")
    }
    
    response = requests.post(
        f"{BASE_URL}/registros/",
        data=data,
        files=files,
        headers=headers
    )
    print_response(response, "Crear Registro")
    return response.status_code in [200, 201]


def test_listar_registros():
    """Test 8: Listar registros"""
    print("🔍 TEST 8: Listar Registros")
    
    if not TOKEN:
        print("❌ No hay token disponible")
        return False
    
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.get(f"{BASE_URL}/registros/", headers=headers)
    print_response(response, "Listar Registros")
    return response.status_code == 200


def test_buscar_registros():
    """Test 9: Buscar registros"""
    print("🔍 TEST 9: Buscar Registros")
    
    if not TOKEN:
        print("❌ No hay token disponible")
        return False
    
    headers = {"Authorization": f"Bearer {TOKEN}"}
    params = {
        "buscar": "María",
        "resultado": "Anemia"
    }
    
    response = requests.get(f"{BASE_URL}/registros/", params=params, headers=headers)
    print_response(response, "Buscar Registros")
    return response.status_code == 200


def test_actividad_reciente():
    """Test 10: Actividad reciente"""
    print("🔍 TEST 10: Actividad Reciente")
    
    if not TOKEN:
        print("❌ No hay token disponible")
        return False
    
    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = requests.get(f"{BASE_URL}/dashboard/actividad-reciente", headers=headers)
    print_response(response, "Actividad Reciente")
    return response.status_code == 200


def run_all_tests():
    """Ejecutar todas las pruebas"""
    print("\n" + "=" * 60)
    print("🧪 INICIANDO PRUEBAS DE LA API SCANNA")
    print("=" * 60)
    
    tests = [
        ("Health Check", test_health),
        ("Registro", test_registro),
        ("Login", test_login),
        ("Perfil", test_perfil),
        ("Actualizar Perfil", test_actualizar_perfil),
        ("Dashboard Estadísticas", test_dashboard_estadisticas),
        ("Crear Registro", test_crear_registro),
        ("Listar Registros", test_listar_registros),
        ("Buscar Registros", test_buscar_registros),
        ("Actividad Reciente", test_actividad_reciente),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Error en {name}: {e}")
            results.append((name, False))
    
    # Resumen
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE PRUEBAS")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "-" * 60)
    print(f"Total: {len(results)} | Exitosas: {passed} | Fallidas: {failed}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    # Verificar que el servidor esté corriendo
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✅ Servidor detectado y en línea")
            run_all_tests()
        else:
            print("❌ El servidor no responde correctamente")
    except requests.exceptions.ConnectionError:
        print("❌ No se puede conectar al servidor")
        print("   Asegúrate de que el servidor esté corriendo: python main.py")