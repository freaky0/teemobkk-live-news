from urllib.parse import urlencode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, Prefetch, Count, Exists, OuterRef, Value, BooleanField
from django.shortcuts import get_object_or_404, redirect, render
from django.http import Http404, HttpResponse
from django.db import transaction
from rest_framework.exceptions import PermissionDenied as APIPermissionDenied, NotFound as APINotFound
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache
from rest_framework.exceptions import ValidationError as APIValidationError
from config.seo import render_seo
from .forms import CATEGORIES, REGIONS, AppealForm, CommentForm, PostForm, ReportForm
from .models import BoardCategory, Comment, CommentLike, Notification, Post, PostImage, RESOLUTION_CATEGORIES
from .board_versions import board_data_version
from .post_media import replace_inline_upload_markers, save_post_images
from . import services

DEFAULT_BOARD_COPY = ("이웃에게 묻고 답하기", "태국 생활의 질문과 경험을 나눕니다.")
BOARD_COPY = {
    "notice": ("공지사항", "서비스 소식과 운영 안내를 확인하세요."),
    "free": ("자유게시판", "태국 생활의 일상과 관심사를 이웃과 자유롭게 나눠요."),
    "questions": ("질문/답변", "태국 생활 중 궁금한 점을 묻고 아는 정보를 나눠요."),
    "market": ("중고게시판", "태국에서 필요한 물건을 사고팔며 이웃과 거래해요."),
    "jobs": ("구인구직", "태국 현지의 채용과 구직 정보를 나누고 찾아보세요."),
    "foodtravel": ("맛집/여행지", "직접 다녀온 맛집과 여행지를 소개하고 후기를 나눠요."),
    "living": ("생활 질문", "주거와 일상에서 마주친 궁금한 점을 묻고 답해요."),
    "visa": ("비자·체류", "비자와 체류 관련 경험과 정보를 함께 나눠요."),
    "travel": ("교통·여행", "태국의 이동과 여행에 필요한 정보를 나눠요."),
}


def with_post_images(queryset):
    return queryset.prefetch_related(
        Prefetch(
            'images',
            queryset=PostImage.objects.only('pk', 'post_id', 'image_url', 'position'),
        ),
    )
BOARD_GUIDES = {
    "notice": {"title": "공지 작성 안내", "description": "운영진의 공식 소식과 이용 안내를 간결하게 전달해 주세요.", "tips": ["변경 내용과 적용 날짜를 제목에 담아 주세요.", "개인 정보나 확인되지 않은 안내는 게시하지 마세요."]},
    "free": {"title": "자유게시판 작성 안내", "description": "태국에서 겪은 일상과 경험을 이웃과 나눠 보세요.", "tips": ["지역이나 상황을 덧붙이면 다른 회원이 공감하기 쉬워요.", "연락처·주소 등 개인 정보는 공개하지 마세요."]},
    "questions": {"title": "질문 작성 안내", "description": "상황과 궁금한 점을 구체적으로 적으면 더 정확한 답을 받을 수 있어요.", "tips": ["지역, 일정, 예산처럼 답변에 필요한 조건을 적어 주세요.", "답을 찾으면 질문 상태를 해결로 표시해 주세요."]},
    "market": {"title": "중고 거래 작성 안내", "description": "물건 상태와 거래 조건을 분명히 적어 안전한 거래를 도와주세요.", "tips": ["가격(바트), 상태, 거래 희망 지역을 확인해 주세요.", "송금 전 물건과 판매자 정보를 직접 확인하세요."]},
    "jobs": {"title": "구인구직 작성 안내", "description": "직무와 근무 조건을 투명하게 알려 구직자와 연결해 주세요.", "tips": ["근무지, 급여, 근무 시간, 지원 방법을 적어 주세요.", "비자·취업 자격은 공식 기관의 최신 안내를 확인하세요."]},
    "foodtravel": {"title": "맛집·여행 후기 작성 안내", "description": "직접 방문한 장소와 경험을 바탕으로 이웃에게 추천해 주세요.", "tips": ["장소명, 지역, 방문 시기와 가격대를 알려 주세요.", "광고·협찬이 있다면 관계를 밝혀 주세요."]},
    "living": {"title": "생활 질문 작성 안내", "description": "집, 통신, 은행 등 생활에 필요한 정보를 함께 찾아요.", "tips": ["도시·동네와 현재 상황을 알려 주면 답변에 도움이 돼요.", "계좌번호, 여권번호 등 민감 정보는 올리지 마세요."]},
    "visa": {"title": "비자·체류 정보 작성 안내", "description": "비자와 체류 경험을 나누되 기준과 날짜를 함께 적어 주세요.", "tips": ["비자 종류와 신청 시기를 밝혀 경험의 맥락을 알려 주세요.", "규정은 바뀔 수 있으니 공식 기관 안내도 함께 확인하세요."]},
    "travel": {"title": "교통·여행 정보 작성 안내", "description": "이동 경로와 여행 팁을 공유해 태국 여행을 더 편하게 만들어요.", "tips": ["출발·도착지, 이동 수단, 소요 시간과 비용을 적어 주세요.", "운행 시간과 요금은 방문 전에 다시 확인해 주세요."]},
}
def call_service(name, *args):
    try:
        return getattr(services, name)(*args)
    except APIPermissionDenied as exc:
        raise PermissionDenied from exc
    except APINotFound as exc:
        raise Http404 from exc

