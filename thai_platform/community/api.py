from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter
from . import services
from .models import Post, Report
from .serializers import CommentSerializer, PostSerializer, ReportSerializer


class CommunityPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ActiveWritePermission(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user.is_authenticated and request.user.is_active)


class StaffPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_active and request.user.is_staff)


class PostViewSet(viewsets.ModelViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [ActiveWritePermission]
    pagination_class = CommunityPagination
    serializer_class = PostSerializer
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = Post.objects.filter(status=Post.Status.PUBLISHED)
        if self.action != 'list':
            return qs
        params = self.request.query_params
        resolution = params.get('resolution')
        if resolution:
            if resolution not in Post.Resolution.values:
                raise ValidationError({'resolution': 'Invalid resolution.'})
            qs = qs.filter(resolution=resolution)
        region, category, query = params.get('region'), params.get('category'), params.get('q')
        if region:
            if region not in Post.Region.values:
                raise ValidationError({'region': 'Invalid region.'})
            qs = qs.filter(region__in=[region, Post.Region.COMMON])
        if category:
            if category not in Post.Category.values:
                raise ValidationError({'category': 'Invalid category.'})
            qs = qs.filter(category=category)
        if query:
            qs = qs.filter(Q(title__icontains=query) | Q(body__icontains=query))
        return qs

    def create(self, request, *args, **kwargs):
        post = services.create_post(request.user, request.data)
        return Response(PostSerializer(post).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        post = services.update_post(request.user, self.get_object(), request.data)
        return Response(PostSerializer(post).data)

    def destroy(self, request, *args, **kwargs):
        services.delete_post(request.user, self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def resolution(self, request, pk=None):
        post = services.set_resolution(request.user, self.get_object(), request.data)
        return Response(PostSerializer(post).data)

    @action(detail=True, methods=['get', 'post'])
    def comments(self, request, pk=None):
        post = self.get_object()
        if request.method == 'POST':
            comment = services.create_comment(request.user, post, request.data)
            return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)
        qs = post.comments.filter(status='published')
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(CommentSerializer(page, many=True).data)

    @action(detail=True, methods=['post'])
    def reports(self, request, pk=None):
        report = services.create_report(request.user, self.get_object(), request.data)
        # Acknowledgement only; confidential contents are staff-only.
        return Response({'id': report.pk, 'status': report.status}, status=status.HTTP_201_CREATED)


class ReportViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [StaffPermission]
    pagination_class = CommunityPagination
    serializer_class = ReportSerializer
    queryset = Report.objects.all()
    http_method_names = ['get', 'patch', 'head', 'options']

    def partial_update(self, request, *args, **kwargs):
        report = services.resolve_report(request.user, self.get_object(), request.data)
        return Response(ReportSerializer(report).data)


router = DefaultRouter()
router.register('posts', PostViewSet, basename='post')
router.register('reports', ReportViewSet, basename='report')
urlpatterns = router.urls
