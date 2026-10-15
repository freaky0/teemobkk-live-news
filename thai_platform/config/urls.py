from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from community import web
urlpatterns = [
    path("health/", lambda request: JsonResponse({"status": "ok", "service": "teemobkk-post"})),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("api/v1/", include("community.api")),
    path("", web.home, name="home"),
    path("community/", web.post_list, name="post-list"),
    path("community/new/", web.post_create, name="post-create"),
    path("community/<int:pk>/", web.post_detail, name="post-detail"),
    path("community/<int:pk>/edit/", web.post_edit, name="post-edit"),
    path("community/<int:pk>/delete/", web.post_delete, name="post-delete"),
    path("community/<int:pk>/comments/", web.comment_create, name="comment-create"),
    path("community/<int:pk>/report/", web.report_create, name="report-create"),
]
