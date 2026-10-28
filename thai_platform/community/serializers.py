from rest_framework import serializers
from .models import BoardCategory, Comment, ModerationAppeal, Notification, Post, Report
from .places import validate_external_place_url
from .board_versions import board_data_version


class StrictInputMixin:
    """Reject unknown/read-only keys instead of silently discarding forged fields."""
    def to_internal_value(self, data):
        if not hasattr(data, 'keys'):
            raise serializers.ValidationError('Expected an object.')
        forbidden = set(data.keys()) - {name for name, field in self.fields.items() if not field.read_only}
        if forbidden:
            raise serializers.ValidationError({key: 'This field is not writable.' for key in sorted(forbidden)})
        return super().to_internal_value(data)


class BoardCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BoardCategory
        fields = ['id', 'board', 'slug', 'name']
        read_only_fields = fields


class PostInputSerializer(StrictInputMixin, serializers.ModelSerializer):
    body = serializers.CharField(max_length=6000)
    confirm_board_data_removal = serializers.BooleanField(required=False, write_only=True)
    board_data_version = serializers.CharField(required=False, allow_blank=True, write_only=True)
    place_url = serializers.CharField(max_length=500, allow_blank=True, required=False)

    class Meta:
        model = Post
        fields = ['title', 'body', 'region', 'category', 'board_category', 'is_pinned', 'market_kind', 'market_price', 'market_region', 'market_status', 'job_kind', 'job_region', 'job_compensation', 'job_status', 'place_name', 'place_region', 'place_note', 'place_url', 'confirm_board_data_removal', 'board_data_version']

    def validate_place_url(self, value):
        return validate_external_place_url(value)


class PostSerializer(serializers.ModelSerializer):
    board_data_version = serializers.SerializerMethodField()

    def get_board_data_version(self, obj):
        return board_data_version(obj)
    author = serializers.IntegerField(source='author_id', read_only=True)
    helpful_count = serializers.IntegerField(read_only=True, default=0)
    helpful_active = serializers.BooleanField(read_only=True, default=False)
    bookmarked = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = Post
        fields = ['id', 'author', 'title', 'body', 'region', 'category', 'board_category', 'is_pinned', 'market_kind', 'market_price', 'market_region', 'market_status', 'job_kind', 'job_region', 'job_compensation', 'job_status', 'place_name', 'place_region', 'place_note', 'place_url', 'status', 'resolution', 'helpful_count', 'helpful_active', 'bookmarked', 'created_at', 'updated_at', 'board_data_version']
        read_only_fields = fields


class EngagementInputSerializer(StrictInputMixin, serializers.Serializer):
    active = serializers.BooleanField()


class PostResolutionSerializer(StrictInputMixin, serializers.Serializer):
    resolution = serializers.ChoiceField(choices=Post.Resolution.choices)


class CommentInputSerializer(StrictInputMixin, serializers.Serializer):
    body = serializers.CharField(max_length=3000)
    parent = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.IntegerField(source='author_id', read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'post', 'parent', 'author', 'body', 'created_at', 'updated_at']
        read_only_fields = fields


class ReportInputSerializer(StrictInputMixin, serializers.Serializer):
    reason = serializers.ChoiceField(choices=Report.Reason.choices)
    details = serializers.CharField(min_length=5, max_length=2000)
    comment = serializers.PrimaryKeyRelatedField(queryset=Comment.objects.filter(status='published', post__status='published'), required=False, allow_null=True)


class ReportResolutionSerializer(StrictInputMixin, serializers.Serializer):
    status = serializers.ChoiceField(choices=[Report.Status.RESOLVED, Report.Status.DISMISSED])


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'kind', 'post', 'comment', 'report', 'appeal', 'is_read', 'created_at']
        read_only_fields = fields


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ['id', 'reporter', 'post', 'comment', 'target_type', 'reason', 'details', 'status', 'created_at', 'updated_at']
        read_only_fields = fields


class AppealInputSerializer(StrictInputMixin, serializers.Serializer):
    post = serializers.PrimaryKeyRelatedField(queryset=Post.objects.all())
    comment = serializers.PrimaryKeyRelatedField(queryset=Comment.objects.all(), required=False, allow_null=True)
    details = serializers.CharField(min_length=5, max_length=2000)


class AppealSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModerationAppeal
        fields = ['id', 'post', 'comment', 'details', 'target_type', 'status', 'reviewed_at', 'created_at']
        read_only_fields = fields
