from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from community import web, news_views
from members import views as member_views
from django.views.generic import RedirectView
urlpatterns = [
    path("health/", lambda request: JsonResponse({"status": "ok", "service": "teemobkk-post"})),
    path("admin/", admin.site.urls),
    path("accounts/login/", member_views.login_choice, name="member-login"),
    path("accounts/signup/", RedirectView.as_view(pattern_name="email-request", permanent=False)),
    path("accounts/email/", member_views.email_request, name="email-request"),
    path("accounts/email/sent/", member_views.email_sent, name="email-sent"),
    path("accounts/email/confirm/", member_views.email_confirm, name="email-confirm"),
    path("accounts/onboarding/", member_views.onboarding, name="member-onboarding"),
    path("accounts/profile/", member_views.profile, name="member-profile"),
    path("accounts/policy/<str:kind>/", member_views.policy, name="member-policy"),
    path("api/v1/me/", member_views.me, name="member-me"),
    path("accounts/", include("allauth.urls")),
    path("api/v1/news/", news_views.api_list, name="news-api-list"),
    path("api/v1/news/<str:article_id>/", news_views.api_detail, name="news-api-detail"),
    path("news/", news_views.listing, name="news-list"),
    path("news/<str:article_id>/", news_views.detail, name="news-detail"),
    path("api/v1/", include("community.api")),
    path("", web.home, name="home"),
    path("community/", web.post_list, name="post-list"),
    path("community/new/", web.post_create, name="post-create"),
    path("community/activity/", web.my_activity, name="my-activity"),
    path("community/notifications/", web.notifications_page, name="notifications"),
    path("community/notifications/<int:pk>/read/", web.notification_read, name="notification-read"),
    path("community/<int:pk>/", web.post_detail, name="post-detail"),
    path("community/<int:pk>/edit/", web.post_edit, name="post-edit"),
    path("community/<int:pk>/delete/", web.post_delete, name="post-delete"),
    path("community/<int:pk>/resolution/", web.post_resolution, name="post-resolution"),
    path("community/<int:pk>/helpful/", web.post_helpful, name="post-helpful"),
    path("community/<int:pk>/bookmark/", web.post_bookmark, name="post-bookmark"),
    path("community/<int:pk>/comments/", web.comment_create, name="comment-create"),
    path("community/<int:pk>/report/", web.report_create, name="report-create"),
]
