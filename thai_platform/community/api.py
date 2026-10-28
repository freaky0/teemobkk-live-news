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
from .models import BoardCategory, ModerationAppeal, Notification, Post, Report
from .serializers import AppealSerializer, BoardCategorySerializer, CommentSerializer, NotificationSerializer, PostSerializer, ReportSerializer


class CommunityPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ActiveWritePermission(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user.is_authenticated and request.user.is_active)


class ActiveUserPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_active)


class BoardCategoryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = BoardCategorySerializer
    pagination_class = CommunityPagination

    def get_queryset(self):
        qs = BoardCategory.objects.all()
        board = self.request.query_params.get('board')
        if board:
            if board not in dict(BoardCategory._meta.get_field('board').choices):
                raise ValidationError({'board': 'Invalid board.'})
            qs = qs.filter(board=board)
        return qs


class PostViewSet(viewsets.ModelViewSet):
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store, private'
        return response

    authentication_classes = [SessionAuthentication]
    permission_classes = [ActiveWritePermission]
    pagination_class = CommunityPagination
    serializer_class = PostSerializer
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = services.public_posts(self.request.user)
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
            qs = qs.filter(category__in=services.category_filter_values(category))
        board_category = params.get('board_category')
        if board_category:
            if not board_category.isascii() or not board_category.isdecimal() or len(board_category) > 18 or int(board_category) < 1:
                raise ValidationError({'board_category': 'Invalid category.'})
            qs = qs.filter(board_category_id=int(board_category))
        if query:
            qs = services.search_posts(qs, query)
        return qs

    def create(self, request, *args, **kwargs):
        post = services.create_post(request.user, request.data)
        return Response(PostSerializer(services.public_posts(request.user).get(pk=post.pk)).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        post = services.update_post(request.user, self.get_object(), request.data)
        return Response(PostSerializer(services.public_posts(request.user).get(pk=post.pk)).data)

    def destroy(self, request, *args, **kwargs):
        services.delete_post(request.user, self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def bookmark(self, request, pk=None):
        return Response(services.set_bookmark(request.user, self.get_object(), request.data))

    @action(detail=True, methods=['post'])
    def helpful(self, request, pk=None):
        return Response(services.set_helpful(request.user, self.get_object(), request.data))

    @action(detail=True, methods=['post'])
    def resolution(self, request, pk=None):
        post = services.set_resolution(request.user, self.get_object(), request.data)
        return Response(PostSerializer(services.public_posts(request.user).get(pk=post.pk)).data)

    @action(detail=True, methods=['get', 'post'])
    def comments(self, request, pk=None):
        post = self.get_object()
        if request.method == 'POST':
            comment = services.create_comment(request.user, post, request.data)
            return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)
        qs = services.visible_comments(request.user, post)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(CommentSerializer(page, many=True).data)

    @action(detail=True, methods=['post'])
    def reports(self, request, pk=None):
        report = services.create_report(request.user, self.get_object(), request.data)
        # Acknowledgement only; confidential contents are staff-only.
        return Response({'id': report.pk, 'status': report.status}, status=status.HTTP_201_CREATED)


class ReportModeratorPermission(BasePermission):
    def has_permission(self, request, view):
        return services.is_report_moderator(request.user)


class ReportViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store, private'
        return response

    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportModeratorPermission]
    pagination_class = CommunityPagination
    serializer_class = ReportSerializer
    queryset = Report.objects.all()
    http_method_names = ['get', 'patch', 'post', 'head', 'options']

    def partial_update(self, request, *args, **kwargs):
        report = services.resolve_report(request.user, self.get_object(), request.data)
        return Response(ReportSerializer(report).data)

    @action(detail=True, methods=['post'])
    def hide(self, request, pk=None):
        report = services.hide_reported_content(request.user, self.get_object())
        return Response(ReportSerializer(report).data)


class AppealViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store, private'
        return response

    authentication_classes = [SessionAuthentication]
    permission_classes = [ActiveUserPermission]
    pagination_class = CommunityPagination
    serializer_class = AppealSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        return ModerationAppeal.objects.filter(author=self.request.user).select_related('post', 'comment')

    def create(self, request, *args, **kwargs):
        appeal = services.create_appeal(request.user, request.data)
        return Response(AppealSerializer(appeal).data, status=status.HTTP_201_CREATED)


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [ActiveUserPermission]
    pagination_class = CommunityPagination
    serializer_class = NotificationSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Notification.objects.none()
        return services.visible_notifications(self.request.user).select_related('post', 'comment', 'report', 'appeal')

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response['Cache-Control'] = 'no-store, private'
        return response

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        item = self.get_object()
        if not item.is_read:
            item.is_read = True
            item.save(update_fields=['is_read', 'updated_at'])
        response = Response(NotificationSerializer(item).data)
        response['Cache-Control'] = 'no-store, private'
        return response


class ActivityViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    authentication_classes = [SessionAuthentication]
    pagination_class = CommunityPagination
    http_method_names = ['get', 'head', 'options']

    def list(self, request, *args, **kwargs):
        kind = request.query_params.get('kind', 'posts')
        qs = services.activity(request.user, kind)
        page = self.paginate_queryset(qs)
        serializer = CommentSerializer if kind == 'comments' else PostSerializer
        response = self.get_paginated_response(serializer(page, many=True).data)
        response['Cache-Control'] = 'no-store, private'
        return response


router = DefaultRouter()
router.register('board-categories', BoardCategoryViewSet, basename='board-category')
router.register('posts', PostViewSet, basename='post')
router.register('notifications', NotificationViewSet, basename='notification')
router.register('activity', ActivityViewSet, basename='activity')
router.register('reports', ReportViewSet, basename='report')
router.register('appeals', AppealViewSet, basename='appeal')
urlpatterns = router.urls
