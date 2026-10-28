"""Fixtures for posts created outside the application write service."""
from .models import Post
from .services import _sync_board_content


def fixture_post(**fields):
    post = Post.objects.create(**fields)
    _sync_board_content(post, post.title, post.body)
    return post
