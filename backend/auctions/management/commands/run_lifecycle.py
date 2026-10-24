import time
from django.core.management.base import BaseCommand
from auctions.tasks import process_auction_lifecycle


class Command(BaseCommand):
    help = 'Local-dev replacement for Celery Beat: starts and closes auctions every few seconds.'

    def add_arguments(self, parser):
        parser.add_argument('--interval', type=int, default=5)

    def handle(self, *args, **opts):
        self.stdout.write(f'Auction lifecycle loop running every {opts["interval"]}s (Ctrl+C to stop)')
        while True:
            try:
                process_auction_lifecycle()
            except Exception as exc:  # keep the loop alive
                self.stderr.write(f'lifecycle error: {exc}')
            time.sleep(opts['interval'])
