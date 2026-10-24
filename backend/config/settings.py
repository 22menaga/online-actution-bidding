import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


DEBUG = env_bool("DEBUG", False)
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not DEBUG and (
    len(SECRET_KEY) < 50
    or len(set(SECRET_KEY)) < 5
    or SECRET_KEY.startswith("django-insecure-")
):
    raise ImproperlyConfigured(
        "Set SECRET_KEY to a unique, randomly generated value of at least 50 characters."
    )

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("Set ALLOWED_HOSTS before starting with DEBUG=False.")

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "corsheaders",
    "channels",
    "accounts",
    "products",
    "auctions",
    "bidding",
    "payments",
    "notifications",
    "messaging",
    "audit",
    "dashboard",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "config.security.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


def database_config():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        if not DEBUG:
            raise ImproperlyConfigured(
                "Set DATABASE_URL to PostgreSQL before starting with DEBUG=False."
            )
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.getenv("SQLITE_PATH") or BASE_DIR / "db.sqlite3",  # SQLITE_PATH lets tests/demos use a scratch database
            # Concurrent writers (requests + the auction clock) caused "database is locked" 500s with SQLite's defaults.
            # WAL lets readers and a writer overlap, IMMEDIATE takes the write lock up front (no failed read->write upgrade),
            # and the timeout makes a waiting writer queue up instead of erroring.
            "OPTIONS": {
                "timeout": 20,
                "transaction_mode": "IMMEDIATE",
                "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
            },
        }

    parsed_url = urlparse(database_url)
    if parsed_url.scheme not in {"postgres", "postgresql"} or not parsed_url.path.strip("/"):
        raise ImproperlyConfigured("DATABASE_URL must be a PostgreSQL URL with a database name.")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed_url.path.lstrip("/")),
        "USER": unquote(parsed_url.username or ""),
        "PASSWORD": unquote(parsed_url.password or ""),
        "HOST": parsed_url.hostname or "",
        "PORT": parsed_url.port or 5432,
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"connect_timeout": 5},
    }


DATABASES = {"default": database_config()}
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/1")
USE_INMEMORY_CHANNELS = env_bool("USE_INMEMORY_CHANNELS", False)
if USE_INMEMORY_CHANNELS:
    # Local development without Redis (single process only).
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
if USE_INMEMORY_CHANNELS:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/2")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/3")
CELERY_BEAT_SCHEDULE = {
    "auction-lifecycle-every-10-seconds": {
        "task": "auctions.tasks.process_auction_lifecycle",
        "schedule": 10.0,
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "60/min", "user": "240/min", "resend_verification": "5/hour", "ai_estimate": "15/hour",
                               "login": "20/min", "bid": "40/min", "bid_auction": "15/min"},
}

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not DEBUG)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", not DEBUG)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", not DEBUG)

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@example.com")
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))

# Razorpay (https://dashboard.razorpay.com/app/keys). Keep the secret in the environment, never in source control.
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
PAYMENT_CURRENCY = os.getenv("PAYMENT_CURRENCY", "INR").upper()
PAYMENTS_MOCK = env_bool("PAYMENTS_MOCK", DEBUG and not os.getenv("RAZORPAY_KEY_SECRET"))  # test-mode checkout, never on in production
# AI price estimates from photos (Claude vision). Without a key the feature is simply switched off.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_VALUATION_MODEL = os.getenv("AI_VALUATION_MODEL", "claude-opus-5-5")

# ---- authentication hardening
from datetime import timedelta as _td  # noqa: E402

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": _td(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "15"))),  # short: the SPA refreshes silently
    "REFRESH_TOKEN_LIFETIME": _td(days=int(os.getenv("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,        # every refresh issues a new refresh token ...
    "BLACKLIST_AFTER_ROTATION": True,     # ... and revokes the old one, so a stolen copy dies on first reuse
    "UPDATE_LAST_LOGIN": True,            # admins see when people last signed in
}
LOGIN_LOCK_THRESHOLD = int(os.getenv("LOGIN_LOCK_THRESHOLD", "5"))
LOGIN_LOCK_MINUTES = int(os.getenv("LOGIN_LOCK_MINUTES", "15"))
BID_LARGE_MULTIPLIER = int(os.getenv("BID_LARGE_MULTIPLIER", "10"))  # a bid above Nx the current price must be explicitly confirmed
WS_MAX_CONNECTIONS_PER_USER = int(os.getenv("WS_MAX_CONNECTIONS_PER_USER", "10"))

# Local development has no real inbox, so new accounts are verified immediately. Never on in production (DEBUG=False).
AUTO_VERIFY_EMAIL = env_bool("AUTO_VERIFY_EMAIL", DEBUG)
# Fake (test) payments: a no-money option next to Razorpay so the whole flow can be tried. Never on in production.
FAKE_PAYMENTS_ENABLED = env_bool("FAKE_PAYMENTS_ENABLED", DEBUG)
# In-app coin wallet. 1 coin = COIN_VALUE rupees. Platform fee is taken from the seller's credit when an invoice is paid with coins.
COIN_VALUE = float(os.getenv("COIN_VALUE", "1"))
COIN_TOPUP_MIN = int(os.getenv("COIN_TOPUP_MIN", "10"))
COIN_TOPUP_MAX = int(os.getenv("COIN_TOPUP_MAX", "100000"))
PLATFORM_FEE_PERCENT = float(os.getenv("PLATFORM_FEE_PERCENT", "0"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
# Admin-controlled scheduling: sellers/buyers only *request* times, the admin allocates them within these limits.
AUCTION_MIN_DURATION_MINUTES = int(os.getenv("AUCTION_MIN_DURATION_MINUTES", "10"))
AUCTION_MAX_DURATION_DAYS = int(os.getenv("AUCTION_MAX_DURATION_DAYS", "30"))
AUCTION_MAX_CONCURRENT = int(os.getenv("AUCTION_MAX_CONCURRENT", "100"))  # simultaneous live/scheduled auctions in one window
ANTI_SNIPE_WINDOW_SECONDS = int(os.getenv("ANTI_SNIPE_WINDOW_SECONDS", "120"))
ANTI_SNIPE_EXTENSION_SECONDS = int(os.getenv("ANTI_SNIPE_EXTENSION_SECONDS", "120"))

LOGIN_URL = "/login/"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        }
    },
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        }
    },
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        }
    },
}
