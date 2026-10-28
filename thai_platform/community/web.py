from urllib.parse import urlencode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, Prefetch, Count, Exists, OuterRef, Value, BooleanField
from django.shortcuts import get_object_or_404, redirect, render
from django.http import Http404
from rest_framework.exceptions import PermissionDenied as APIPermissionDenied, NotFound as APINotFound
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache
from rest_framework.exceptions import ValidationError as APIValidationError
from .forms import CATEGORIES, REGIONS, AppealForm, CommentForm, PostForm, ReportForm
from .models import Comment, CommentLike, Post
from .board_versions import board_data_version
from . import services

def call_service(name, *args):
    try:
        return getattr(services, name)(*args)
    except APIPermissionDenied as exc:
        raise PermissionDenied from exc
    except APINotFound as exc:
        raise Http404 from exc

def published(user=None):
    return services.public_posts(user)

def back_url(request):
    query = request.GET.get("from", "")
    if query.startswith("?") and len(query) < 2000:
        return reverse("post-list") + query
    return reverse("post-list")

def home(request):
    from . import news
    context = {"posts": published(request.user)[:4], "helpful_posts": published(request.user).filter(helpful_count__gt=0).order_by('-helpful_count', '-created_at', '-pk')[:4]}
    try:
        context["news_page"] = news.list_articles(page_size=5)
    except news.NewsUnavailable:
        context["news_error"] = "뉴스를 불러오지 못했습니다. 잠시 후 다시 확인해 주세요."
    return render(request, "community/home.html", context)

def post_list(request):
    qs = published(request.user)
    resolution = request.GET.get('resolution', '')
    if resolution in Post.Resolution.values:
        qs = qs.filter(resolution=resolution)
    q = request.GET.get("q", "").strip()[:200]
    region, category = request.GET.get("region", ""), request.GET.get("category", "")
    if q:
        qs = services.search_posts(qs, q)
    if region in dict(REGIONS):
        qs = qs.filter(region__in=[region, "common"])
    if category in services.LIFE_BOARD_CATEGORIES:
        qs = qs.filter(category__in=services.LIFE_BOARD_CATEGORIES)
        category = Post.Category.LIVING
    elif category in dict(CATEGORIES):
        qs = qs.filter(category=category)
    pagination = Paginator(qs, 20).get_page(request.GET.get("page"))
    keep = request.GET.copy()
    keep.pop("page", None)
    return render(request, "community/list.html", {"resolution": resolution, "resolutions": Post.Resolution.choices, "page_obj": pagination, "q": q, "region": region, "category": category, "regions": REGIONS, "categories": CATEGORIES, "list_query": "?" + request.GET.urlencode(), "filter_query": keep.urlencode()})


@never_cache
@require_GET
def operator_hidden_posts(request):
    call_service('require_post_operator', request.user)
    posts = Post.objects.filter(status=Post.Status.HIDDEN).select_related('author')
    return render(request, 'community/operator_hidden.html', {'page_obj': Paginator(posts, 20).get_page(request.GET.get('page'))})


@never_cache
def operator_delete_confirm(request, pk):
    call_service('require_post_operator', request.user)
    if request.method != 'GET':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['GET'])
    post = get_object_or_404(Post.objects.exclude(status=Post.Status.DELETED), pk=pk)
    return render(request, 'community/operator_delete.html', {'post': post})


@never_cache
@require_POST
def operator_post_action(request, pk):
    call_service('require_post_operator', request.user)
    post = get_object_or_404(Post.objects.exclude(status=Post.Status.DELETED), pk=pk)
    action = request.POST.get('action')
    if action == 'delete' and request.POST.get('confirm') != 'yes':
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest('Confirmation required.')
    try:
        call_service('operator_post_action', request.user, post, action)
    except APIValidationError:
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest('Invalid action or post status.')
    if action == 'restore':
        return redirect('post-detail', pk=pk)
    return redirect('operator-hidden-posts' if action == 'hide' else 'post-list')

