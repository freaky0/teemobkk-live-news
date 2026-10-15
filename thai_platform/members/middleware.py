from django.conf import settings
from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
import logging
import re

class AuthBoundaryMiddleware(MiddlewareMixin):
    def process_request(self,request):
        if request.path.startswith(('/accounts/password/','/accounts/3rdparty/','/accounts/social/')):
            return render(request,'403.html',status=403)
        if request.user.is_authenticated and request.path.startswith('/accounts/'):
            request._post_private_account_response=True
    def process_response(self,request,response):
        if request.path.startswith(('/accounts/','/api/v1/me/')):
            response['Cache-Control']='no-store, private'
            # Django's HTTPS CSRF checks require a same-origin Referer when
            # Origin is absent. Tokens use fragments and are removed by JS.
            response['Referrer-Policy']='same-origin'
        return response

class AuthLogFilter(logging.Filter):
    def filter(self,record):
        # OAuth callback codes and any accidental account query tokens stay out
        # of development server access logs. Fragments never reach this layer.
        text=record.getMessage()
        record.msg=re.sub(r'(/accounts/[^\s?]*)\?[^\s]+',r'\1?[REDACTED]',text)
        record.args=()
        return True
