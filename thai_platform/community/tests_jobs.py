from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase

from . import services
from .forms import PostForm
from .models import Post
from .board_versions import board_data_version


from .test_board_fixtures import fixture_post

class JobBoardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="job-writer")
        self.client.force_login(self.user)

    def job_payload(self, title, **overrides):
        return {
            "title": title,
            "body": "구인구직 게시판에 올리는 상세한 안내입니다.",
            "region": "common",
            "category": "jobs",
            "privacy": "on",
            "job_kind": "hiring",
            "job_region": "bangkok",
            "job_compensation": "급여 협의 가능",
            "job_status": "open",
            **overrides,
        }

    def test_job_fields_are_available_when_category_changes(self):
        form = PostForm(initial={"category": "free"})
        for field_name in (
            "job_kind",
            "job_region",
            "job_compensation",
            "job_status",
        ):
            with self.subTest(field=field_name):
                self.assertIn(field_name, form.fields)

    def test_stale_same_category_api_and_web_edits_are_rejected(self):
        post = fixture_post(author=self.user, title='Concurrent edit', body='A sufficiently long job post description.', category='jobs', job_compensation='Original')
        version = self.client.get(f'/community/{post.pk}/edit/').context['form']['board_data_version'].value()
        updated = self.client.patch(f'/api/v1/posts/{post.pk}/', {'job_compensation': 'New salary'}, content_type='application/json')
        self.assertEqual(updated.status_code, 200)
        stale = self.client.patch(f'/api/v1/posts/{post.pk}/', {'job_compensation': 'Old salary', 'board_data_version': version}, content_type='application/json')
        self.assertEqual(stale.status_code, 400)
        response = self.client.post(f'/community/{post.pk}/edit/', self.job_payload('Concurrent edit', job_compensation='Old salary', board_data_version=version))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form']['board_data_version'].value(), version)
        retry = self.client.post(f'/community/{post.pk}/edit/', self.job_payload('Concurrent edit', job_compensation='Old salary', board_data_version=response.context['form']['board_data_version'].value()))
        self.assertEqual(retry.status_code, 200)
        post.refresh_from_db()
        self.assertEqual(post.job_compensation, 'New salary')

    def test_failed_non_js_switch_restores_stored_board_fields(self):
        post = fixture_post(author=self.user, title='Original job', body='A sufficiently long job post description.', category='jobs', job_compensation='Stored salary')
        payload = self.job_payload('Original job', category='free', job_compensation='', board_data_version=board_data_version(post))
        response = self.client.post(f'/community/{post.pk}/edit/', payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form']['job_compensation'].value(), 'Stored salary')

    def test_failed_switch_preserves_submitted_dirty_board_values(self):
        post = fixture_post(author=self.user, title='Original job', body='A sufficiently long job post description.', category='jobs', job_compensation='Stored salary', job_kind='hiring')
        payload = self.job_payload('Original job', category='free', job_compensation='Unsaved salary', job_kind='', board_data_version=board_data_version(post), board_fields_snapshot='1')
        response = self.client.post(f'/community/{post.pk}/edit/', payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form']['job_compensation'].value(), 'Unsaved salary')
        self.assertEqual(response.context['form']['job_kind'].value(), '')
        post.refresh_from_db()
        self.assertEqual((post.job_compensation, post.job_kind), ('Stored salary', 'hiring'))

    def test_edit_responses_are_private_and_not_stored(self):
        post = fixture_post(author=self.user, title='Private job', body='A sufficiently long job post description.', category='jobs')
        url = f'/community/{post.pk}/edit/'
        for response in (self.client.get(url), self.client.post(url, {}), self.client.post(url, self.job_payload('Private job', board_data_version=board_data_version(post)))):
            with self.subTest(status=response.status_code):
                self.assertIn('private', response['Cache-Control'])
                self.assertIn('no-store', response['Cache-Control'])

    def test_stale_api_confirmation_cannot_delete_new_details(self):
        post = fixture_post(author=self.user, title='Concurrent job', body='A sufficiently long job post description.', category='jobs', job_compensation='Original')
        snapshot = self.client.get(f'/api/v1/posts/{post.pk}/').json()['board_data_version']
        self.client.patch(f'/api/v1/posts/{post.pk}/', {'job_compensation': 'Updated by another session'}, content_type='application/json')
        response = self.client.patch(f'/api/v1/posts/{post.pk}/', {'category': 'free', 'confirm_board_data_removal': True, 'board_data_version': snapshot}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        post.refresh_from_db()
        self.assertEqual((post.category, post.job_compensation), ('jobs', 'Updated by another session'))

    def test_stale_web_session_requires_new_approval(self):
        post = fixture_post(author=self.user, title='Concurrent job web', body='A sufficiently long job post description.', category='jobs', job_compensation='Original')
        first = Client()
        second = Client()
        first.force_login(self.user)
        second.force_login(self.user)
        original = first.get(f'/community/{post.pk}/edit/').context['form']['board_data_version'].value()
        updated = second.patch(f'/api/v1/posts/{post.pk}/', {'job_compensation': 'New salary'}, content_type='application/json')
        self.assertEqual(updated.status_code, 200)
        payload = self.job_payload('Concurrent job web', category='free', board_data_version=original, confirm_board_data_removal='on')
        for name in ('job_kind', 'job_region', 'job_compensation', 'job_status'):
            payload.pop(name)
        response = first.post(f'/community/{post.pk}/edit/', payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['form']['confirm_board_data_removal'].value())
        self.assertEqual(response.context['form']['job_compensation'].value(), 'New salary')
        post.refresh_from_db()
        self.assertEqual((post.category, post.job_compensation), ('jobs', 'New salary'))
        payload['board_data_version'] = response.context['form']['board_data_version'].value()
        self.assertEqual(first.post(f'/community/{post.pk}/edit/', payload).status_code, 200)
        post.refresh_from_db()
        self.assertEqual((post.category, post.job_compensation), ('jobs', 'New salary'))
        payload['board_data_version'] = first.get(f'/community/{post.pk}/edit/').context['form']['board_data_version'].value()
        self.assertEqual(first.post(f'/community/{post.pk}/edit/', payload).status_code, 302)
        post.refresh_from_db()
        self.assertEqual((post.category, post.job_compensation), ('free', ''))

    def test_stale_category_switch_cannot_rebase_and_overwrite(self):
        post = fixture_post(author=self.user, title='Old title', body='Original content long enough for validation.', category='free', region='common')
        old = board_data_version(post)
        services.update_post(self.user, post, {
            'title': 'New saved title',
            'body': 'New saved content long enough for validation.',
        })
        payload = self.job_payload('Old draft title', body='Old draft content long enough for validation.', category='questions', board_data_version=old)
        for _ in range(2):
            response = self.client.post(f'/community/{post.pk}/edit/', payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['form']['board_data_version'].value(), old)
            payload['board_data_version'] = response.context['form']['board_data_version'].value()
        post.refresh_from_db()
        self.assertEqual(post.category, 'free')
        self.assertEqual(post.freepost.title, 'New saved title')
        self.assertEqual(post.freepost.body, 'New saved content long enough for validation.')

    def test_boolean_confirmation_without_version_is_rejected(self):
        post = fixture_post(author=self.user, title='No snapshot job', body='A sufficiently long job post description.', category='jobs', job_compensation='Keep me')
        response = self.client.patch(f'/api/v1/posts/{post.pk}/', {'category': 'free', 'confirm_board_data_removal': True}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        post.refresh_from_db()
        self.assertEqual((post.category, post.job_compensation), ('jobs', 'Keep me'))

    def test_stale_confirmation_cannot_delete_another_category(self):
        post = fixture_post(author=self.user, title='Concurrent categories', body='A sufficiently long job post description.', category='jobs', job_compensation='Original')
        version = self.client.get(f'/api/v1/posts/{post.pk}/').json()['board_data_version']
        change = self.client.patch(f'/api/v1/posts/{post.pk}/', {'category': 'market', 'market_kind': 'sell', 'market_price': '250.00', 'confirm_board_data_removal': True, 'board_data_version': version}, content_type='application/json')
        self.assertEqual(change.status_code, 200)
        stale = self.client.patch(f'/api/v1/posts/{post.pk}/', {'category': 'free', 'confirm_board_data_removal': True, 'board_data_version': version}, content_type='application/json')
        self.assertEqual(stale.status_code, 400)
        post.refresh_from_db()
        self.assertEqual((post.category, str(post.market_price)), ('market', '250.00'))

    def test_inactive_board_invalid_values_do_not_block_selected_category(self):
        form = PostForm(self.job_payload('Valid ordinary post', category='free', job_status='invalid', market_price='-1', place_url='javascript:bad'))
        self.assertTrue(form.is_valid(), form.errors)

    def test_category_change_requires_server_confirmation_for_web_and_api(self):
        post = fixture_post(author=self.user, title='Saved job post', body='A sufficiently long job post description.', category='jobs', job_compensation='Private negotiation')
        payload = self.job_payload('Saved job post', category='free')
        response = self.client.post(f'/community/{post.pk}/edit/', payload)
        self.assertEqual(response.status_code, 200)
        post.refresh_from_db()
        self.assertEqual((post.category, post.job_compensation), ('jobs', 'Private negotiation'))
        response = self.client.patch(f'/api/v1/posts/{post.pk}/', {'category': 'free'}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        post.refresh_from_db()
        self.assertEqual((post.category, post.job_compensation), ('jobs', 'Private negotiation'))
        response = self.client.patch(f'/api/v1/posts/{post.pk}/', {'category': 'free', 'confirm_board_data_removal': True, 'board_data_version': board_data_version(post)}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        post.refresh_from_db()
        self.assertEqual((post.category, post.job_compensation), ('free', ''))

    def test_web_category_change_requires_checkbox_and_privacy_confirmation(self):
        post = fixture_post(author=self.user, title='Saved web job', body='A sufficiently long job post description.', category='jobs', job_compensation='Negotiable')
        payload = self.job_payload('Saved web job', category='free', confirm_board_data_removal='on', board_data_version=board_data_version(post))
        payload.pop('privacy')
        self.assertEqual(self.client.post(f'/community/{post.pk}/edit/', payload).status_code, 200)
        post.refresh_from_db()
        self.assertEqual(post.job_compensation, 'Negotiable')
        payload['privacy'] = 'on'
        self.assertEqual(self.client.post(f'/community/{post.pk}/edit/', payload).status_code, 302)
        post.refresh_from_db()
        self.assertEqual((post.category, post.job_compensation), ('free', ''))

    def test_hiring_and_seeking_details_render(self):
        cases = (
            ("Hiring in Bangkok", "hiring", "bangkok", "급여 협의 가능", "open", "구인", "모집 중"),
            ("Seeking in Chiang Mai", "seeking", "chiangmai", "", "closed", "구직", "마감"),
        )
        for title, kind, region, compensation, status, kind_label, status_label in cases:
            with self.subTest(kind=kind):
                response = self.client.post(
                    "/community/new/",
                    self.job_payload(
                        title,
                        job_kind=kind,
                        job_region=region,
                        job_compensation=compensation,
                        job_status=status,
                    ),
                )
                self.assertEqual(response.status_code, 302)
                post = services.search_posts(Post.objects.all(), title).get()
                self.assertEqual(
                    (post.job_kind, post.job_region, post.job_compensation, post.job_status),
                    (kind, region, compensation, status),
                )
                detail = self.client.get(f"/community/{post.pk}/")
                self.assertContains(detail, kind_label)
                self.assertContains(detail, post.get_job_region_display())
                self.assertContains(detail, status_label)
                if compensation:
                    self.assertContains(detail, compensation)
                listing = self.client.get("/community/?category=jobs")
                self.assertContains(listing, title)
                self.assertContains(listing, kind_label)

        api_payload = self.job_payload(
            "API seeking post",
            job_kind="seeking",
            job_region="phuket",
            job_compensation="",
            job_status="open",
        )
        api_payload.pop("privacy")
        api_response = self.client.post(
            "/api/v1/posts/", api_payload, content_type="application/json"
        )
        self.assertEqual(api_response.status_code, 201)
        self.assertEqual(api_response.json()["job_kind"], "seeking")
        self.assertEqual(api_response.json()["job_region"], "phuket")

    def test_compensation_length_and_status_validation(self):
        invalid_cases = (
            ("Long compensation", {"job_compensation": "x" * 201}, "job_compensation"),
            ("Invalid job status", {"job_status": "pending"}, "job_status"),
        )
        for title, invalid, field_name in invalid_cases:
            with self.subTest(field=field_name):
                payload = self.job_payload(title, **invalid)
                web_response = self.client.post("/community/new/", payload)
                self.assertEqual(web_response.status_code, 200)
                self.assertFalse(services.search_posts(Post.objects.all(), title).exists())

                api_payload = {key: value for key, value in payload.items() if key != "privacy"}
                api_response = self.client.post(
                    "/api/v1/posts/", api_payload, content_type="application/json"
                )
                self.assertEqual(api_response.status_code, 400)
                self.assertIn(field_name, api_response.json())

    def test_non_job_payload_cannot_store_job_fields(self):
        web_payload = self.job_payload("Ordinary post with job fields", category="free")
        web_response = self.client.post("/community/new/", web_payload)
        self.assertEqual(web_response.status_code, 302)
        web_post = services.search_posts(Post.objects.all(), web_payload["title"]).get()
        self.assertEqual(
            (web_post.job_kind, web_post.job_region, web_post.job_compensation, web_post.job_status),
            ("", "", "", ""),
        )

        api_payload = {
            key: value
            for key, value in self.job_payload("API non-job post", category="free").items()
            if key != "privacy"
        }
        api_response = self.client.post(
            "/api/v1/posts/", api_payload, content_type="application/json"
        )
        self.assertEqual(api_response.status_code, 201)
        self.assertEqual(
            tuple(api_response.json()[key] for key in (
                "job_kind", "job_region", "job_compensation", "job_status"
            )),
            ("", "", "", ""),
        )

        job_post = services.create_post(
            self.user,
            {
                "title": "Move job post to another board",
                "body": "This job post has details before changing category.",
                "category": "jobs",
                "job_kind": "hiring",
                "job_region": "bangkok",
                "job_compensation": "Salary negotiable",
                "job_status": "open",
            },
        )
        services.update_post(self.user, job_post, {"category": "free", "job_kind": "seeking", "confirm_board_data_removal": True, "board_data_version": board_data_version(job_post)})
        job_post.refresh_from_db()
        self.assertEqual(job_post.category, "free")
        self.assertEqual(
            (job_post.job_kind, job_post.job_region, job_post.job_compensation, job_post.job_status),
            ("", "", "", ""),
        )


class JobMigrationPreservationTests(TransactionTestCase):
    reset_sequences = True

    def test_existing_post_rows_survive_job_migration(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        old_target = ('community', '0022_post_market_kind_post_market_price_and_more')
        try:
            executor.migrate([old_target])
            old_apps = executor.loader.project_state([old_target]).apps
            User = old_apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
            PostBefore = old_apps.get_model('community', 'Post')
            user = User.objects.create(username='legacy-job-row')
            legacy = PostBefore.objects.create(
                author_id=user.pk,
                title='Pre-existing job migration row',
                body='Original content must survive the migration.',
                category='visa',
                region='common',
            )
            old_pk = legacy.pk

            executor = MigrationExecutor(connection)
            executor.migrate(leaves)
            PostAfter = executor.loader.project_state(leaves).apps.get_model('community', 'Post')
            migrated = PostAfter.objects.get(pk=old_pk)
            self.assertEqual(
                (migrated.author_id, migrated.title, migrated.body, migrated.category, migrated.region),
                (user.pk, 'Pre-existing job migration row', 'Original content must survive the migration.', 'visa', 'common'),
            )
            self.assertEqual(
                (migrated.job_kind, migrated.job_region, migrated.job_compensation, migrated.job_status),
                ('', '', '', ''),
            )

            legacy_write = PostBefore.objects.create(
                author_id=user.pk,
                title='Legacy application insert after migration',
                body='An older release should keep writing posts.',
                category='jobs',
                region='common',
            )
            inserted = PostAfter.objects.get(pk=legacy_write.pk)
            self.assertEqual(
                (inserted.job_kind, inserted.job_region, inserted.job_compensation, inserted.job_status),
                ('', '', '', ''),
            )
        finally:
            MigrationExecutor(connection).migrate(leaves)
