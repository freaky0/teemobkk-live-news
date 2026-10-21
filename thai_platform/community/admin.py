from django.contrib import admin, messages
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import AuditEvent, Comment, Post, Report
from .services import moderate_comment, resolve_report


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'author', 'region', 'category', 'status', 'created_at']
    list_filter = ['status', 'region', 'category']
    search_fields = ['title', 'body']
    readonly_fields = ['author', 'created_at', 'updated_at']
    actions = None

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'post', 'author', 'status', 'created_at']
    list_filter = ['status']
    readonly_fields = ['post', 'author', 'body', 'created_at', 'updated_at']
    actions = ['hide_selected', 'restore_selected']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def apply_moderation(self, request, queryset, status):
        for comment in queryset:
            try:
                moderate_comment(request.user, comment, status)
            except (PermissionDenied, ValidationError) as exc:
                self.message_user(request, f'Comment {comment.pk} could not be moderated: {exc}', level=messages.ERROR)

    @admin.action(description='Hide selected comments')
    def hide_selected(self, request, queryset):
        self.apply_moderation(request, queryset, Comment.Status.HIDDEN)

    @admin.action(description='Restore selected comments after review')
    def restore_selected(self, request, queryset):
        self.apply_moderation(request, queryset, Comment.Status.PUBLISHED)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'post', 'reason', 'status', 'created_at']
    list_filter = ['status', 'reason']
    readonly_fields = ['reporter', 'post', 'comment', 'reason', 'details', 'status', 'created_at', 'updated_at']
    actions = ['mark_resolved', 'mark_dismissed']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='Resolve selected reports')
    def mark_resolved(self, request, queryset):
        for report in queryset:
            resolve_report(request.user, report, {'status': 'resolved'})

    @admin.action(description='Dismiss selected reports')
    def mark_dismissed(self, request, queryset):
        for report in queryset:
            resolve_report(request.user, report, {'status': 'dismissed'})


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ['id', 'actor', 'action', 'target_type', 'target_id', 'created_at']
    readonly_fields = ['actor', 'action', 'target_type', 'target_id', 'created_at', 'metadata']
    actions = None

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False
