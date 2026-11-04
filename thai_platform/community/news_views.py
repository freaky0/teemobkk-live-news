from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from urllib.parse import urlsplit
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied as APIPermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from config.seo import render_seo
from . import news, services
from .forms import NewsCommentForm
from .models import NewsComment, NewsLike

NOTICE='뉴스를 불러오지 못했습니다. 잠시 후 다시 확인해 주세요.'

def request_page(request):
    try:
        page=int(request.GET.get('page','1'))
        if page<1 or page>10000:
            raise ValueError
        return page
    except ValueError as exc:
        raise ValidationError({'page':'1부터 10000까지 정수를 입력하세요.'}) from exc


def listing(request):
    query=request.GET.get('q','').strip()[:200]
    category=request.GET.get('category','').strip()[:200]
    region_group=request.GET.get('region','').strip()[:32]
    try:
        page=request_page(request)
    except ValidationError:
        return render(request,'news/error.html',{'news_error':'페이지 번호를 확인해 주세요.'},status=400)
    try:
        result=news.list_articles(page=page,query=query,category=category,region_group=region_group,include_categories=True)
    except news.NewsUnavailable:
        return render(request,'news/error.html',{'news_error':NOTICE},status=503)
    return render_seo(
        request,
        'news/list.html',
        {'news_page':result,'query':query,'category':result.category,'region_group':result.region_group,'list_query':('?'+request.GET.urlencode()) if request.GET else ''},
        title='태국 최신 뉴스 | 태국 교민 뉴스 | TeemoBKK POST',
        description='태국 각지의 주요 소식을 한국어로 모았습니다. 방콕과 태국 북부·중부·남부의 최신 뉴스를 확인하세요.',
    )


def _summary_preview(summary, authenticated):
    text=str(summary or '').strip()
    if authenticated or len(text)<=100:
        return text,False

    limit=min(220,max(50,len(text)//2))
    if len(text)-limit<60:
        limit=max(50,len(text)-60)
    sentence_end=max(
        text.rfind('. ',0,limit),
        text.rfind('! ',0,limit),
        text.rfind('? ',0,limit),
        text.rfind('。',0,limit),
    )
    if sentence_end>=int(limit*.6) and len(text)-(sentence_end+1)>=60:
        limit=sentence_end+1
    else:
        word_end=text.rfind(' ',0,limit)
        if word_end>=int(limit*.7):
            limit=word_end
    return text[:limit].rstrip(),True


def _detail_context(request, article, back_url, comment_form=None, root_news_layout=False):
    article_id=article['id']
    detail_next_url=request.get_full_path()
    if root_news_layout and request.GET.get('presentation')!='root':
        detail_next_url+=('&' if '?' in detail_next_url else '?')+'presentation=root'
    summary_preview,has_summary_continuation=_summary_preview(
        article.get('summary',''),request.user.is_authenticated,
    )
    return {
        'article':article,
        'summary_preview':summary_preview,
        'has_summary_continuation':has_summary_continuation,
        'back_url':back_url,
        'like_count':NewsLike.objects.filter(article_id=article_id).count(),
        'liked_by_user':request.user.is_authenticated and NewsLike.objects.filter(article_id=article_id,user=request.user).exists(),
        'comments':NewsComment.objects.filter(article_id=article_id,status=NewsComment.Status.PUBLISHED).select_related('author'),
        'comment_form':comment_form or NewsCommentForm(),
        'root_news_layout':root_news_layout,
        'detail_next_url':detail_next_url,
    }


def _from_root_news_site(request):
    referrer=request.META.get('HTTP_REFERER','')
    try:
        parsed=urlsplit(referrer)
    except ValueError:
        return False
    if (parsed.scheme not in {'http','https'} or parsed.username or parsed.password
            or parsed.netloc.lower()!=request.get_host().lower()):
        return False
    path=parsed.path.rstrip('/') or '/'
    root_sections=('/news','/perspectives','/blog','/indicators','/tradingtalk','/lab')
    return path=='/' or any(path==section or path.startswith(section+'/') for section in root_sections)


def detail(request,article_id,comment_form=None,status=200):
    try:
        article=news.get_article(article_id)
    except news.NewsUnavailable:
        return render(request,'news/error.html',{'news_error':NOTICE},status=503)
    if not article:
        raise Http404
    root_news_layout=request.GET.get('presentation')=='root' or _from_root_news_site(request)
    origin=request.GET.get('from','')
    news_url=reverse('news-list')
    back_url=('/news/' if root_news_layout else
              news_url+origin if origin.startswith('?') and len(origin)<2000 else news_url)
    return render_seo(
        request,
        'news/detail.html',
        _detail_context(request,article,back_url,comment_form,root_news_layout),
        title=(f"{article['title']} | TeemoBKK" if root_news_layout else
               f"{article['title']} | 태국 뉴스 | TeemoBKK POST"),
        description=article.get('summary', ''),
        status=status,
        allow_from=True,
    )


def _require_active_member(user):
    try:
        services.require_active(user)
    except APIPermissionDenied as exc:
        raise PermissionDenied from exc


def _detail_redirect(request, article_id):
    url=reverse('news-detail',kwargs={'article_id':article_id})
    if request.GET.get('presentation')=='root':
        url+='?presentation=root'
    return redirect(url)


@login_required
@require_POST
@transaction.atomic
def news_like_toggle(request,article_id):
    try:
        article=news.get_article(article_id)
    except news.NewsUnavailable:
        return render(request,'news/error.html',{'news_error':NOTICE},status=503)
    if not article:
        raise Http404
    _require_active_member(request.user)
    like=NewsLike.objects.filter(article_id=article_id,user=request.user).first()
    if like:
        like.delete()
    else:
        NewsLike.objects.get_or_create(article_id=article_id,user=request.user)
    return _detail_redirect(request,article_id)


@login_required
@require_POST
def news_comment_create(request,article_id):
    try:
        article=news.get_article(article_id)
    except news.NewsUnavailable:
        return render(request,'news/error.html',{'news_error':NOTICE},status=503)
    if not article:
        raise Http404
    _require_active_member(request.user)
    form=NewsCommentForm(request.POST)
    if not form.is_valid():
        form.fields['body'].widget.attrs.update({'aria-invalid':'true','aria-describedby':'news-comment-error'})
        return detail(request,article_id,comment_form=form,status=400)
    NewsComment.objects.create(article_id=article_id,author=request.user,body=form.cleaned_data['body'])
    messages.success(request,'댓글을 등록했습니다.')
    return _detail_redirect(request,article_id)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_list(request):
    page=request_page(request)
    query=request.GET.get('q','').strip()[:200]
    category=request.GET.get('category','').strip()[:200]
    region_group=request.GET.get('region','').strip()[:32]
    try:
        result=news.list_articles(
            page=page,
            query=query,
            category=category,
            region_group=region_group,
            include_categories=bool(category),
        )
    except news.NewsUnavailable:
        return Response({'detail':NOTICE},status=503)
    return Response({'count':result.total,'page':result.page,'page_size':result.page_size,'has_next':result.has_next,'results':result.items})


@api_view(['GET'])
@permission_classes([AllowAny])
def api_detail(request,article_id):
    try:
        article=news.get_article(article_id)
    except news.NewsUnavailable:
        return Response({'detail':NOTICE},status=503)
    if not article:
        raise Http404
    return Response(article)
