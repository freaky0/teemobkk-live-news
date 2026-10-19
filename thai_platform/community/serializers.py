from rest_framework import serializers
from .models import Comment, Notification, Post, Report


class StrictInputMixin:
    """Reject unknown/read-only keys instead of silently discarding forged fields."""
    def to_internal_value(self, data):
        if not hasattr(data, 'keys'):
            raise serializers.ValidationError('Expected an object.')
        forbidden = set(data.keys()) - {name for name, field in self.fields.items() if not field.read_only}
        if forbidden:
            raise serializers.ValidationError({key: 'This field is not writable.' for key in sorted(forbidden)})
        return super().to_internal_value(data)


class PostInputSerializer(StrictInputMixin, serializers.ModelSerializer):
    body = serializers.CharField(max_length=6000)

    class Meta:
        model = Post
        fields = ['title', 'body', 'region', 'category']


class PostSerializer(serializers.ModelSerializer):
    author = serializers.IntegerField(source='author_id', read_only=True)
    helpful_count = serializers.IntegerField(read_only=True, default=0)
    helpful_active = serializers.BooleanField(read_only=True, default=False)
    bookmarked = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = Post
        fields = ['id', 'author', 'title', 'body', 'region', 'category', 'status', 'resolution', 'helpful_count', 'helpful_active', 'bookmarked', 'created_at', 'updated_at']
        read_only_fields = fields


class EngagementInputSerializer(StrictInputMixin, serializers.Serializer):
    active = serializers.BooleanField()


class PostResolutionSerializer(StrictInputMixin, serializers.Serializer):
    resolution = serializers.ChoiceField(choices=Post.Resolution.choices)


class CommentInputSerializer(StrictInputMixin, serializers.Serializer):
    body = serializers.CharField(max_length=3000)


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.IntegerField(source='author_id', read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'post', 'author', 'body', 'created_at', 'updated_at']
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
        fields = ['id', 'kind', 'post', 'comment', 'report', 'is_read', 'created_at']
        read_only_fields = fields


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ['id', 'reporter', 'post', 'comment', 'reason', 'details', 'status', 'created_at', 'updated_at']
        read_only_fields = fields
