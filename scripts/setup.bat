@echo off
REM Script de configuración inicial para Portafolio IOL

echo 🚀 Configurando Portafolio IOL...

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python no encontrado. Instala Python 3.12+ primero.
    pause
    exit /b 1
)

REM Crear entorno virtual
echo 📦 Creando entorno virtual...
python -m venv venv

REM Activar entorno virtual
echo 🔧 Activando entorno virtual...
call venv\Scripts\activate

REM Instalar dependencias
echo 📚 Instalando dependencias...
pip install -r requirements/dev.txt

REM Configurar pre-commit
echo 🔒 Configurando pre-commit...
pre-commit install

REM Copiar .env
if not exist .env (
    echo 📋 Copiando .env.example a .env...
    copy .env.example .env
    echo ⚠️  Edita el archivo .env con tus credenciales IOL antes de continuar.
)

REM Crear migraciones
echo 🗃️  Creando migraciones...
python manage.py makemigrations

REM Ejecutar migraciones
echo 🗃️  Ejecutando migraciones...
python manage.py migrate

REM Crear superusuario
echo 👤 Creando superusuario...
python manage.py createsuperuser

echo ✅ Configuración completada!
echo.
echo 📝 Próximos pasos:
echo 1. Edita .env con tus credenciales reales
echo 2. Ejecuta: python manage.py runserver
echo 3. Visita: http://localhost:8000
echo 4. Sincroniza datos: python manage.py actualizar_iol

pause