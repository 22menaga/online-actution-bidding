import logging

import redis
from django.conf import settings
from django.db import OperationalError, connections
from django.db.migrations.executor import MigrationExecutor
from django.http import HttpResponse

logger = logging.getLogger(__name__)


def readiness(_request):
    try:
        connection = connections["default"]
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        pending = MigrationExecutor(connection).migration_plan(MigrationExecutor(connection).loader.graph.leaf_nodes())
    except OperationalError:
        logger.exception("Application readiness check failed (database).")
        return HttpResponse("not ready: database unavailable", status=503, content_type="text/plain")
    if pending:
        names = ", ".join(f"{m.app_label}.{m.name}" for m, _ in pending[:5])
        logger.error("Unapplied database migrations: %s", names)
        return HttpResponse(f"not ready: unapplied database migrations ({names}). Run: python manage.py migrate", status=503, content_type="text/plain")
    if not getattr(settings, "USE_INMEMORY_CHANNELS", False):
        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        try:
            client.ping()
        except redis.RedisError:
            logger.exception("Application readiness check failed (redis).")
            return HttpResponse("not ready: redis unavailable", status=503, content_type="text/plain")
        finally:
            client.close()
    return HttpResponse("ok", content_type="text/plain")
