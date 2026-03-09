#!/bin/bash
# Script de configuración inicial para Portafolio IOL

echo "🚀 Configurando Portafolio IOL..."

# Verificar Python
if ! command -v python &> /dev/null; then
    echo "❌ Python no encontrado. Instala Python 3.12+ primero."
    exit 1
fi

# Crear entorno virtual
echo "📦 Creando entorno virtual..."
python -m venv venv

# Activar entorno virtual
echo "🔧 Activando entorno virtual..."
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
echo "📚 Instalando dependencias..."
pip install -r requirements/dev.txt

# Configurar pre-commit
echo "🔒 Configurando pre-commit..."
pre-commit install

# Copiar .env
if [ ! -f .env ]; then
    echo "📋 Copiando .env.example a .env..."
    cp .env.example .env
    echo "⚠️  Edita el archivo .env con tus credenciales IOL antes de continuar."
fi

# Crear migraciones
echo "🗃️  Creando migraciones..."
python manage.py makemigrations

# Ejecutar migraciones
echo "🗃️  Ejecutando migraciones..."
python manage.py migrate

# Crear superusuario
echo "👤 Creando superusuario..."
python manage.py createsuperuser

echo "✅ Configuración completada!"
echo ""
echo "📝 Próximos pasos:"
echo "1. Edita .env con tus credenciales reales"
echo "2. Ejecuta: python manage.py runserver"
echo "3. Visita: http://localhost:8000"
echo "4. Sincroniza datos: python manage.py actualizar_iol"