@require_GET
def public_member(request, pk):
    from members.models import MemberProfile
    members = MemberProfile.objects.filter(user__is_active=True, accepted_at__isnull=False, email_verified_at__isnull=False, nickname_key__isnull=False)
    blocked_ids = services.blocked_member_ids(request.user)
    if blocked_ids is not None:
        members = members.exclude(user_id__in=blocked_ids)
    member = get_object_or_404(members, user_id=pk)
    if not member.nickname_key:
        raise Http404
    posts = Paginator(published(request.user).filter(author_id=pk), 20).get_page(request.GET.get('page'))
    return render(request, 'community/public_member.html', {'member': member, 'page_obj': posts})


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
    viewer = Exists(CommentLike.objects.filter(comment_id=OuterRef('pk'), user=request.user)) if request.user.is_authenticated else Value(False, output_field=BooleanField())
    visible = services.visible_comments(request.user, post).select_related('author', 'author__membership').annotate(like_count=Count('likes'), viewer_likes=viewer).order_by('created_at', 'pk')
    replies = visible.filter(parent__isnull=False)
    comments = visible.filter(parent__isnull=True).prefetch_related(Prefetch('replies', queryset=replies))
    return render(request, "community/detail.html", {"post": post, "comments": comments, "comment_form": CommentForm(), "report_form": ReportForm(), "back_url": back_url(request)})


@never_cache
@require_POST
def comment_like(request, pk, comment_pk):
    call_service('require_active', request.user)
    post = get_object_or_404(published(request.user), pk=pk)
    comment = get_object_or_404(services.visible_comments(request.user, post), pk=comment_pk)
    active = request.POST.get('active')
    if active not in ('true', 'false') or set(request.POST) - {'active', 'csrfmiddlewaretoken'}:
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest('Invalid request.')
    if active == 'true':
        CommentLike.objects.get_or_create(user=request.user, comment=comment)
    else:
        CommentLike.objects.filter(user=request.user, comment=comment).delete()
    return redirect('post-detail', pk=pk)

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
    if request.method == 'POST' and 'is_pinned' in request.POST and not request.user.is_staff:
        raise PermissionDenied
    category = request.GET.get('category', '')
    form = PostForm(request.POST or None, initial={'category': category} if category in dict(CATEGORIES) else None, staff=request.user.is_staff)
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
@never_cache
def post_edit(request, pk):
    if request.method == 'POST' and 'is_pinned' in request.POST and not request.user.is_staff:
        raise PermissionDenied
    post = get_object_or_404(published(request.user), pk=pk)
    if not (post.category == Post.Category.NOTICE and request.user.is_staff) and request.user.pk != post.author_id:
        raise PermissionDenied
    if post.category == Post.Category.NOTICE and not request.user.is_staff:
        raise PermissionDenied
    form = PostForm(request.POST or None, initial={"board_data_version": board_data_version(post), "title": post.display_title, "body": post.display_body, "region": post.region, "category": services.canonical_life_category(post.category), "is_pinned": post.is_pinned, "market_kind": post.market_kind, "market_price": post.market_price, "market_region": post.market_region, "market_status": post.market_status, "job_kind": post.job_kind, "job_region": post.job_region, "job_compensation": post.job_compensation, "job_status": post.job_status, "place_name": post.place_name, "place_region": post.place_region, "place_note": post.place_note, "place_url": post.place_url}, staff=request.user.is_staff, editing=True)
    if request.method == "POST" and form.is_valid():
        try:
            call_service("update_post", request.user, post, {k: v for k, v in form.cleaned_data.items() if k != "privacy"})
            messages.success(request, "질문을 수정했습니다.", extra_tags="post-saved")
            return redirect("post-detail", pk=post.pk)
        except (ValidationError, APIValidationError) as exc:
            service_error(form, exc)
    if request.method == 'POST':
        post.refresh_from_db()
        data = form.data.copy()
        stale = bool(data.get('board_data_version')) and data.get('board_data_version') != board_data_version(post)
        for prefix, category in (('market_', 'market'), ('job_', 'jobs'), ('place_', 'foodtravel')):
            for name in form.fields:
                if name.startswith(prefix) and data.get('category') != category and (name not in data or (post.category == category and data.get('board_fields_snapshot') != '1' and not data.get(name))):
                    data[name] = getattr(post, name) if getattr(post, name) is not None else ''
        data['board_data_version'] = data.get('board_data_version') if stale else board_data_version(post)
        data.pop('confirm_board_data_removal', None)
        form.data = data
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
    post = get_object_or_404(published(request.user), pk=pk)
    try:
        call_service(service, request.user, post, {k: v for k, v in request.POST.items() if k != 'csrfmiddlewaretoken'})
    except APIValidationError:
        return render(request, 'community/action.html', {'form': None, 'title': '요청 값을 확인해 주세요', 'post': post}, status=400)
    return redirect('post-detail', pk=pk)


