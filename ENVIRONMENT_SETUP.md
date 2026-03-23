# Configuración de Ambientes Multi-Ambiente

Este documento explica cómo configurar y ejecutar el proyecto en diferentes ambientes (desarrollo, staging, producción, testing).

## Estructura de Configuración

El proyecto utiliza un sistema de configuración multi-ambiente basado en la variable de entorno `FLASK_ENV`:

```
config.py
├── Config (Clase base)
├── DevelopmentConfig
├── StagingConfig
├── ProductionConfig
└── TestingConfig
```

## Ambientes Disponibles

### 1. **Development** (Desarrollo Local)
- **FLASK_ENV:** `development`
- **Base de Datos:** SQLite local (`instance/dev.db`)
- **Debug:** Activado
- **Caché:** Deshabilitado
- **Ideal para:** Desarrollo local y debugging

### 2. **Staging** (Pre-producción)
- **FLASK_ENV:** `staging`
- **Base de Datos:** PostgreSQL (requiere `DATABASE_URL`)
- **Debug:** Desactivado
- **Caché:** Habilitado con Redis
- **Ideal para:** Testing antes de producción

### 3. **Production** (Producción)
- **FLASK_ENV:** `production`
- **Base de Datos:** PostgreSQL (requiere `DATABASE_URL`)
- **Debug:** Desactivado
- **Caché:** Habilitado y optimizado con Redis
- **Seguridad:** Máxima (cookies seguras, HTTPS recomendado)
- **Ideal para:** Ambiente en vivo

### 4. **Testing** (Tests Automatizados)
- **FLASK_ENV:** `testing`
- **Base de Datos:** SQLite en memoria
- **Debug:** Desactivado
- **Caché:** Deshabilitado
- **Ideal para:** Ejecutar pruebas automatizadas

## Configuración Inicial

### Entorno Python recomendado para este proyecto

- Este proyecto usa **conda** y no `.venv`.
- Nombre de entorno estándar: `bookkeeply`.

```bash
conda create -y -n bookkeeply python=3.12
conda activate bookkeeply
pip install -r requirements.txt
```

### 1. Crear archivo .env.local

```bash
cp .env.example .env.local
```

Edita `.env.local` con tus valores locales:

```bash
FLASK_ENV=development
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
SECRET_KEY=tu-clave-secreta-local
# DATABASE_URL= (dejar en blanco para usar SQLite)
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
LOG_LEVEL=DEBUG
```

### 2. Cargar variables de entorno

#### Opción A: Fish Shell (recomendado para tu setup)

```fish
source load_env.fish
```

#### Opción B: Bash Shell

```bash
source load_env.sh
```

#### Opción C: Directo en la terminal

```fish
set -x FLASK_ENV development
set -x FLASK_HOST 0.0.0.0
set -x FLASK_PORT 5000
```

### 3. Verificar configuración

```bash
python -m app
```

O más fácil:

```bash
python run.py
```

Deberías ver algo como:

```
✅ Variables de entorno cargadas
FLASK_ENV: development
FLASK_HOST: 0.0.0.0
FLASK_PORT: 5000

 * Running on http://0.0.0.0:5000
```

## Instalación de Dependencias

### Desarrollo Local

```bash
pip install -r requirements.txt
pip install redis celery pytest pytest-flask python-dotenv
```

### Con todas las herramientas recomendadas

```bash
pip install -r requirements.txt redis celery pytest pytest-flask python-dotenv pylint black
```

## Variables de Entorno

### Requeridas por Ambiente

| Variable | Development | Staging | Production | Testing |
|----------|-------------|---------|-----------|---------|
| `FLASK_ENV` | ✅ dev | ✅ staging | ✅ prod | ✅ testing |
| `SECRET_KEY` | Opcional | ✅ Requerido | ✅ Requerido | ✅ Generado |
| `DATABASE_URL` | Opcional | ✅ Requerido | ✅ Requerido | ✅ Memory |
| `REDIS_URL` | Opcional | Opcional | Opcional | Opcional |
| `CELERY_BROKER_URL` | Opcional | Opcional | Opcional | N/A |

### Variables Opcionales

```bash
FLASK_HOST=0.0.0.0           # Host por defecto
FLASK_PORT=5000              # Puerto por defecto
LOG_LEVEL=INFO               # Nivel de logging
```

## Ejemplos de Uso

### Run Development

```bash
source load_env.fish
python run.py
```

### Run Staging

```bash
export FLASK_ENV=staging
export DATABASE_URL=postgresql://user:pass@localhost/bookkeeply_staging
export SECRET_KEY=staging-secret-key-123
export REDIS_URL=redis://localhost:6379/0

python run.py
```

### Run Production

Usa systemd/supervisord en servidor:

```ini
[program:bookkeeply]
command=/path/to/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 run:app
directory=/path/to/bookkeeply
environment=FLASK_ENV=production,DATABASE_URL=...,SECRET_KEY=...
autostart=true
autorestart=true
```

### Run Tests

```bash
export FLASK_ENV=testing
pytest tests/
```

## Migraciones de Base de Datos

Las migraciones se ejecutan automáticamente según el ambiente:

### Development

```bash
source load_env.fish
flask db init          # Primera vez
flask db migrate       # Crear nueva migración
flask db upgrade       # Aplicar migraciones
```

### Production

```bash
export FLASK_ENV=production
flask db upgrade       # Solo applicar, no crear nuevas
```

## Redis (Caché y Celery)

### Desarrollo Local

```bash
# Instalar Redis (Linux)
sudo apt-get install redis-server

# O con Docker
docker run -d -p 6379:6379 redis:latest

# Iniciar Redis
redis-server

# Verificar conexión
redis-cli ping
# Output: PONG
```

### Staging/Production

Usa Redis gestionado:
- AWS ElastiCache
- Azure Cache for Redis
- Heroku Redis
- DigitalOcean Managed Databases

## Checklist para Deployment

- [ ] Variables de entorno configuradas en el servidor
- [ ] Base de datos PostgreSQL creada
- [ ] Redis disponible
- [ ] SECRET_KEY generada y configurada
- [ ] DATABASE_URL apunta a base de datos correcta
- [ ] Migraciones ejecutadas (`flask db upgrade`)
- [ ] Static files compilados (`tailwindcss build`)
- [ ] HTTPS configurado
- [ ] Logging centralizado (opcional)
- [ ] Backups configurados

## Troubleshooting

### "SECRET_KEY must be set in production environment"

```bash
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
echo $SECRET_KEY
# Guardar este valor en tus variables de entorno
```

### "DATABASE_URL must be set in staging/production"

```bash
export DATABASE_URL=postgresql://user:password@localhost:5432/bookkeeply
```

### Redis connection refused

```bash
# Verificar que Redis está ejecutándose
redis-cli ping

# O iniciar con Docker
docker run -d -p 6379:6379 redis:latest
```

### El archivo .env.local no se carga

```bash
# Asegúrate de estar en el directorio raíz del proyecto
pwd
# Output: /home/jravalug/devcode/bookkeeply

# Verifica que el archivo existe
ls -la .env.local
```

## Referencias

- [Flask Configurations](https://flask.palletsprojects.com/en/2.3.x/config/)
- [Python-dotenv](https://github.com/theskumar/python-dotenv)
- [Redis](https://redis.io/)
- [Celery](https://docs.celeryproject.io/)
