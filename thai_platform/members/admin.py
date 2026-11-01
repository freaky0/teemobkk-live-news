from django.contrib import admin
from django.utils import timezone
from .models import AccountClosureRequest, MemberProfile


@admin.action(description="비활성화 요청 검토 완료로 표시")
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
    list_display = ["member_name", "member_email", "email_verified_at", "email_login_enabled", "joined_at", "last_login"]
    search_fields = ["user__username", "user__email", "nickname_key", "email_key"]
    list_filter = ["user__is_active", "email_login_enabled", "email_verified_at"]
    ordering = ["-user__date_joined"]
    list_select_related = ["user"]
    readonly_fields = ["user", "email_key", "email_verified_at", "email_login_enabled", "nickname_key", "terms_version", "privacy_version", "accepted_at"]

    @admin.display(description="회원", ordering="nickname_key")
    def member_name(self, obj):
        return obj.nickname_key or obj.user.get_username()

    @admin.display(description="이메일", ordering="email_key")
    def member_email(self, obj):
        return obj.email_key

    @admin.display(description="가입일", ordering="user__date_joined")
    def joined_at(self, obj):
        return obj.user.date_joined

    @admin.display(description="최근 로그인", ordering="user__last_login")
    def last_login(self, obj):
        return obj.user.last_login

    def has_add_permission(self,request): return False
    def has_delete_permission(self,request,obj=None): return False
    def has_change_permission(self,request,obj=None): return False