@require_POST
def post_resolution(request, pk):
    if not request.user.is_authenticated or not request.user.is_active:
        raise PermissionDenied
    post = get_object_or_404(published(request.user), pk=pk)
    try:
        call_service('set_resolution', request.user, post, {k: v for k, v in request.POST.items() if k != 'csrfmiddlewaretoken'})
    except APIValidationError:
        return render(request, 'community/action.html', {'form': None, 'title': '해결 상태를 확인해 주세요', 'post': post}, status=400)
    return redirect('post-detail', pk=pk)


@login_required
@require_POST
def post_delete(request, pk):
    post = get_object_or_404(published(request.user), pk=pk)
    call_service("delete_post", request.user, post)
    messages.success(request, "질문을 삭제했습니다.")
    return redirect("post-list")

@login_required
@require_GET
def notifications_page(request):
    if not request.user.is_active:
        raise PermissionDenied
    items = services.visible_notifications(request.user).select_related('post', 'appeal').order_by('-created_at', '-pk')
    response = render(request, 'community/notifications.html', {'notifications': items[:50]})
    response['Cache-Control'] = 'no-store, private'
    return response


@login_required
@require_POST
def notification_read(request, pk):
    if not request.user.is_active:
        raise PermissionDenied
    item = get_object_or_404(services.visible_notifications(request.user), pk=pk)
    if not item.is_read:
        item.is_read = True
        item.save(update_fields=['is_read', 'updated_at'])
    return redirect('notifications')


@login_required
@require_POST
def comment_create(request, pk):
    post = get_object_or_404(published(request.user), pk=pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        try:
            data = dict(form.cleaned_data)
            if 'parent' in request.POST:
                data['parent'] = request.POST['parent']
            call_service("create_comment", request.user, post, data)
            messages.success(request, "답변을 서버에 저장했습니다.")
            return redirect("post-detail", pk=pk)
        except (ValidationError, APIValidationError) as exc:
            service_error(form, exc)
    return render(request, "community/action.html", {"form": form, "title": "답변 내용을 확인해 주세요", "post": post}, status=400)

@login_required
@require_POST
def report_create(request, pk):
    post = get_object_or_404(published(request.user), pk=pk)
    form = ReportForm(request.POST)
    if form.is_valid():
        try:
            call_service("create_report", request.user, post, form.cleaned_data)
            messages.success(request, "신고를 접수했습니다. 운영자가 확인할 수 있습니다.")
            return redirect("post-detail", pk=pk)
        except (ValidationError, APIValidationError) as exc:
            service_error(form, exc)
    return render(request, "community/action.html", {"form": form, "title": "신고 내용을 확인해 주세요", "post": post}, status=400)


@login_required
@never_cache
def appeal_create(request, pk):
    post = get_object_or_404(Post, pk=pk)
    comment_id = request.GET.get('comment')
    comment = None
    if comment_id:
        if not comment_id.isdecimal():
            raise Http404
        comment = get_object_or_404(Comment, pk=int(comment_id), post=post, author=request.user, status=Comment.Status.HIDDEN)
    elif post.author_id != request.user.pk or post.status != Post.Status.HIDDEN:
        raise Http404
    form = AppealForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            call_service('create_appeal', request.user, {'post': post.pk, 'comment': comment.pk if comment else None, **form.cleaned_data})
            messages.success(request, '이의신청을 접수했습니다. 심사 상태와 처리 방식은 운영 정책 확정 후 안내됩니다.')
            return redirect('notifications')
        except (ValidationError, APIValidationError) as exc:
            service_error(form, exc)
    response = render(request, 'community/appeal.html', {'form': form, 'post': post, 'comment': comment})
    response['Cache-Control'] = 'no-store, private'
    return response
