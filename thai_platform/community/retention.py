from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import AuditEvent, Report

REPORT_RETENTION_DAYS = 90


def _expired_reports(cutoff):
    closed_statuses = [Report.Status.RESOLVED, Report.Status.DISMISSED]
    return Report.objects.filter(status__in=closed_statuses).filter(
        Q(closed_at__lte=cutoff)
        | Q(closed_at__isnull=True, updated_at__lte=cutoff)
    )


@transaction.atomic
def purge_expired_reports(*, now=None, dry_run=False):
    now = now or timezone.now()
    cutoff = now - timedelta(days=REPORT_RETENTION_DAYS)
    reports = _expired_reports(cutoff)
    if dry_run:
        report_ids = list(reports.values_list('pk', flat=True))
    else:
        report_ids = list(reports.select_for_update().values_list('pk', flat=True))

    audit_events = AuditEvent.objects.filter(
        target_type='report', target_id__in=[str(pk) for pk in report_ids]
    )
    counts = {
        'reports': len(report_ids),
        'audit_events': audit_events.count(),
    }
    if not dry_run and report_ids:
        audit_events.delete()
        Report.objects.filter(pk__in=report_ids).delete()
    return counts