def post_editor_context(form, **extra):
    categories = dict(CATEGORIES)
    region_names = dict(REGIONS)
    category = form["category"].value() or "questions"
    return {
        "form": form,
        "board_name": categories.get(category, categories["questions"]),
        "region_name": region_names.get(form["region"].value(), REGIONS[0][1]),
        "board_guides": BOARD_GUIDES,
        "board_guide": BOARD_GUIDES.get(category, BOARD_GUIDES["questions"]),
        **extra,
    }


def published(user=None):
    return services.public_posts(user)

def back_url(request):
    query = request.GET.get("from", "")
    if query.startswith("?") and len(query) < 2000:
        return reverse("post-list") + query
    return reverse("post-list")

def home(request):
    from . import news
    question_posts = published(request.user).filter(category__in=RESOLUTION_CATEGORIES)
    posts = question_posts.order_by('-created_at', '-pk')[:4]
    helpful_posts = question_posts.filter(helpful_count__gt=0).order_by(
        '-helpful_count', '-created_at', '-pk'
    )[:4]
    feed_mode = 'helpful' if request.GET.get('feed') == 'helpful' else 'recent'
    context = {
        "posts": posts,
        "helpful_posts": helpful_posts,
        "community_posts": helpful_posts if feed_mode == 'helpful' else posts,
        "community_feed_mode": feed_mode,
    }
    if request.user.is_authenticated:
        membership = getattr(request.user, 'membership', None)
        if request.user.is_active and (membership is None or membership.is_complete):
            own_posts = services.activity(request.user, 'posts')
            saved_posts = services.activity(request.user, 'bookmarks')
            context['member_home'] = {
                'questions': own_posts.filter(category__in=RESOLUTION_CATEGORIES).count(),
                'answers': services.visible_comments(request.user).filter(author=request.user).count(),
                'saved': saved_posts.count(),
                'unread_answers': services.visible_notifications(request.user).filter(
                    kind=Notification.Kind.REPLY, is_read=False,
                ).count(),
                'saved_posts': saved_posts.select_related('author')[:3],
            }
    try:
        context["news_page"] = news.list_articles(page_size=5)
    except news.NewsUnavailable:
        context["news_error"] = "뉴스를 불러오지 못했습니다. 잠시 후 다시 확인해 주세요."
    return render_seo(
        request,
        "community/home.html",
        context,
        title="태국 교민 뉴스와 생활정보 | TeemoBKK POST",
        description="태국 소식은 한국어로 읽고, 비자·집·생활 정보는 이웃의 경험에서 찾아보세요.",
    )

