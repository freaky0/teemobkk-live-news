from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command, get_commands
from django.test import TestCase
from django.utils import timezone

from .models import AuditEvent, Post, Report


class ReportRetentionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='retention-reporter')
        self.post = Post.objects.create(author=self.user, title='Retention test', body='Test content')

    def test_closed_reports_older_than_90_days_and_their_audits_are_removed(self):
        old_report = Report.objects.create(
            reporter=self.user,
            post=self.post,
            reason=Report.Reason.SPAM,
            status=Report.Status.RESOLVED,
            closed_at=timezone.now() - timedelta(days=91),
        )
        old_audit = AuditEvent.objects.create(
            actor=self.user,
            action='report.resolve',
            target_type='report',
            target_id=str(old_report.pk),
        )
        old_open_report = Report.objects.create(
            reporter=self.user,
            post=self.post,
            reason=Report.Reason.ABUSE,
            status=Report.Status.OPEN,
        )
        Report.objects.filter(pk=old_open_report.pk).update(updated_at=timezone.now() - timedelta(days=100))
        old_open_audit = AuditEvent.objects.create(
            actor=self.user,
            action='report.create',
            target_type='report',
            target_id=str(old_open_report.pk),
        )
        recent_report = Report.objects.create(
            reporter=self.user,
            post=self.post,
            reason=Report.Reason.OUTDATED,
            status=Report.Status.DISMISSED,
            closed_at=timezone.now() - timedelta(days=89),
        )
        recent_audit = AuditEvent.objects.create(
            actor=self.user,
            action='report.resolve',
            target_type='report',
            target_id=str(recent_report.pk),
        )

        self.assertIn('apply_report_retention', get_commands())
        call_command('apply_report_retention')

        self.assertFalse(Report.objects.filter(pk=old_report.pk).exists())
        self.assertFalse(AuditEvent.objects.filter(pk=old_audit.pk).exists())
        self.assertTrue(Report.objects.filter(pk=old_open_report.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(pk=old_open_audit.pk).exists())
        self.assertTrue(Report.objects.filter(pk=recent_report.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(pk=recent_audit.pk).exists())
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())

    def test_dry_run_counts_eligible_reports_without_deleting(self):
        old_report = Report.objects.create(
            reporter=self.user,
            post=self.post,
            reason=Report.Reason.SPAM,
            status=Report.Status.RESOLVED,
            closed_at=timezone.now() - timedelta(days=91),
        )
        old_audit = AuditEvent.objects.create(
            actor=self.user,
            action='report.resolve',
            target_type='report',
            target_id=str(old_report.pk),
        )
        output = StringIO()

        call_command('apply_report_retention', '--dry-run', stdout=output)

        self.assertIn('Would remove 1 expired reports and 1 related audit events', output.getvalue())
        self.assertTrue(Report.objects.filter(pk=old_report.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(pk=old_audit.pk).exists())
