from django.core.management.base import BaseCommand

from payments.provider_status import provider_status


class Command(BaseCommand):
    help = 'Verify the payment provider configuration (calls Razorpay with your keys).'

    def handle(self, *args, **opts):
        s = provider_status(force=True)
        line = f"Payments [{s['provider']}]: {s['status'].upper()} - {s['detail']}"
        if s['status'] in ('ok', 'mock'):
            self.stdout.write(self.style.SUCCESS(line))
        else:
            self.stdout.write(self.style.WARNING(line))
