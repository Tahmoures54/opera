import os
import urllib.parse as _up

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _is_serverless():
    """تشخیص اجرا روی Vercel / AWS Lambda و محیط‌های serverless مشابه."""
    return bool(
        os.getenv('VERCEL')
        or os.getenv('VERCEL_ENV')
        or os.getenv('AWS_LAMBDA_FUNCTION_NAME')
    )


def _get_instance_dir():
    """
    مسیر پوشه instance:
    - اگر INSTANCE_DIR تنظیم شده باشد، از همان استفاده می‌شود.
    - روی Vercel/Lambda فقط /tmp قابل نوشتن است.
    - در لوکال، پوشه instance کنار پروژه ساخته می‌شود.
    """
    custom_dir = os.getenv('INSTANCE_DIR')
    if custom_dir:
        return os.path.abspath(custom_dir)

    if _is_serverless():
        return '/tmp/instance'  # nosec B108  # On Vercel/Lambda /tmp is the only writable location

    return os.path.join(BASE_DIR, 'instance')


def _get_bool_env(name, default=False):
    """تبدیل متغیر محیطی رشته‌ای به boolean."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def _normalize_database_url(url):
    """
    نرمال‌سازی URL دیتابیس:
    - postgres://  -> postgresql://
    - حذف channel_binding که با بعضی درایورها سازگار نیست.
    """
    if not url:
        return url

    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)

    if 'channel_binding=' in url:
        parsed = _up.urlparse(url)
        query = _up.parse_qs(parsed.query)
        query.pop('channel_binding', None)
        new_query = _up.urlencode(query, doseq=True)
        parsed = parsed._replace(query=new_query)
        url = _up.urlunparse(parsed)

    return url


def _get_database_url():
    """
    Resolve PostgreSQL URLs using the same aliases as the Vercel migration script.

    Prefer the application's canonical URL, then Vercel/Neon-provided aliases.
    Non-pooling URLs are supported for deployments where pooled connections are
    unsuitable for schema migrations or the application runtime.
    """
    return (
        os.getenv('DATABASE_URL')
        or os.getenv('material_DATABASE_URL')
        or os.getenv('POSTGRES_URL')
        or os.getenv('material_POSTGRES_URL')
        or os.getenv('POSTGRES_PRISMA_URL')
        or os.getenv('POSTGRES_URL_NON_POOLING')
        or os.getenv('material_POSTGRES_URL_NON_POOLING')
    )


# ---------------------------------------------------------------------------
# Base Config
# ---------------------------------------------------------------------------

class Config:
    """Base configuration."""

    # Flask environment
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    IS_PRODUCTION = (
        FLASK_ENV.lower() == 'production'
        or os.getenv('VERCEL_ENV') == 'production'
    )

    # Secret key
    SECRET_KEY = os.getenv('SECRET_KEY')

    # Paths
    BASE_DIR = BASE_DIR
    INSTANCE_DIR = _get_instance_dir()
    os.makedirs(INSTANCE_DIR, exist_ok=True)

    # Database
    DATABASE_URL = _normalize_database_url(_get_database_url())
    if IS_PRODUCTION:
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL must be configured in production; SQLite is not permitted.")
        if not DATABASE_URL.startswith(("postgresql://", "postgresql+psycopg2://")):
            raise ValueError("Production database must be PostgreSQL.")
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    elif DATABASE_URL:
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        SQLALCHEMY_DATABASE_URI = (
            f'sqlite:///{os.path.join(INSTANCE_DIR, "opera.db")}'
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', '300')),
        'pool_size': int(os.getenv('DB_POOL_SIZE', '5')),
        'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', '10')),
        'pool_timeout': int(os.getenv('DB_POOL_TIMEOUT', '30')),
    }

    # Misc
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))
    OPERA_UPLOAD_DIR = os.getenv('OPERA_UPLOAD_DIR', os.path.join(INSTANCE_DIR, 'uploads'))
    IS_SERVERLESS = _is_serverless()
    OPERA_STORAGE_BACKEND = os.getenv('OPERA_STORAGE_BACKEND', 'local').strip().lower()
    OPERA_S3_BUCKET = os.getenv('OPERA_S3_BUCKET')
    OPERA_S3_REGION = os.getenv('OPERA_S3_REGION', os.getenv('AWS_REGION', 'us-east-1'))
    OPERA_S3_ENDPOINT_URL = os.getenv('OPERA_S3_ENDPOINT_URL')
    OPERA_S3_ACCESS_KEY_ID = os.getenv('OPERA_S3_ACCESS_KEY_ID')
    OPERA_S3_SECRET_ACCESS_KEY = os.getenv('OPERA_S3_SECRET_ACCESS_KEY')
    OPERA_S3_PREFIX = os.getenv('OPERA_S3_PREFIX', 'opera-evidence')
    JSON_SORT_KEYS = False
    PREFERRED_URL_SCHEME = os.getenv(
        'PREFERRED_URL_SCHEME',
        'https' if IS_PRODUCTION else 'http'
    )

    # CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    WTF_CSRF_CHECK_DEFAULT = True

    # Session / cookies
    SESSION_COOKIE_SECURE = _get_bool_env('SESSION_COOKIE_SECURE', IS_PRODUCTION)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    REMEMBER_COOKIE_SAMESITE = SESSION_COOKIE_SAMESITE

    # Rate limiting
    # Keep route-specific protections enabled. Without an external store, counters
    # are local to each serverless instance and are not shared across Vercel instances.
    # This is a deliberate low-traffic fallback; set RATELIMIT_STORAGE_URI to Redis
    # later when globally shared limits are required.
    RATELIMIT_ENABLED = _get_bool_env('RATELIMIT_ENABLED', True)
    RATELIMIT_STORAGE_URI = os.getenv('RATELIMIT_STORAGE_URI', 'memory://')
    RATELIMIT_DEFAULT = os.getenv('RATELIMIT_DEFAULT', '300 per minute')
    RATELIMIT_HEADERS_ENABLED = True

    # Security
    WTF_CSRF_SSL_STRICT = IS_PRODUCTION
    SESSION_COOKIE_NAME = os.getenv('SESSION_COOKIE_NAME', 'opera_session')

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    SQLALCHEMY_ECHO = False


# ---------------------------------------------------------------------------
# Environment-specific configs
# ---------------------------------------------------------------------------

class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True

    @classmethod
    def validate(cls):
        """Validate mandatory production secrets and database settings."""
        secret_key = os.getenv('SECRET_KEY')
        if not secret_key:
            raise ValueError("SECRET_KEY must be provided by the environment.")
        if len(secret_key.encode("utf-8")) < 32:
            raise ValueError("SECRET_KEY must contain at least 32 bytes.")

        database_url = cls.SQLALCHEMY_DATABASE_URI or ''
        if not database_url.startswith(("postgresql://", "postgresql+psycopg2://")):
            raise ValueError("Production database must be PostgreSQL.")

        storage_backend = str(cls.OPERA_STORAGE_BACKEND or "").lower()
        if storage_backend not in {"local", "s3"}:
            raise ValueError("OPERA_STORAGE_BACKEND must be either local or s3.")
        if storage_backend == "s3" and not cls.OPERA_S3_BUCKET:
            raise ValueError("OPERA_S3_BUCKET is required when OPERA_STORAGE_BACKEND=s3.")



class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'opera-test-secret'  # nosec B105  # Test-only configuration
    SQLALCHEMY_DATABASE_URI = (
        'sqlite:///' + os.path.join(Config.INSTANCE_DIR, 'test.db')
    )
    SESSION_COOKIE_SECURE = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}
