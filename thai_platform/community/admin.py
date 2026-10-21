from django.contrib import admin, messages
from rest_framework.exceptions import PermissionDenied as APIPermissionDenied, ValidationError as APIValidationError
from .models import AuditEvent, Comment, ModerationAppeal, NewsComment, NewsLike, Post, Report
from .services import hide_reported_content, is_report_moderator, resolve_appeal, resolve_report


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'author', 'region', 'category', 'status', 'created_at']
    list_filter = ['status', 'region', 'category']
    search_fields = ['title', 'body']
    readonly_fields = [field.name for field in Post._meta.fields]
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ('GET', 'HEAD') and super().has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'post', 'author', 'status', 'created_at']
    list_filter = ['status']
    readonly_fields = [field.name for field in Comment._meta.fields]
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ('GET', 'HEAD') and super().has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NewsComment)
class NewsCommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'article_id', 'author', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['article_id', 'body', 'author__username']
    readonly_fields = [field.name for field in NewsComment._meta.fields]
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ('GET', 'HEAD') and super().has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NewsLike)
class NewsLikeAdmin(admin.ModelAdmin):
    list_display = ['id', 'article_id', 'user', 'created_at']
    list_filter = ['created_at']
    readonly_fields = [field.name for field in NewsLike._meta.fields]
    actions = None

    def has_add_permission(self, request):
        return False

    def has_module_permission(self, request):
        return is_report_moderator(request.user)

    def has_view_permission(self, request, obj=None):
        return is_report_moderator(request.user)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'target_type', 'post', 'comment', 'reason', 'status', 'created_at']
    list_filter = ['status', 'reason']
    readonly_fields = ['reporter', 'post', 'comment', 'target_type', 'reason', 'details', 'status', 'created_at', 'updated_at']
    actions = ['mark_resolved', 'mark_dismissed', 'hide_reported']

    def has_module_permission(self, request):
        return is_report_moderator(request.user)

    def has_view_permission(self, request, obj=None):
        return is_report_moderator(request.user)

    def has_change_permission(self, request, obj=None):
        return is_report_moderator(request.user)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def apply_reports(self, request, queryset, operation):
        for report in queryset:
            try:
                operation(request.user, report)
            except APIValidationError:
                self.message_user(request, f'Report {report.pk} could not be processed; review its current state.', level=messages.ERROR)

    @admin.action(description='Resolve selected reports')
    def mark_resolved(self, request, queryset):
        self.apply_reports(request, queryset, lambda user, report: resolve_report(user, report, {'status': Report.Status.RESOLVED}))

    @admin.action(description='Dismiss selected reports')
    def mark_dismissed(self, request, queryset):
        self.apply_reports(request, queryset, lambda user, report: resolve_report(user, report, {'status': Report.Status.DISMISSED}))

    @admin.action(description='Hide only reported content')
    def hide_reported(self, request, queryset):
        self.apply_reports(request, queryset, hide_reported_content)


@admin.register(ModerationAppeal)
class ModerationAppealAdmin(admin.ModelAdmin):
    list_display = ['id', 'author', 'target_type', 'post', 'comment', 'status', 'reviewed_by', 'created_at']
    list_filter = ['status']
    readonly_fields = [field.name for field in ModerationAppeal._meta.fields]
    actions = ['uphold_appeals', 'restore_appeals']

    def has_module_permission(self, request):
        return is_report_moderator(request.user)

    def has_view_permission(self, request, obj=None):
        return is_report_moderator(request.user)

    def has_change_permission(self, request, obj=None):
        return is_report_moderator(request.user)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def apply_decisions(self, request, queryset, outcome):
        for appeal in queryset:
            try:
                resolve_appeal(request.user, appeal, outcome)
            except (APIValidationError, APIPermissionDenied) as exc:
                self.message_user(request, f'Appeal {appeal.pk} could not be processed: {exc}', level=messages.ERROR)

    @admin.action(description='Uphold selected hidden-content decisions')
    def uphold_appeals(self, request, queryset):
        self.apply_decisions(request, queryset, ModerationAppeal.Status.UPHELD)

    @admin.action(description='Restore selected appealed content')
    def restore_appeals(self, request, queryset):
        self.apply_decisions(request, queryset, ModerationAppeal.Status.RESTORED)


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ['id', 'actor', 'action', 'target_type', 'target_id', 'created_at']
    readonly_fields = ['actor', 'action', 'target_type', 'target_id', 'created_at', 'metadata']
    actions = None

    def has_add_permission(self, request):
        return False

    def has_module_permission(self, request):
        return is_report_moderator(request.user)

    def has_view_permission(self, request, obj=None):
        return is_report_moderator(request.user)

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False