def post_list(request):
    qs = published(request.user)
    resolution = request.GET.get('resolution', '')
    q = request.GET.get("q", "").strip()[:200]
    region, category = request.GET.get("region", ""), request.GET.get("category", "")
    requested_category = category
    if q:
        qs = services.search_posts(qs, q)
    if region in dict(REGIONS):
        qs = qs.filter(region__in=[region, "common"])
    if category in services.LIFE_BOARD_CATEGORIES:
        qs = qs.filter(category__in=services.LIFE_BOARD_CATEGORIES)
        category = Post.Category.LIVING
    elif category in dict(CATEGORIES):
        qs = qs.filter(category=category)
    can_filter_resolution = not category or category in RESOLUTION_CATEGORIES
    if can_filter_resolution and resolution in Post.Resolution.values:
        if not category:
            qs = qs.filter(category__in=RESOLUTION_CATEGORIES)
        qs = qs.filter(resolution=resolution)
    else:
        resolution = ""
    board_title, board_description = BOARD_COPY.get(
        requested_category, BOARD_COPY.get(category, DEFAULT_BOARD_COPY)
    )
    board_categories = BoardCategory.objects.filter(board=category)
    board_category = request.GET.get('board_category', '')
    if board_category:
        if board_category.isascii() and board_category.isdigit() and len(board_category) <= 18 and board_categories.filter(pk=board_category).exists():
            qs = qs.filter(board_category_id=board_category)
        else:
            qs = qs.none()
    qs = with_post_images(qs)
    pagination = Paginator(qs, 20).get_page(request.GET.get("page"))
    keep = request.GET.copy()
    keep.pop("page", None)
    if not can_filter_resolution or resolution not in Post.Resolution.values:
        keep.pop("resolution", None)
    is_question_board = category in RESOLUTION_CATEGORIES
    return render_seo(
        request,
        "community/list.html",
        {"resolution": resolution, "can_filter_resolution": can_filter_resolution, "is_question_board": is_question_board, "resolutions": Post.Resolution.choices, "page_obj": pagination, "q": q, "region": region, "category": category, "board_categories": board_categories, "board_category": board_category, "regions": REGIONS, "categories": CATEGORIES, "board_title": board_title, "board_description": board_description, "list_query": "?" + request.GET.urlencode(), "filter_query": keep.urlencode()},
        title="태국 교민 커뮤니티 | TeemoBKK POST",
        description=board_description,
    )


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
    if kind != 'comments':
        qs = with_post_images(qs)
    page = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'community/activity.html', {'page_obj': page, 'kind': kind})


@never_cache
def post_detail(request, pk):
    post = get_object_or_404(services.public_posts(request.user).prefetch_related(
        Prefetch('images', queryset=PostImage.objects.only('pk', 'post_id', 'image_url', 'position')),
    ), pk=pk)
    viewer = Exists(CommentLike.objects.filter(comment_id=OuterRef('pk'), user=request.user)) if request.user.is_authenticated else Value(False, output_field=BooleanField())
    visible = services.visible_comments(request.user, post).select_related('author', 'author__membership').annotate(like_count=Count('likes'), viewer_likes=viewer).order_by('created_at', 'pk')
    replies = visible.filter(parent__isnull=False)
    comments = visible.filter(parent__isnull=True).prefetch_related(Prefetch('replies', queryset=replies))
    body = post.display_body
    gallery_images = [
        image for image in post.images.all()
        if (image.image_url or reverse('post-image', args=[image.pk])) not in body
    ]
    return render_seo(request, "community/detail.html", {
        "post": post,
        "gallery_images": gallery_images,
        "has_resolution_status": post.has_resolution_status,
        "create_category": services.canonical_life_category(post.category),
        "comments": comments,
        "comment_form": CommentForm(),
        "report_form": ReportForm(),
        "back_url": back_url(request),
    }, title=f"{post.display_title} | 태국 교민 생활정보 | TeemoBKK POST",
        description=post.display_body, allow_from=True)


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


def finalize_inline_images(post, body, saved_images):
    rendered_body = replace_inline_upload_markers(body, saved_images)
    if rendered_body == body:
        return
    if len(rendered_body) > 6000:
        raise ValidationError({'body': '사진을 본문에 넣은 뒤 내용이 6,000자 제한을 넘어요. 본문을 조금 줄여 주세요.'})
    content_model = services.BOARD_CONTENT_MODELS.get(services.canonical_life_category(post.category))
    if content_model is not None:
        content_model.objects.filter(post_id=post.pk).update(body=rendered_body)
    else:
        Post.objects.filter(pk=post.pk).update(body=rendered_body)

