from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

SESSION_KEY = 'post_login_return'


def safe_return(request, value):
    if not isinstance(value, str) or not value.startswith('/'):
        return ''
    if not url_has_allowed_host_and_scheme(value, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return ''
    return value


def remember_return(request):
    if 'next' in request.GET:
        value = safe_return(request, request.GET.get('next'))
        if value:
            request.session[SESSION_KEY] = value
        else:
            request.session.pop(SESSION_KEY, None)


def finish_login(request, complete):
    if not complete:
        return reverse('member-onboarding')
    return safe_return(request, request.session.pop(SESSION_KEY, '')) or reverse('home')
