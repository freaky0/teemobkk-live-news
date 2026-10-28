from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from members.models import MemberProfile

from .models import Comment, MemberBlock, Notification, Post


class BlockedContentVisibilityTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.blocker = user_model.objects.create_user(username="content-blocker")
        self.blocked = user_model.objects.create_user(username="content-author")
        self.other = user_model.objects.create_user(username="unrelated-viewer")
        now = timezone.now()
        for user, nickname in (
            (self.blocker, "차단자"),
            (self.blocked, "비공개 차단 대상 이름"),
            (self.other, "다른 회원"),
        ):
            MemberProfile.objects.create(
                user=user,
                email_key=f"{user.username}@example.test",
                nickname_key=nickname,
                accepted_at=now,
                email_verified_at=now,
            )

        self.visible_post = Post.objects.create(
            author=self.other,
            title="Visible community question",
            body="Visible post body",
            category=Post.Category.LIVING,
        )
        self.blocked_post = Post.objects.create(
            author=self.blocked,
            title="Secret blocked post title",
            body="Secret blocked post body",
            category=Post.Category.LIVING,
        )
        self.blocked_comment = Comment.objects.create(
            post=self.visible_post,
            author=self.blocked,
            body="Secret blocked comment body",
        )
        self.blocked_reply = Comment.objects.create(
            post=self.visible_post,
            parent=self.blocked_comment,
            author=self.blocked,
            body="Secret blocked reply body",
        )
        self.reply_under_blocked_parent = Comment.objects.create(
            post=self.visible_post,
            parent=self.blocked_comment,
            author=self.other,
            body="Reply under hidden parent",
        )
        self.visible_comment = Comment.objects.create(
            post=self.visible_post,
            author=self.other,
            body="Visible comment body",
        )
        self.visible_reply = Comment.objects.create(
            post=self.visible_post,
            parent=self.visible_comment,
            author=self.other,
            body="Visible reply body",
        )

        self.client.force_login(self.blocker)
        self.api = APIClient()
        self.api.force_authenticate(self.blocker)

    def block_target(self):
        return MemberBlock.objects.get_or_create(blocker=self.blocker, blocked=self.blocked)

    def test_block_hides_target_posts_only_for_blocker(self):
        self.block_target()

        filtered_list = self.client.get(reverse("post-list"), {"q": "Secret blocked"})
        self.assertEqual(filtered_list.context["page_obj"].paginator.count, 0)
        self.assertNotContains(filtered_list, self.blocked_post.title)
        self.assertNotContains(filtered_list, self.blocked_post.body)

        home = self.client.get(reverse("home"))
        self.assertNotContains(home, self.blocked_post.title)
        self.assertNotContains(home, self.blocked_post.body)
        self.assertNotContains(home, "비공개 차단 대상 이름")

        blocked_api = self.api.get("/api/v1/posts/")
        self.assertEqual(blocked_api.status_code, 200)
        self.assertEqual(blocked_api.data["count"], 1)
        self.assertEqual(blocked_api.data["results"][0]["id"], self.visible_post.pk)
        self.assertNotIn(self.blocked_post.pk, [row["id"] for row in blocked_api.data["results"]])

        anonymous_list = Client().get(reverse("post-list"))
        self.assertContains(anonymous_list, self.blocked_post.title)
        self.assertContains(anonymous_list, "비공개 차단 대상 이름")
        anonymous_detail = Client().get(reverse("post-detail", args=[self.blocked_post.pk]))
        self.assertContains(anonymous_detail, self.blocked_post.body)
        anonymous_api = APIClient().get("/api/v1/posts/")
        self.assertEqual(anonymous_api.data["count"], 2)
        self.assertIn(self.blocked_post.pk, [row["id"] for row in anonymous_api.data["results"]])
        self.assertIn(self.blocked_post.body, str(anonymous_api.data))

        unrelated_api = APIClient()
        unrelated_api.force_authenticate(self.other)
        unrelated_response = unrelated_api.get("/api/v1/posts/")
        self.assertEqual(unrelated_response.data["count"], 2)
        self.assertIn(self.blocked_post.pk, [row["id"] for row in unrelated_response.data["results"]])

    def test_block_hides_comments_and_replies_in_detail_and_api(self):
        self.block_target()

        detail = self.client.get(reverse("post-detail", args=[self.visible_post.pk]))
        self.assertContains(detail, self.visible_comment.body)
        self.assertContains(detail, self.visible_reply.body)
        self.assertNotContains(detail, self.blocked_comment.body)
        self.assertNotContains(detail, self.blocked_reply.body)
        self.assertNotContains(detail, self.reply_under_blocked_parent.body)
        self.assertNotContains(detail, "비공개 차단 대상 이름")
        self.assertNotContains(detail, f"/community/members/{self.blocked.pk}/")

        blocked_api = self.api.get(f"/api/v1/posts/{self.visible_post.pk}/comments/")
        self.assertEqual(blocked_api.status_code, 200)
        self.assertEqual(blocked_api.data["count"], 2)
        ids = [row["id"] for row in blocked_api.data["results"]]
        self.assertEqual(set(ids), {self.visible_comment.pk, self.visible_reply.pk})
        self.assertNotIn(self.blocked.pk, [row["author"] for row in blocked_api.data["results"]])

        unrelated_api = APIClient()
        unrelated_api.force_authenticate(self.other)
        unrelated_response = unrelated_api.get(f"/api/v1/posts/{self.visible_post.pk}/comments/")
        self.assertEqual(unrelated_response.data["count"], 5)
        self.assertIn(self.blocked_comment.pk, [row["id"] for row in unrelated_response.data["results"]])
        self.assertIn(self.blocked_reply.pk, [row["id"] for row in unrelated_response.data["results"]])
        self.assertIn(self.reply_under_blocked_parent.pk, [row["id"] for row in unrelated_response.data["results"]])

        anonymous_response = APIClient().get(f"/api/v1/posts/{self.visible_post.pk}/comments/")
        self.assertEqual(anonymous_response.data["count"], 5)

    def test_block_hides_profile_activity_and_notification_hints(self):
        self.block_target()

        profile = self.client.get(f"/community/members/{self.blocked.pk}/")
        self.assertEqual(profile.status_code, 404)
        anonymous_profile = Client().get(f"/community/members/{self.blocked.pk}/")
        self.assertContains(anonymous_profile, self.blocked_post.title)
        self.assertContains(anonymous_profile, "비공개 차단 대상 이름")

        own_comment_on_blocked_post = Comment.objects.create(
            post=self.blocked_post,
            author=self.blocker,
            body="My answer on a blocked post",
        )
        own_reply_to_blocked_comment = Comment.objects.create(
            post=self.visible_post,
            parent=self.blocked_comment,
            author=self.blocker,
            body="My reply under a blocked answer",
        )
        own_visible_comment = Comment.objects.create(
            post=self.visible_post,
            author=self.blocker,
            body="My answer on a visible post",
        )
        activity = self.client.get("/community/activity/?kind=comments")
        self.assertContains(activity, own_visible_comment.body)
        self.assertNotContains(activity, own_comment_on_blocked_post.body)
        self.assertNotContains(activity, own_reply_to_blocked_comment.body)

        comment_on_blocked_post = Comment.objects.create(
            post=self.blocked_post,
            author=self.other,
            body="Comment on a blocked post",
        )
        blocked_comment_notice = Notification.objects.create(
            recipient=self.blocker,
            kind=Notification.Kind.REPLY,
            post=self.visible_post,
            comment=self.blocked_comment,
        )
        blocked_post_notice = Notification.objects.create(
            recipient=self.blocker,
            kind=Notification.Kind.REPLY,
            post=self.blocked_post,
            comment=comment_on_blocked_post,
        )
        visible_notice = Notification.objects.create(
            recipient=self.blocker,
            kind=Notification.Kind.REPLY,
            post=self.visible_post,
            comment=self.visible_comment,
        )
        notifications = self.client.get("/community/notifications/")
        visible_notification_ids = [item.pk for item in notifications.context["notifications"]]
        self.assertNotIn(blocked_comment_notice.pk, visible_notification_ids)
        self.assertNotIn(blocked_post_notice.pk, visible_notification_ids)
        self.assertIn(visible_notice.pk, visible_notification_ids)

        api_notifications = self.api.get("/api/v1/notifications/")
        self.assertEqual(api_notifications.data["count"], 1)
        self.assertEqual([item["id"] for item in api_notifications.data["results"]], [visible_notice.pk])
        self.assertEqual(
            self.client.post(f"/community/notifications/{blocked_comment_notice.pk}/read/").status_code,
            404,
        )
        self.assertEqual(
            self.api.post(f"/api/v1/notifications/{blocked_comment_notice.pk}/read/").status_code,
            404,
        )
        blocked_comment_notice.refresh_from_db()
        self.assertFalse(blocked_comment_notice.is_read)

        self.client.post(reverse("member-unblock", args=[self.blocked.pk]))
        restored_ids = [item.pk for item in self.client.get("/community/notifications/").context["notifications"]]
        self.assertIn(blocked_comment_notice.pk, restored_ids)
        restored_api = self.api.get("/api/v1/notifications/")
        self.assertEqual(restored_api.data["count"], 3)

    def test_direct_post_and_comment_routes_do_not_leak_blocked_content(self):
        self.block_target()

        blocked_detail = self.client.get(reverse("post-detail", args=[self.blocked_post.pk]))
        self.assertEqual(blocked_detail.status_code, 404)
        self.assertNotIn(self.blocked_post.title, blocked_detail.content.decode())
        self.assertNotIn("비공개 차단 대상 이름", blocked_detail.content.decode())

        blocked_api = self.api.get(f"/api/v1/posts/{self.blocked_post.pk}/")
        self.assertEqual(blocked_api.status_code, 404)
        self.assertNotIn(self.blocked_post.body, str(blocked_api.data))

        like_response = self.client.post(
            reverse("comment-like", args=[self.visible_post.pk, self.blocked_comment.pk]),
            {"active": "true"},
        )
        self.assertEqual(like_response.status_code, 404)

        web_reply = self.client.post(
            reverse("comment-create", args=[self.blocked_post.pk]),
            {"body": "Attempted reply to hidden post"},
        )
        self.assertEqual(web_reply.status_code, 404)
        api_reply = self.api.post(
            f"/api/v1/posts/{self.visible_post.pk}/comments/",
            {"body": "Attempted reply to blocked answer", "parent": self.blocked_comment.pk},
            format="json",
        )
        self.assertEqual(api_reply.status_code, 400)
        self.assertFalse(Comment.objects.filter(body__startswith="Attempted reply").exists())

    def test_unblock_restores_unchanged_content(self):
        self.block_target()
        self.assertContains(
            self.client.get("/community/blocks/"),
            "차단한 회원의 글과 답변은 나에게서 숨겨집니다.",
        )
        self.assertEqual(
            self.client.get(reverse("post-detail", args=[self.blocked_post.pk])).status_code,
            404,
        )
        hidden_detail = self.client.get(reverse("post-detail", args=[self.visible_post.pk]))
        self.assertNotContains(hidden_detail, self.blocked_comment.body)

        response = self.client.post(reverse("member-unblock", args=[self.blocked.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(MemberBlock.objects.filter(blocker=self.blocker, blocked=self.blocked).exists())

        self.assertContains(self.client.get(reverse("post-list")), self.blocked_post.title)
        restored_detail = self.client.get(reverse("post-detail", args=[self.visible_post.pk]))
        self.assertContains(restored_detail, self.blocked_comment.body)
        self.assertContains(restored_detail, self.blocked_reply.body)
        restored_comments = self.api.get(f"/api/v1/posts/{self.visible_post.pk}/comments/")
        self.assertEqual(restored_comments.data["count"], 5)

        self.blocked_post.refresh_from_db()
        self.blocked_comment.refresh_from_db()
        self.blocked_reply.refresh_from_db()
        self.assertEqual(self.blocked_post.title, "Secret blocked post title")
        self.assertEqual(self.blocked_comment.body, "Secret blocked comment body")
        self.assertEqual(self.blocked_reply.body, "Secret blocked reply body")

    def test_operator_hidden_content_remains_hidden_for_every_viewer(self):
        hidden_post = Post.objects.create(
            author=self.blocked,
            title="Operator hidden post secret",
            body="Operator hidden post body",
            status=Post.Status.HIDDEN,
        )
        hidden_comment = Comment.objects.create(
            post=self.visible_post,
            author=self.blocked,
            body="Operator hidden comment secret",
            status=Comment.Status.HIDDEN,
        )
        hidden_comment_notice = Notification.objects.create(
            recipient=self.other,
            kind=Notification.Kind.REPLY,
            post=self.visible_post,
            comment=hidden_comment,
        )
        hidden_post_comment = Comment.objects.create(
            post=hidden_post,
            author=self.other,
            body="Comment on operator-hidden post",
        )
        hidden_post_notice = Notification.objects.create(
            recipient=self.other,
            kind=Notification.Kind.REPLY,
            post=hidden_post,
            comment=hidden_post_comment,
        )
        self.block_target()

        viewers = [Client(), Client(), Client(), Client()]
        viewers[1].force_login(self.blocker)
        viewers[2].force_login(self.other)
        viewers[3].force_login(self.blocked)
        for client in viewers:
            post_list = client.get(reverse("post-list"))
            self.assertNotContains(post_list, hidden_post.title)
            self.assertNotContains(post_list, hidden_post.body)
            self.assertEqual(client.get(reverse("post-detail", args=[hidden_post.pk])).status_code, 404)
            detail = client.get(reverse("post-detail", args=[self.visible_post.pk]))
            self.assertNotContains(detail, hidden_comment.body)

        api_viewers = [APIClient(), APIClient(), APIClient(), APIClient()]
        api_viewers[1].force_authenticate(self.blocker)
        api_viewers[2].force_authenticate(self.other)
        api_viewers[3].force_authenticate(self.blocked)
        for client in api_viewers:
            hidden_posts = client.get("/api/v1/posts/")
            self.assertNotIn(hidden_post.pk, [row["id"] for row in hidden_posts.data["results"]])
            hidden_comments = client.get(f"/api/v1/posts/{self.visible_post.pk}/comments/")
            self.assertNotIn(hidden_comment.pk, [row["id"] for row in hidden_comments.data["results"]])

        other_web = Client()
        other_web.force_login(self.other)
        notification_ids = [
            item.pk
            for item in other_web.get("/community/notifications/").context["notifications"]
        ]
        self.assertNotIn(hidden_comment_notice.pk, notification_ids)
        self.assertNotIn(hidden_post_notice.pk, notification_ids)
        other_api = APIClient()
        other_api.force_authenticate(self.other)
        self.assertEqual(other_api.get("/api/v1/notifications/").data["count"], 0)
