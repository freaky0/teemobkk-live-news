from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from urllib.parse import parse_qs, urlencode, urlsplit
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


def _listing(request, region='태국', economic_news=False):
    query=request.GET.get('q','').strip()[:200]
    category=request.GET.get('category','').strip()[:200]
    region_group='' if economic_news else request.GET.get('region','').strip()[:32]
    try:
        page=request_page(request)
    except ValidationError:
        return render(request,'news/error.html',{'news_error':'페이지 번호를 확인해 주세요.'},status=400)
    try:
        result=news.list_articles(
            page=page,query=query,category=category,region_group=region_group,
            include_categories=True,region=region,
        )
    except news.NewsUnavailable:
        return render(request,'news/error.html',{'news_error':NOTICE},status=503)
    list_params={}
    if economic_news:
        list_params['feed']='global'
    if query:
        list_params['q']=query
    if category:
        list_params['category']=category
    if region_group:
        list_params['region']=region_group
    if page>1:
        list_params['page']=page
    return render_seo(
        request,
        'news/list.html',
        {
            'news_page':result,'query':query,'category':result.category,
            'region_group':result.region_group,
            'list_query':('?'+urlencode(list_params)) if list_params else '',
            'economic_news':economic_news,
            'news_feed':'global' if economic_news else '',
        },
        title=('경제 뉴스 | TeemoBKK POST' if economic_news else
               '태국 최신 뉴스 | 태국 교민 뉴스 | TeemoBKK POST'),
        description=('세계 경제와 금융 시장의 주요 뉴스를 태국 교민 사이트의 뉴스 화면에서 확인하세요.' if economic_news else
                     '태국 각지의 주요 소식을 한국어로 모았습니다. 방콕과 태국 북부·중부·남부의 최신 뉴스를 확인하세요.'),
    )


def listing(request):
    return _listing(request)


def economic_listing(request):
    return _listing(request,region='글로벌',economic_news=True)


def _summary_preview(summary, authenticated, max_preview=220):
    text=str(summary or '').strip()
    if authenticated or len(text)<=max_preview:
        return text,False

    limit=min(max_preview,max(50,len(text)//2))
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


def _detail_context(request, article, back_url, comment_form=None, root_news_layout=False,
                    economic_news_context=False):
    article_id=article['id']
    detail_next_url=request.get_full_path()
    if root_news_layout and request.GET.get('presentation')!='root':
        detail_next_url+=('&' if '?' in detail_next_url else '?')+'presentation=root'
    summary_preview,has_summary_continuation=_summary_preview(
        article.get('summary',''),request.user.is_authenticated,
    )
    article_body_preview,has_article_continuation=_summary_preview(
        article.get('full_text',''),request.user.is_authenticated,max_preview=900,
    )
    return {
        'article':article,
        'summary_preview':summary_preview,
        'has_summary_continuation':has_summary_continuation,
        'article_body_preview':article_body_preview,
        'has_article_continuation':has_article_continuation,
        'back_url':back_url,
        'like_count':NewsLike.objects.filter(article_id=article_id).count(),
        'liked_by_user':request.user.is_authenticated and NewsLike.objects.filter(article_id=article_id,user=request.user).exists(),
        'comments':NewsComment.objects.filter(article_id=article_id,status=NewsComment.Status.PUBLISHED).select_related('author'),
        'comment_form':comment_form or NewsCommentForm(),
        'root_news_layout':root_news_layout,
        'economic_news_context':economic_news_context,
        'origin_query':request.GET.get('from',''),
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


def _from_economic_news_list(origin):
    if not isinstance(origin,str) or len(origin)>2000:
        return False
    try:
        return parse_qs(urlsplit(origin).query).get('feed')==['global']
    except ValueError:
        return False


def detail(request,article_id,comment_form=None,status=200):
    try:
        article=news.get_article(article_id,include_full_text=True)
    except news.NewsUnavailable:
        return render(request,'news/error.html',{'news_error':NOTICE},status=503)
    if not article:
        raise Http404
    root_news_layout=request.GET.get('presentation')=='root' or _from_root_news_site(request)
    origin=request.GET.get('from','')
    news_url=reverse('news-list')
    economic_news_context=not root_news_layout and _from_economic_news_list(origin)
    back_url=('/news/' if root_news_layout else
              reverse('economic-news-list')+origin if economic_news_context and origin.startswith('?') else
              news_url+origin if origin.startswith('?') and len(origin)<2000 else news_url)
    return render_seo(
        request,
        'news/detail.html',
        _detail_context(request,article,back_url,comment_form,root_news_layout,economic_news_context),
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
    elif _from_economic_news_list(request.GET.get('from','')):
        url+='?'+urlencode({'from':request.GET.get('from','')})
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
    economic_feed=request.GET.get('feed')=='global'
    try:
        result=news.list_articles(
            page=page,
            query=query,
            category=category,
            region_group='' if economic_feed else region_group,
            include_categories=bool(category),
            region='글로벌' if economic_feed else '태국',
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
