from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied as APIPermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
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
    try:
        page=request_page(request)
    except ValidationError:
        return render(request,'news/error.html',{'news_error':'페이지 번호를 확인해 주세요.'},status=400)
    try:
        result=news.list_articles(page=page,query=query)
    except news.NewsUnavailable:
        return render(request,'news/error.html',{'news_error':NOTICE},status=503)
    return render(request,'news/list.html',{'news_page':result,'query':query,'list_query':('?'+request.GET.urlencode()) if request.GET else ''})


def _detail_context(request, article, back_url, comment_form=None):
    article_id=article['id']
    return {
        'article':article,
        'back_url':back_url,
        'like_count':NewsLike.objects.filter(article_id=article_id).count(),
        'liked_by_user':request.user.is_authenticated and NewsLike.objects.filter(article_id=article_id,user=request.user).exists(),
        'comments':NewsComment.objects.filter(article_id=article_id,status=NewsComment.Status.PUBLISHED).select_related('author'),
        'comment_form':comment_form or NewsCommentForm(),
    }


def detail(request,article_id,comment_form=None,status=200):
    try:
        article=news.get_article(article_id)
    except news.NewsUnavailable:
        return render(request,'news/error.html',{'news_error':NOTICE},status=503)
    if not article:
        raise Http404
    origin=request.GET.get('from','')
    news_url=reverse('news-list')
    back_url=news_url+origin if origin.startswith('?') and len(origin)<2000 else news_url
    return render(request,'news/detail.html',_detail_context(request,article,back_url,comment_form),status=status)


def _require_active_member(user):
    try:
        services.require_active(user)
    except APIPermissionDenied as exc:
        raise PermissionDenied from exc


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
    return redirect('news-detail',article_id=article_id)


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
    return redirect('news-detail',article_id=article_id)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_list(request):
    page=request_page(request)
    query=request.GET.get('q','').strip()[:200]
    try:
        result=news.list_articles(page=page,query=query)
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
