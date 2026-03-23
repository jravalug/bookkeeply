import os
from pathlib import Path

# Directorio raiz del proyecto
BASE_DIR = Path(__file__).parent


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Configuración base compartida por todos los ambientes"""

    # Seguridad y sesiones
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False

    # Sesiones
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 604800  # 7 días

    # Variables que deben ser sobrescritas en subclases
    SECRET_KEY = None
    SQLALCHEMY_DATABASE_URI = None
    DEBUG = False
    TESTING = False
    ENV = None

    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_DIR = str(BASE_DIR / "logs")
    LOG_FILE = os.environ.get("LOG_FILE", "bookkeeply.log")
    LOG_MAX_BYTES = int(os.environ.get("LOG_MAX_BYTES", 5 * 1024 * 1024))
    LOG_BACKUP_COUNT = int(os.environ.get("LOG_BACKUP_COUNT", 5))

    # Reglas de contabilidad por cliente
    ACCOUNTING_FISCAL_THRESHOLD = float(
        os.environ.get("ACCOUNTING_FISCAL_THRESHOLD", 500000)
    )
    ACCOUNTING_REGIME_ALLOW_REVERSION = _get_bool_env(
        "ACCOUNTING_REGIME_ALLOW_REVERSION", True
    )
    ACCOUNTING_REGIME_AUTO_UPDATE = _get_bool_env("ACCOUNTING_REGIME_AUTO_UPDATE", True)
    ACCOUNTING_REGIME_AUTO_UPDATE_MONTH = int(
        os.environ.get("ACCOUNTING_REGIME_AUTO_UPDATE_MONTH", 1)
    )


def _resolve_database_url(env_key: str) -> str:
    """Resuelve URL de DB por entorno con fallback a DATABASE_URL."""
    specific = os.environ.get(env_key)
    generic = os.environ.get("DATABASE_URL")
    return specific or generic or ""


class DevConfig(Config):
    """Configuracion para desarrollo local con PostgreSQL."""

    ENV = "dev"
    DEBUG = True
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG")
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"
    SQLALCHEMY_DATABASE_URI = _resolve_database_url("DATABASE_URL_DEV")
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }

    # Caché deshabilitado en desarrollo
    CACHE_TYPE = "simple"
    CACHE_DEFAULT_TIMEOUT = 0

    # Redis para desarrollo local
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # Celery
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND = os.environ.get(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379/2"
    )


class ProductionConfig(Config):
    """Configuracion para produccion con PostgreSQL."""

    ENV = "prod"
    DEBUG = False
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _resolve_database_url("DATABASE_URL_PROD")
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }

    # Caché habilitado y optimizado
    CACHE_TYPE = "redis"
    CACHE_REDIS_URL = os.environ.get("REDIS_URL")
    CACHE_DEFAULT_TIMEOUT = 600

    # Redis
    REDIS_URL = os.environ.get("REDIS_URL")

    # Celery
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND")

    # Seguridad extra para producción
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True


class TestingConfig(Config):
    """Configuracion para tests con PostgreSQL."""

    ENV = "test"
    TESTING = True
    DEBUG = False
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = _resolve_database_url("DATABASE_URL_TEST")
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }

    # Sin caché en tests
    CACHE_TYPE = "null"
    CACHE_DEFAULT_TIMEOUT = 0

    # Redis mock
    REDIS_URL = "redis://localhost:6379/15"


# Mapeo de ambientes a clases de configuración
config_by_env = {
    "dev": DevConfig,
    "test": TestingConfig,
    "prod": ProductionConfig,
}


def get_config(env=None):
    """
    Obtiene la configuración según el ambiente.

    Args:
        env (str): Nombre del ambiente. Si no se proporciona, usa FLASK_ENV

    Returns:
        Config: Clase de configuración apropiada
    """
    if env is None:
        env = os.environ.get("FLASK_ENV", "dev")

    config_class = config_by_env.get(env)
    if config_class is None:
        raise ValueError(
            f"Unknown environment: {env}. "
            f"Must be one of: {', '.join(config_by_env.keys())}"
        )
    required_db_env = {
        "dev": "DATABASE_URL_DEV",
        "test": "DATABASE_URL_TEST",
        "prod": "DATABASE_URL_PROD",
    }
    db_key = required_db_env[env]
    if not (os.environ.get(db_key) or os.environ.get("DATABASE_URL")):
        raise ValueError(
            f"{db_key} (o DATABASE_URL) debe estar configurada para el entorno {env}."
        )

    if env == "prod" and not os.environ.get("SECRET_KEY"):
        raise ValueError("SECRET_KEY must be set in prod environment")

    return config_class