@login_required
def post_create(request):
    if request.method == 'POST' and 'is_pinned' in request.POST and not request.user.is_staff:
        raise PermissionDenied
    category = request.GET.get('category', '')
    initial_category = category if category in dict(CATEGORIES) else 'questions'
    selected_category = category if category in dict(CATEGORIES) else ''
    form = PostForm(request.POST or None, request.FILES or None, initial={'category': initial_category}, staff=request.user.is_staff)
    if request.method == "POST" and form.is_valid():
        try:
            cleaned = form.cleaned_data
            data = {k: v for k, v in cleaned.items() if k not in {"privacy", "image_uploads", "image_urls", "remove_image_ids"}}
            with transaction.atomic():
                post = call_service("create_post", request.user, data)
                saved_images = save_post_images(post, cleaned.get('image_uploads', []), cleaned.get('image_urls', []))
                finalize_inline_images(post, cleaned.get('body', ''), saved_images)
            messages.success(request, "게시물을 등록했습니다.", extra_tags="post-saved")
            return redirect("post-detail", pk=post.pk)
        except (ValidationError, APIValidationError) as exc:
            service_error(form, exc)
    return render(request, "community/write.html", post_editor_context(
        form, editing=False, selected_category=selected_category,
    ))

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
    existing_images = list(post.images.only('pk', 'post_id', 'image_url', 'position'))
    form = PostForm(request.POST or None, request.FILES or None, initial={"board_category": post.board_category_id, "board_data_version": board_data_version(post), "title": post.display_title, "body": post.display_body, "region": post.region, "category": services.canonical_life_category(post.category), "is_pinned": post.is_pinned, "market_kind": post.market_kind, "market_price": post.market_price, "market_region": post.market_region, "market_status": post.market_status, "job_kind": post.job_kind, "job_region": post.job_region, "job_compensation": post.job_compensation, "job_status": post.job_status, "place_name": post.place_name, "place_region": post.place_region, "place_note": post.place_note, "place_url": post.place_url}, staff=request.user.is_staff, editing=True, existing_images=existing_images)
    if request.method == "POST" and form.is_valid():
        try:
            cleaned = form.cleaned_data
            data = {k: v for k, v in cleaned.items() if k not in {"privacy", "image_uploads", "image_urls", "remove_image_ids"}}
            with transaction.atomic():
                post = call_service("update_post", request.user, post, data)
                saved_images = save_post_images(post, cleaned.get('image_uploads', []), cleaned.get('image_urls', []), cleaned.get('remove_image_ids', []))
                finalize_inline_images(post, cleaned.get('body', ''), saved_images)
            messages.success(request, "게시물을 수정했습니다.", extra_tags="post-saved")
            return redirect("post-detail", pk=post.pk)
        except (ValidationError, APIValidationError) as exc:
            service_error(form, exc)
    if request.method == 'POST':
        post.refresh_from_db()
        data = form.data.copy()
        stale = data.get('board_data_version') != board_data_version(post)
        for prefix, category in (('market_', 'market'), ('job_', 'jobs'), ('place_', 'foodtravel')):
            for name in form.fields:
                if name.startswith(prefix) and data.get('category') != category and (name not in data or (post.category == category and data.get('board_fields_snapshot') != '1' and not data.get(name))):
                    data[name] = getattr(post, name) if getattr(post, name) is not None else ''
        data['board_data_version'] = data.get('board_data_version') if stale else board_data_version(post)
        data.pop('confirm_board_data_removal', None)
        form.data = data
    return render(request, "community/write.html", post_editor_context(form, editing=True, post=post, existing_images=existing_images))


@never_cache
@require_GET
def post_image(request, pk):
    image = get_object_or_404(PostImage.objects.only('pk', 'post_id', 'content_type'), pk=pk)
    if not services.public_posts(request.user).filter(pk=image.post_id).exists():
        raise Http404
    if image.image_data is None:
        raise Http404
    response = HttpResponse(bytes(image.image_data), content_type=image.content_type or 'image/jpeg')
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    response['Cache-Control'] = 'private, no-store'
    return response

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
