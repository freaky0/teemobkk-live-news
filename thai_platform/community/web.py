from urllib.parse import urlencode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.http import Http404
from rest_framework.exceptions import PermissionDenied as APIPermissionDenied, NotFound as APINotFound
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache
from rest_framework.exceptions import ValidationError as APIValidationError
from .forms import CATEGORIES, REGIONS, CommentForm, PostForm, ReportForm
from .models import Notification, Post
from . import services

def call_service(name, *args):
    try:
        return getattr(services, name)(*args)
    except APIPermissionDenied as exc:
        raise PermissionDenied from exc
    except APINotFound as exc:
        raise Http404 from exc

def published():
    return services.public_posts()

def back_url(request):
    query = request.GET.get("from", "")
    if query.startswith("?") and len(query) < 2000:
        return reverse("post-list") + query
    return reverse("post-list")

def home(request):
    from . import news
    context = {"posts": published()[:4]}
    try:
        context["news_page"] = news.list_articles(page_size=5)
    except news.NewsUnavailable:
        context["news_error"] = "뉴스를 불러오지 못했습니다. 잠시 후 다시 확인해 주세요."
    return render(request, "community/home.html", context)

def post_list(request):
    qs = published()
    resolution = request.GET.get('resolution', '')
    if resolution in Post.Resolution.values:
        qs = qs.filter(resolution=resolution)
    q = request.GET.get("q", "").strip()[:200]
    region, category = request.GET.get("region", ""), request.GET.get("category", "")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(body__icontains=q))
    if region in dict(REGIONS):
        qs = qs.filter(region__in=[region, "common"])
    if category in dict(CATEGORIES):
        qs = qs.filter(category=category)
    pagination = Paginator(qs, 20).get_page(request.GET.get("page"))
    keep = request.GET.copy()
    keep.pop("page", None)
    return render(request, "community/list.html", {"resolution": resolution, "resolutions": Post.Resolution.choices, "page_obj": pagination, "q": q, "region": region, "category": category, "regions": REGIONS, "categories": CATEGORIES, "list_query": "?" + request.GET.urlencode(), "filter_query": keep.urlencode()})

@never_cache
def my_activity(request):
    kind = request.GET.get('kind', 'posts')
    try:
        qs = call_service('activity', request.user, kind)
    except APIValidationError:
        raise Http404
    page = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'community/activity.html', {'page_obj': page, 'kind': kind})


@never_cache
def post_detail(request, pk):
    post = get_object_or_404(services.public_posts(request.user), pk=pk)
    return render(request, "community/detail.html", {"post": post, "comments": post.comments.filter(status="published").select_related("author").order_by("created_at"), "comment_form": CommentForm(), "report_form": ReportForm(), "back_url": back_url(request)})

def service_error(form, exc):
    errors = getattr(exc, "message_dict", None) or getattr(exc, "detail", None)
    if isinstance(errors, dict):
        for key, values in errors.items():
            for value in values if isinstance(values, (list, tuple)) else [values]:
                form.add_error(key if key in form.fields else None, str(value))
    else:
        form.add_error(None, "처리하지 못했습니다. 입력 내용을 확인해 주세요.")

@login_required
def post_create(request):
    form = PostForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            data = {k: v for k, v in form.cleaned_data.items() if k != "privacy"}
            post = call_service("create_post", request.user, data)
            messages.success(request, "질문을 서버에 저장했습니다.", extra_tags="post-saved")
            return redirect("post-detail", pk=post.pk)
        except (ValidationError, APIValidationError) as exc:
            service_error(form, exc)
    return render(request, "community/write.html", {"form": form, "editing": False})

@login_required
def post_edit(request, pk):
    post = get_object_or_404(published(), pk=pk)
    if request.user.pk != post.author_id and not request.user.is_staff:
        raise PermissionDenied
    form = PostForm(request.POST or None, initial={"title": post.title, "body": post.body, "region": post.region, "category": post.category})
    if request.method == "POST" and form.is_valid():
        try:
            call_service("update_post", request.user, post, {k: v for k, v in form.cleaned_data.items() if k != "privacy"})
            messages.success(request, "질문을 수정했습니다.", extra_tags="post-saved")
            return redirect("post-detail", pk=post.pk)
        except (ValidationError, APIValidationError) as exc:
            service_error(form, exc)
    return render(request, "community/write.html", {"form": form, "editing": True, "post": post})

@require_POST
def post_helpful(request, pk):
    return engagement_action(request, pk, 'set_helpful')


@require_POST
def post_bookmark(request, pk):
    return engagement_action(request, pk, 'set_bookmark')


def engagement_action(request, pk, service):
    if not request.user.is_authenticated or not request.user.is_active:
        raise PermissionDenied
    post = get_object_or_404(published(), pk=pk)
    try:
        call_service(service, request.user, post, {k: v for k, v in request.POST.items() if k != 'csrfmiddlewaretoken'})
    except APIValidationError:
        return render(request, 'community/action.html', {'form': None, 'title': '요청 값을 확인해 주세요', 'post': post}, status=400)
    return redirect('post-detail', pk=pk)


@require_POST
def post_resolution(request, pk):
    if not request.user.is_authenticated or not request.user.is_active:
        raise PermissionDenied
    post = get_object_or_404(published(), pk=pk)
    try:
        call_service('set_resolution', request.user, post, {k: v for k, v in request.POST.items() if k != 'csrfmiddlewaretoken'})
    except APIValidationError:
        return render(request, 'community/action.html', {'form': None, 'title': '해결 상태를 확인해 주세요', 'post': post}, status=400)
    return redirect('post-detail', pk=pk)


@login_required
@require_POST
def post_delete(request, pk):
    post = get_object_or_404(published(), pk=pk)
    call_service("delete_post", request.user, post)
    messages.success(request, "질문을 삭제했습니다.")
    return redirect("post-list")

@login_required
@require_GET
def notifications_page(request):
    if not request.user.is_active:
        raise PermissionDenied
    items = Notification.objects.filter(recipient=request.user).select_related('post').order_by('-created_at', '-pk')
    response = render(request, 'community/notifications.html', {'notifications': items[:50]})
    response['Cache-Control'] = 'no-store, private'
    return response


@login_required
@require_POST
def notification_read(request, pk):
    if not request.user.is_active:
        raise PermissionDenied
    item = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not item.is_read:
        item.is_read = True
        item.save(update_fields=['is_read', 'updated_at'])
    return redirect('notifications')


@login_required
@require_POST
def comment_create(request, pk):
    post = get_object_or_404(published(), pk=pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        try:
            call_service("create_comment", request.user, post, form.cleaned_data)
            messages.success(request, "답변을 서버에 저장했습니다.")
            return redirect("post-detail", pk=pk)
        except (ValidationError, APIValidationError) as exc:
            service_error(form, exc)
    return render(request, "community/action.html", {"form": form, "title": "답변 내용을 확인해 주세요", "post": post}, status=400)

@login_required
@require_POST
def report_create(request, pk):
    post = get_object_or_404(published(), pk=pk)
    form = ReportForm(request.POST)
    if form.is_valid():
        try:
            call_service("create_report", request.user, post, form.cleaned_data)
            messages.success(request, "신고를 접수했습니다. 운영자가 확인할 수 있습니다.")
            return redirect("post-detail", pk=pk)
        except (ValidationError, APIValidationError) as exc:
            service_error(form, exc)
    return render(request, "community/action.html", {"form": form, "title": "신고 내용을 확인해 주세요", "post": post}, status=400)
