from django.contrib import admin
from .models import MemberProfile

@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "email_verified_at", "email_login_enabled", "accepted_at"]
    readonly_fields = ["user", "email_key", "email_verified_at", "email_login_enabled", "nickname_key", "terms_version", "privacy_version", "accepted_at"]
    def has_add_permission(self,request): return False
    def has_delete_permission(self,request,obj=None): return False
    def has_change_permission(self,request,obj=None): return False
