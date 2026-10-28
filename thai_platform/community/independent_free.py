"""Isolated free-board vertical slice; legacy routes remain separate."""
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET
from rest_framework.exceptions import PermissionDenied as ServicePermissionDenied

from . import services
from .models import FreePost, Post


class FreePostForm(forms.Form):
    title = forms.CharField(max_length=100)
    body = forms.CharField(max_length=6000, widget=forms.Textarea)


def visible_entries(user):
    entries = FreePost.objects.filter(post__status=Post.Status.PUBLISHED).select_related('post', 'post__author').order_by('-post__created_at', '-post_id')
    blocked = services.blocked_member_ids(user)
    return entries.exclude(post__author_id__in=blocked) if blocked is not None else entries


@require_GET
def listing(request):
    return render(request, 'community/independent_free_list.html', {'entries': visible_entries(request.user)})


@require_GET
def detail(request, pk):
    entry = get_object_or_404(visible_entries(request.user), pk=pk)
    return render(request, 'community/independent_free_detail.html', {'entry': entry})


@login_required
def create(request):
    try:
        services.require_active(request.user)
    except ServicePermissionDenied as exc:
        raise PermissionDenied from exc
    form = FreePostForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            identity = Post.objects.create(author=request.user, category=Post.Category.FREE, title='', body='')
            entry = FreePost.objects.create(post=identity, **form.cleaned_data)
            services._audit(request.user, 'post.create', identity)
        return redirect('independent-free-detail', pk=entry.pk)
    return render(request, 'community/independent_free_form.html', {'form': form})


@login_required
def edit(request, pk):
    entry = get_object_or_404(visible_entries(request.user), pk=pk)
    try:
        services.require_owner(request.user, entry.post)
    except ServicePermissionDenied as exc:
        raise PermissionDenied from exc
    form = FreePostForm(request.POST or None, initial={'title': entry.title, 'body': entry.body})
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            identity = Post.objects.select_for_update().get(pk=pk)
            try:
                services.require_owner(request.user, identity)
            except ServicePermissionDenied as exc:
                raise PermissionDenied from exc
            if identity.status != Post.Status.PUBLISHED:
                from django.http import Http404
                raise Http404
            FreePost.objects.filter(pk=pk).update(**form.cleaned_data)
            services._audit(request.user, 'post.update', identity)
        return redirect('independent-free-detail', pk=pk)
    return render(request, 'community/independent_free_form.html', {'form': form})
