from django.http import Http404
from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from . import news

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


def detail(request,article_id):
    try:
        article=news.get_article(article_id)
    except news.NewsUnavailable:
        return render(request,'news/error.html',{'news_error':NOTICE},status=503)
    if not article:
        raise Http404
    origin=request.GET.get('from','')
    back_url='/news/'+origin if origin.startswith('?') and len(origin)<2000 else '/news/'
    return render(request,'news/detail.html',{'article':article,'back_url':back_url})


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
