#!/usr/bin/env fish
# load_env.fish - Carga variables de entorno para el proyecto
# Uso: source load_env.fish

# Detectar si el archivo .env.local existe
if test -f .env.local
    echo "Cargando variables desde .env.local..."
    set -l env_file .env.local
else if test -f .env
    echo "Cargando variables desde .env..."
    set -l env_file .env
else
    echo "⚠️  No se encontró .env.local o .env"
    echo "Por favor, copia .env.example a .env.local: cp .env.example .env.local"
    return 1
end

# Cargar cada línea del archivo .env
for line in (cat $env_file)
    # Ignorar líneas vacías y comentarios
    if test -n "$line"; and not string match -q '#*' $line
        # Exportar la variable
        set --export (string split -m1 '=' $line)
    end
end

echo "✅ Variables de entorno cargadas"
echo "FLASK_ENV: $FLASK_ENV"
echo "FLASK_HOST: $FLASK_HOST"
echo "FLASK_PORT: $FLASK_PORT"
echo "DATABASE_URL_DEV: $DATABASE_URL_DEV"
