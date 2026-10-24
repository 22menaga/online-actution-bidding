"""One command for local development: migrate, seed demo data, run the auction clock and serve the API.

    python manage.py start_local

- Picks port 8000, or the next free port when another program (e.g. another project) is using it.
- Writes the chosen port to backend/.port so the frontend dev server finds it automatically.
- Replaces Celery Beat locally: a background thread starts/closes auctions every few seconds.
"""
import socket
import threading
import time
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection


def free_port(start):
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:  # nothing is listening there
                return port
    raise SystemExit(f'No free port between {start} and {start + 19}.')


def lifecycle_loop(interval):
    from auctions.tasks import process_auction_lifecycle
    while True:
        try:
            process_auction_lifecycle()
        except Exception as exc:  # keep the clock alive
            print(f'[auction clock] error: {exc}')
        finally:
            connection.close()  # each thread owns its DB connection
        time.sleep(interval)


class Command(BaseCommand):
    help = 'Migrate, seed demo data, run the auction clock and serve the API (local development).'

    def add_arguments(self, parser):
        parser.add_argument('--port', type=int, default=8000)
        parser.add_argument('--no-seed', action='store_true', help='skip demo users/auctions')

    def handle(self, *args, **opts):
        port = free_port(opts['port'])
        if port != opts['port']:
            self.stdout.write(self.style.WARNING(f"Port {opts['port']} is used by another program - using {port} instead."))

        call_command('migrate', interactive=False, verbosity=1)
        if not opts['no_seed']:
            call_command('seed_demo')
        call_command('check_payments')
        if settings.AUTO_VERIFY_EMAIL:
            from accounts.models import User
            n = User.objects.filter(email_verified=False).update(email_verified=True)
            if n:
                self.stdout.write(self.style.WARNING(f'Local mode: marked {n} existing account(s) as email-verified so they can bid.'))

        threading.Thread(target=lifecycle_loop, args=(5,), daemon=True, name='auction-clock').start()

        port_file = Path(settings.BASE_DIR) / '.port'
        port_file.write_text(str(port))
        self.stdout.write(self.style.SUCCESS(f'\nBackend ready: http://127.0.0.1:{port}   (Django admin: /admin/)\nNow start the frontend in another terminal:  cd ..\\frontend ; npm run dev\n'))
        try:
            from daphne.cli import CommandLineInterface
            CommandLineInterface().run(['-b', '127.0.0.1', '-p', str(port), 'config.asgi:application'])
        finally:
            port_file.unlink(missing_ok=True)
