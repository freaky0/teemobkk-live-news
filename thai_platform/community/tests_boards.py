from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied
from . import services
from .forms import PostForm
from .models import Post, LivingPost, NoticePost
from .board_versions import board_data_version


class BoardTests(TestCase):
    def test_each_new_board_can_create_filter_and_edit(self):
        user = get_user_model().objects.create_user(username='writer')
        self.client.force_login(user)
        for category in ('free', 'questions', 'market', 'jobs', 'foodtravel'):
            with self.subTest(category=category):
                form = self.client.get(f'/community/new/?category={category}')
                self.assertEqual(form.context['form']['category'].value(), category)
                payload = {'title': f'Test {category} post', 'body': 'This is a sufficiently long community post.', 'region': 'common', 'category': category, 'privacy': 'on'}
                response = self.client.post('/community/new/', payload)
                self.assertEqual(response.status_code, 302)
                post = Post.objects.get(pk=int(response.url.rstrip('/').split('/')[-1]))
                self.assertEqual(post.category, category)
                self.assertContains(self.client.get(f'/community/?category={category}'), payload['title'])
                payload['title'] = f'Edited {category} post'
                payload['board_data_version'] = board_data_version(post)
                self.assertEqual(self.client.post(f'/community/{post.pk}/edit/', payload).status_code, 302)
                post.refresh_from_db()
                self.assertEqual(post.category, category)
                self.assertEqual(post.display_title, payload['title'])

    def test_board_links_and_legacy_posts_remain_accessible(self):
        user = get_user_model().objects.create_user(username='writer')
        legacy = Post.objects.create(author=user, title='Legacy question', body='Old content', category='visa')
        response = self.client.get('/community/')
        for category in ('notice', 'free', 'questions', 'market', 'jobs', 'foodtravel', 'living', 'visa'):
            self.assertContains(response, f'category={category}')
        self.assertContains(self.client.get('/community/?category=visa'), legacy.title)
        self.assertEqual(Post.objects.get(pk=legacy.pk).category, 'visa')

    def test_life_categories_share_one_board_without_rewriting_legacy_rows(self):
        user = get_user_model().objects.create_user(username='life-board-writer')
        posts = {}
        for category in ('living', 'housing', 'banking'):
            posts[category] = Post.objects.create(
                author=user,
                title=f'Legacy {category} topic',
                body='Existing community content stays unchanged.',
                category=category,
            )
            LivingPost.objects.create(post=posts[category], title=posts[category].title, body=posts[category].body)

        board = self.client.get('/community/?category=living')
        self.assertEqual(board.status_code, 200)
        self.assertEqual(board.context['category'], 'living')
        for post in posts.values():
            self.assertContains(board, post.title)
            self.assertContains(board, '생활 질문')
        self.assertContains(board, '?category=living')
        self.assertNotContains(board, '?category=housing')
        self.assertNotContains(board, '?category=banking')

        for legacy_category in ('housing', 'banking'):
            legacy_link = self.client.get(f'/community/?category={legacy_category}')
            self.assertEqual(legacy_link.context['category'], 'living')
            for post in posts.values():
                self.assertContains(legacy_link, post.title)

        self.assertEqual(
            {post.pk: Post.objects.get(pk=post.pk).category for post in posts.values()},
            {post.pk: category for category, post in posts.items()},
        )

    def test_new_life_posts_use_only_the_canonical_category(self):
        self.assertIn(('living', '생활 질문'), list(PostForm().fields['category'].choices))
        self.assertNotIn('housing', dict(PostForm().fields['category'].choices))
        self.assertNotIn('banking', dict(PostForm().fields['category'].choices))

        user = get_user_model().objects.create_user(username='canonical-life-writer')
        for legacy_category in ('housing', 'banking'):
            with self.subTest(category=legacy_category):
                post = services.create_post(user, {
                    'title': f'New post via {legacy_category}',
                    'body': 'This new post should use the unified life board.',
                    'category': legacy_category,
                })
                self.assertEqual(post.category, 'living')

    def test_editing_legacy_life_post_opens_on_unified_category(self):
        user = get_user_model().objects.create_user(username='legacy-life-editor')
        self.client.force_login(user)
        post = Post.objects.create(
            author=user,
            title='Existing housing post',
            body='Existing housing content remains unchanged until saved.',
            category='housing',
        )
        LivingPost.objects.create(post=post, title=post.title, body=post.body)

        edit = self.client.get(f'/community/{post.pk}/edit/')
        self.assertEqual(edit.context['form']['category'].value(), 'living')
        post.refresh_from_db()
        self.assertEqual(post.category, 'housing')

        response = self.client.post(f'/community/{post.pk}/edit/', {
            'title': 'Updated housing post',
            'body': 'Existing housing content remains available after editing.',
            'region': 'common',
            'category': 'living',
            'privacy': 'on',
            'board_data_version': board_data_version(post),
        })
        self.assertEqual(response.status_code, 302)
        post.refresh_from_db()
        self.assertEqual((post.display_title, post.category), ('Updated housing post', 'living'))

    def test_notice_write_requires_moderator_and_prevents_category_bypass(self):
        User = get_user_model()
        member = User.objects.create_user(username='member')
        staff = User.objects.create_user(username='staff', is_staff=True)
        data = {'title': 'Notice title', 'body': 'Notice body', 'category': 'notice'}
        with self.assertRaises(PermissionDenied):
            services.create_post(member, data)
        notice = services.create_post(staff, data)
        self.assertContains(self.client.get('/community/?category=notice'), notice.display_title)
        with self.assertRaises(PermissionDenied):
            services.update_post(member, notice, {'category': 'living'})
        with self.assertRaises(PermissionDenied):
            services.delete_post(member, notice)
        ordinary = services.create_post(member, {'title': 'Normal title', 'body': 'Normal body', 'category': 'living'})
        with self.assertRaises(PermissionDenied):
            services.update_post(member, ordinary, {'category': 'notice'})

    def test_notice_api_and_web_reject_forged_member_writes(self):
        User = get_user_model()
        member = User.objects.create_user(username='member')
        staff = User.objects.create_user(username='staff', is_staff=True)
        notice = Post.objects.create(author=staff, title='Public notice', body='Public notice content', category='notice')
        ordinary = Post.objects.create(author=member, title='Ordinary post', body='Ordinary content', category='living')
        NoticePost.objects.create(post=notice, title=notice.title, body=notice.body)
        LivingPost.objects.create(post=ordinary, title=ordinary.title, body=ordinary.body)
        self.client.force_login(member)
        payload = {'title': 'Forged notice', 'body': 'This content is long enough for the form.', 'region': 'common', 'category': 'notice', 'privacy': 'on'}
        payload['board_data_version'] = board_data_version(ordinary)
        self.assertEqual(self.client.post('/community/new/', payload).status_code, 403)
        self.assertEqual(self.client.post(f'/community/{notice.pk}/delete/').status_code, 403)
        self.assertEqual(self.client.post(f'/community/{ordinary.pk}/edit/', payload).status_code, 403)
        self.assertEqual(self.client.patch(f'/api/v1/posts/{ordinary.pk}/', data={'category': 'notice', 'board_data_version': board_data_version(ordinary)}, content_type='application/json').status_code, 403)
        self.assertEqual(self.client.delete(f'/api/v1/posts/{notice.pk}/').status_code, 403)
        ordinary.refresh_from_db(); notice.refresh_from_db()
        self.assertEqual(ordinary.category, 'living')
        self.assertEqual(notice.status, Post.Status.PUBLISHED)
