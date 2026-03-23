# Turso Integration for Bookkeeply

Este proyecto utiliza **Turso** con **Embedded Replicas** para desarrollo, proporcionando una experiencia de base de datos distribuida con funcionamiento offline-first puro.

## 🎯 Embedded Replicas - Desarrollo

**Base de datos local que funciona completamente offline** - Sincronización manual opcional con Turso cuando hay conexión.

### ¿Qué son las Embedded Replicas?

- ✅ **Base de datos local**: `instance/bookkeeply.db` (SQLite compatible)
- ✅ **Sincronización manual**: Opcional cuando hay conexión a internet
- ✅ **Lecturas instantáneas**: Consultas locales para máximo rendimiento
- ✅ **Escrituras locales**: Cambios se almacenan localmente
- ✅ **Offline-first puro**: Funciona completamente sin conexión a internet

## 🏗️ Arquitectura Actual

```
Local (bookkeeply.db)     Turso Server
     ↑                        ↑
   Lecturas/              Sincronización
   Escrituras             manual (opcional)
   locales               cuando online
```

**Offline-First Puro**: La aplicación funciona completamente sin conexión. La sincronización con Turso es manual y opcional.

## ⚙️ Configuración

### Variables de Entorno Requeridas

Crea o actualiza tu archivo `.env.local`:

```bash
# Turso Database Configuration (REQUIRED for development)
TURSO_DATABASE_URL=libsql://your-database-name.turso.io
TURSO_AUTH_TOKEN=your-auth-token-here

# Flask Configuration
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
```

### Obtener Credenciales de Turso

```bash
# 1. Instalar Turso CLI
npm install -g @tursodatabase/turso-cli

# 2. Autenticarse
turso auth login

# 3. Crear base de datos
turso db create sale-manager

# 4. Obtener URL de la base de datos
turso db show sale-manager --url

# 5. Crear token de autenticación
turso db tokens create sale-manager
```

## 🚀 Uso en Desarrollo

### Inicio Automático

La aplicación detecta automáticamente las variables de Turso y configura Embedded Replica:

```bash
# Simplemente ejecuta (configura automáticamente Embedded Replica)
python run.py
```

### Verificación de Configuración

```bash
# Verificar que Turso esté configurado
python -c "from app import create_app; app = create_app(); print('✅ Turso configurado correctamente')"
```

### Logs de Sincronización

Al iniciar, verás logs como:
```
INFO:config:🔄 Development using Turso Embedded Replica: /path/to/instance/bookkeeply.db -> libsql://database.turso.io (offline-first - manual sync when needed)
INFO:app:🔧 Registered libsql dialect for Turso connections
```

## 📦 Dependencias Actualizadas

Asegúrate de tener instaladas las dependencias correctas:

```bash
# Dependencias principales
pip install libsql sqlalchemy-libsql

# Verificar instalación
python -c "import libsql; import sqlalchemy_libsql; print('✅ Dependencias instaladas')"
```

## 🔧 Configuración Técnica

### Archivo de Configuración (`config.py`)

```python
class DevelopmentConfig(Config):
    def __init__(self):
        super().__init__()
        # Requiere Turso - no hay fallback a SQLite local
        turso_url = os.environ.get("TURSO_DATABASE_URL")
        turso_token = os.environ.get("TURSO_AUTH_TOKEN")

        if not (turso_url and turso_token):
            raise ValueError("TURSO_DATABASE_URL y TURSO_AUTH_TOKEN requeridos")

        # Embedded Replica Configuration
        local_db_path = BASE_DIR / "instance" / LOCAL_DB_FILENAME
        self.SQLALCHEMY_DATABASE_URI = f"sqlite+libsql:///{local_db_path}"

        self.SQLALCHEMY_ENGINE_OPTIONS = {
            "connect_args": {
                "auth_token": turso_token,
                # sync_url removido para funcionamiento offline puro
                # Sin sync_interval para funcionamiento offline puro
            },
        }
```

### Registro de Dialecto (`app/__init__.py`)

El dialecto `libsql` se registra automáticamente cuando se detecta en el URI:

```python
def _register_libsql_dialect():
    try:
        import sqlalchemy_libsql
        from sqlalchemy.dialects import registry
        registry.register("libsql", "sqlalchemy_libsql", "SQLiteDialect_libsql")
        logger.info("🔧 Registered libsql dialect for Turso connections")
    except ImportError as e:
        raise RuntimeError("sqlalchemy-libsql is required for Turso connections")
```

## 🐛 Solución de Problemas

### Error: "TURSO_DATABASE_URL y TURSO_AUTH_TOKEN deben estar configurados"

**Solución**: Configura las variables de entorno en `.env.local`

### Error: "sqlalchemy-libsql not installed"

**Solución**:
```bash
pip install sqlalchemy-libsql libsql
```

### Error de Conexión

**Verificar configuración**:
```bash
python -c "
import os
print('TURSO_URL:', os.environ.get('TURSO_DATABASE_URL'))
print('TURSO_TOKEN exists:', bool(os.environ.get('TURSO_AUTH_TOKEN')))
"
```

### Sincronización No Funciona

- **Offline-first**: Funciona completamente sin conexión
- **Manual**: La sincronización se puede hacer cuando haya conexión
- **Opcional**: No es necesaria para el funcionamiento normal

### Sincronización Manual

Cuando tengas conexión a internet y quieras sincronizar los cambios con Turso:

```python
# En código Python (opcional)
from app.extensions import db

# Sincronización manual cuando haya conexión
# conn = db.engine.raw_connection()  # Obtener conexión libsql
# conn.sync()  # Sincronizar manualmente
```

### Modo Offline

La aplicación funciona completamente offline:

- ✅ **Sin conexión requerida**: Funciona sin internet
- ✅ **Datos locales**: Todas las operaciones usan la base local
- ✅ **Sincronización opcional**: Solo cuando hay conexión (manual)
- ✅ **Rendimiento**: Consultas instantáneas locales

## 📊 Beneficios de Embedded Replicas

- ✅ **Rendimiento**: Lecturas locales instantáneas
- ✅ **Concurrencia**: Múltiples conexiones simultáneas
- ✅ **Offline**: Funciona sin conexión a internet
- ✅ **Sincronización**: Cambios se propagan automáticamente
- ✅ **Escalabilidad**: Fácil de escalar horizontalmente
- ✅ **Compatibilidad**: Mantiene toda la funcionalidad existente

## 🔄 Migración desde Configuración Anterior

Si tenías una configuración anterior:

1. ✅ **Actualiza dependencias**: `pip install libsql sqlalchemy-libsql`
2. ✅ **Configura variables**: Asegura `TURSO_DATABASE_URL` y `TURSO_AUTH_TOKEN`
3. ✅ **Ejecuta aplicación**: `python run.py` (automáticamente usa Embedded Replica)
4. ✅ **Verifica**: Los datos existentes se sincronizarán automáticamente

## 📝 Notas Importantes

- **Offline-first**: Funciona completamente sin conexión a internet
- **Sincronización opcional**: Manual cuando hay conexión
- **Archivo local**: `instance/bookkeeply.db` se crea automáticamente
- **No sync automático**: Evita errores de conexión cuando está offline
- **Compatibilidad**: Todas las consultas SQL existentes funcionan sin cambios

---

**Estado**: ✅ Implementado y funcionando
**Última actualización**: Febrero 2026