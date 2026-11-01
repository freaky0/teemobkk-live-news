from datetime import datetime, time, timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.http import QueryDict
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone

from community.models import ModerationAppeal, Post, Report
from community.services import is_report_moderator
from members.models import AccountClosureRequest, MemberProfile


class TeemoBKKAdminSite(admin.AdminSite):
    site_header = "TeemoBKK 사이트 관리"
    site_title = "TeemoBKK 관리"
    index_title = "운영 대시보드"
    index_template = "admin/site_dashboard.html"
    app_labels = {
        "members": "회원",
        "community": "커뮤니티",
        "auth": "계정 및 권한",
    }
    model_labels = {
        ("members", "MemberProfile"): "회원 프로필",
        ("members", "AccountClosureRequest"): "계정 비활성화 요청",
        ("auth", "User"): "사용자 계정",
        ("auth", "Group"): "그룹 및 권한",
        ("community", "BoardCategory"): "게시판 분류",
        ("community", "Post"): "게시물",
        ("community", "Comment"): "댓글",
        ("community", "NewsComment"): "뉴스 댓글",
        ("community", "NewsLike"): "뉴스 반응",
        ("community", "Report"): "신고",
        ("community", "ModerationAppeal"): "신고 이의제기",
        ("community", "AuditEvent"): "운영 기록",
    }
    model_order = {
        "members": {"MemberProfile": 0, "AccountClosureRequest": 1},
        "community": {
            "Post": 0,
            "Report": 1,
            "ModerationAppeal": 2,
            "Comment": 3,
            "NewsComment": 4,
            "BoardCategory": 5,
            "NewsLike": 6,
            "AuditEvent": 7,
        },
        "auth": {"User": 0, "Group": 1},
    }

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)
        for app in app_list:
            app["name"] = self.app_labels.get(app["app_label"], app["name"])
            for model in app["models"]:
                model["name"] = self.model_labels.get(
                    (app["app_label"], model["object_name"]), model["name"]
                )
            model_order = self.model_order.get(app["app_label"], {})
            app["models"].sort(key=lambda model: model_order.get(model["object_name"], 99))
        order = {"members": 0, "community": 1, "auth": 2}
        app_list.sort(key=lambda app: order.get(app["app_label"], 3))
        return app_list

    @staticmethod
    def can_view_members(user):
        return bool(user.is_superuser or user.has_perm("members.view_memberprofile"))

    @staticmethod
    def member_summary(user):
        try:
            profile = user.membership
        except MemberProfile.DoesNotExist:
            profile = None

        return {
            "username": user.get_username(),
            "nickname": (profile.nickname_key if profile else "") or user.get_username(),
            "email": (profile.email_key if profile else "") or user.email,
            "date_joined": user.date_joined,
            "last_login": user.last_login,
            "is_active": user.is_active,
            "email_verified": bool(profile and profile.email_verified_at),
        }

    @staticmethod
    def signup_months(user_model, now):
        first_of_month = now.date().replace(day=1)
        month_starts = [first_of_month]
        for _ in range(5):
            month_starts.append((month_starts[-1] - timedelta(days=1)).replace(day=1))
        month_starts.reverse()

        start_at = timezone.make_aware(datetime.combine(month_starts[0], time.min))
        counts = {}
        grouped = (
            user_model.objects.filter(is_staff=False, date_joined__gte=start_at)
            .annotate(month=TruncMonth("date_joined"))
            .values("month")
            .annotate(total=Count("pk"))
            .order_by("month")
        )
        for row in grouped:
            month = timezone.localtime(row["month"]).date().replace(day=1)
            counts[month] = row["total"]

        highest = max(counts.values(), default=0)
        return [
            {
                "label": month.strftime("%y.%m"),
                "count": counts.get(month, 0),
                "width_bucket": min(
                    100,
                    max(
                        0,
                        int(((counts.get(month, 0) * 100 / highest if highest else 0) + 10) // 20) * 20,
                    ),
                ),
            }
            for month in month_starts
        ]

    def index(self, request, extra_context=None):
        user_model = get_user_model()
        can_view_members = self.can_view_members(request.user)
        can_view_posts = bool(
            request.user.is_superuser
            or request.user.has_perm("community.view_post")
            or request.user.has_perm("community.change_post")
        )
        can_view_reports = is_report_moderator(request.user)
        can_view_closures = bool(
            request.user.is_superuser or request.user.has_perm("members.view_accountclosurerequest")
        )
        now = timezone.localtime()

        dashboard = {
            "can_view_members": can_view_members,
            "can_view_posts": can_view_posts,
            "can_view_reports": can_view_reports,
            "can_view_closures": can_view_closures,
            "signup_months": [],
            "recent_members": [],
        }
        if can_view_members:
            member_users = user_model.objects.filter(is_staff=False)
            dashboard.update(
                total_members=member_users.count(),
                active_members=member_users.filter(is_active=True).count(),
                verified_members=MemberProfile.objects.filter(
                    user__is_staff=False,
                    email_verified_at__isnull=False,
                ).count(),
                new_members_30d=member_users.filter(date_joined__gte=now - timedelta(days=30)).count(),
                recent_members=[
                    self.member_summary(user)
                    for user in member_users.select_related("membership").order_by("-date_joined", "-pk")[:8]
                ],
                signup_months=self.signup_months(user_model, now),
            )
        if can_view_posts:
            dashboard["post_count"] = Post.objects.count()
        if can_view_reports:
            dashboard["open_report_count"] = Report.objects.filter(status=Report.Status.OPEN).count()
            dashboard["pending_appeal_count"] = ModerationAppeal.objects.filter(
                status=ModerationAppeal.Status.PENDING_REVIEW
            ).count()
        if can_view_closures:
            dashboard["pending_closure_count"] = AccountClosureRequest.objects.filter(
                status=AccountClosureRequest.Status.PENDING_REVIEW
            ).count()

        context = dict(extra_context or {})
        context.update(dashboard)
        context["dashboard_updated_at"] = now
        return super().index(request, context)

    def get_urls(self):
        custom_urls = [
            path(
                "member-directory/",
                self.admin_view(self.member_directory),
                name="member-directory",
            ),
        ]
        return custom_urls + super().get_urls()

    def member_directory(self, request):
        if not self.can_view_members(request.user):
            raise PermissionDenied("회원 조회 권한이 없습니다.")

        user_model = get_user_model()
        query = request.GET.get("q", "").strip()[:100]
        active_filter = request.GET.get("active", "all")
        if active_filter not in {"all", "active", "inactive"}:
            active_filter = "all"
        verified_filter = request.GET.get("verified", "all")
        if verified_filter not in {"all", "verified", "unverified"}:
            verified_filter = "all"
        members = user_model.objects.filter(is_staff=False).select_related("membership").order_by("-date_joined", "-pk")

        if query:
            members = members.filter(
                Q(username__icontains=query)
                | Q(email__icontains=query)
                | Q(membership__email_key__icontains=query)
                | Q(membership__nickname_key__icontains=query)
            )
        if active_filter == "active":
            members = members.filter(is_active=True)
        elif active_filter == "inactive":
            members = members.filter(is_active=False)
        if verified_filter == "verified":
            members = members.filter(membership__email_verified_at__isnull=False)
        elif verified_filter == "unverified":
            members = members.filter(
                Q(membership__isnull=True) | Q(membership__email_verified_at__isnull=True)
            )

        page_obj = Paginator(members, 30).get_page(request.GET.get("page"))
        params = QueryDict("", mutable=True)
        if query:
            params["q"] = query
        if active_filter != "all":
            params["active"] = active_filter
        if verified_filter != "all":
            params["verified"] = verified_filter
        page_query = params.urlencode()
        if page_query:
            page_query += "&"
        page_numbers = range(max(1, page_obj.number - 2), min(page_obj.paginator.num_pages, page_obj.number + 2) + 1)

        context = {
            **self.each_context(request),
            "title": "회원 관리",
            "members": [self.member_summary(user) for user in page_obj.object_list],
            "page_obj": page_obj,
            "page_query": page_query,
            "page_numbers": page_numbers,
            "search_query": query,
            "active_filter": active_filter,
            "verified_filter": verified_filter,
            "can_view_members": True,
        }
        return TemplateResponse(request, "admin/member_directory.html", context)
