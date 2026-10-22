from django.core.management.base import BaseCommand

from community.retention import purge_expired_reports


class Command(BaseCommand):
    help = 'Apply the 90-day retention period to resolved community reports.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show eligible record counts without changing the database.',
        )

    def handle(self, *args, **options):
        counts = purge_expired_reports(dry_run=options['dry_run'])
        if options['dry_run']:
            message = (
                f"Would remove {counts['reports']} expired reports and "
                f"{counts['audit_events']} related audit events."
            )
        else:
            message = (
                f"Removed {counts['reports']} expired reports and "
                f"{counts['audit_events']} related audit events."
            )
        self.stdout.write(message)
