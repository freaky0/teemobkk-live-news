from django.contrib import admin
from django.utils import timezone
from .models import AccountClosureRequest, MemberProfile


@admin.action(description="삭제 여부 검토 완료로 표시")
def mark_closure_reviewed(modeladmin, request, queryset):
    queryset.filter(status=AccountClosureRequest.Status.PENDING_REVIEW).update(
        status=AccountClosureRequest.Status.REVIEWED,
        reviewed_at=timezone.now(),
        reviewed_by=request.user,
    )


@admin.register(AccountClosureRequest)
class AccountClosureRequestAdmin(admin.ModelAdmin):
    list_display = ["user", "status", "requested_at", "reviewed_at", "reviewed_by"]
    list_filter = ["status", "requested_at"]
    readonly_fields = ["user", "status", "requested_at", "reviewed_at", "reviewed_by"]
    actions = [mark_closure_reviewed]
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "email_verified_at", "email_login_enabled", "accepted_at"]
    readonly_fields = ["user", "email_key", "email_verified_at", "email_login_enabled", "nickname_key", "terms_version", "privacy_version", "accepted_at"]
    def has_add_permission(self,request): return False
    def has_delete_permission(self,request,obj=None): return False
    def has_change_permission(self,request,obj=None): return False
