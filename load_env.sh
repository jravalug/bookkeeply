#!/bin/bash
# load_env.sh - Carga variables de entorno para el proyecto
# Uso: source load_env.sh

# Detectar si el archivo .env.local existe
if [ -f .env.local ]; then
    echo "Cargando variables desde .env.local..."
    ENV_FILE=.env.local
elif [ -f .env ]; then
    echo "Cargando variables desde .env..."
    ENV_FILE=.env
else
    echo "⚠️  No se encontró .env.local o .env"
    echo "Por favor, copia .env.example a .env.local: cp .env.example .env.local"
    return 1 2>/dev/null || exit 1
fi

# Cargar cada línea del archivo .env
if [ -f "$ENV_FILE" ]; then
    set -a  # Exportar todas las variables
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
fi

echo "✅ Variables de entorno cargadas"
echo "FLASK_ENV: $FLASK_ENV"
echo "FLASK_HOST: $FLASK_HOST"
echo "FLASK_PORT: $FLASK_PORT"
echo "DATABASE_URL_DEV: $DATABASE_URL_DEV"
