from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from rest_framework.exceptions import ValidationError as APIValidationError
from rest_framework.test import APIClient

from . import services
from .forms import PostForm
from .models import Post
from .places import build_google_maps_search_url, validate_external_place_url


class AnchorCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.anchors.append(dict(attrs))


class FoodTravelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="place-writer")
        self.client.force_login(self.user)

    def food_payload(self, title="Place details", **overrides):
        return {
            "title": title,
            "body": "맛집이나 여행지를 소개하는 충분히 긴 글입니다.",
            "region": "common",
            "category": "foodtravel",
            "place_name": "카페 & ร้านกาแฟ?",
            "place_region": "bangkok",
            "place_note": "현지인이 추천한 장소",
            "place_url": "https://example.com/place?id=1&view=map",
            **overrides,
        }

    def test_google_maps_search_url_encodes_unicode_and_reserved_chars(self):
        place_name = "카페 & ร้านกาแฟ?"
        region = "Bangkok / 방콕"
        url = build_google_maps_search_url(place_name, region)
        parsed = urlparse(url)

        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "www.google.com")
        self.assertEqual(parsed.path, "/maps/search/")
        self.assertEqual(parse_qs(parsed.query), {"api": ["1"], "query": [f"{place_name} {region}"]})

    def test_rejects_non_http_external_scheme(self):
        for unsafe_url in (
            "javascript:alert(1)",
            "//example.com/place",
            "data:text/html,<script>alert(1)</script>",
            "ftp://example.com/place",
        ):
            with self.subTest(url=unsafe_url):
                with self.assertRaises(ValidationError):
                    validate_external_place_url(unsafe_url)

        invalid_payload = self.food_payload(title="Unsafe place link", place_url="javascript:alert(1)")
        form = PostForm(data={**invalid_payload, "privacy": "on"})
        self.assertFalse(form.is_valid())
        self.assertIn("place_url", form.errors)
        with self.assertRaises(APIValidationError):
            services.create_post(self.user, invalid_payload)
        self.assertFalse(Post.objects.filter(title="Unsafe place link").exists())

        self.assertEqual(validate_external_place_url("  https://example.com/place  "), "https://example.com/place")
        self.assertEqual(validate_external_place_url("http://example.com/place"), "http://example.com/place")
        self.assertEqual(validate_external_place_url(""), "")

    def test_place_details_only_apply_to_foodtravel(self):
        place = services.create_post(self.user, self.food_payload())
        self.assertEqual(
            (place.place_name, place.place_region, place.place_note, place.place_url),
            ("카페 & ร้านกาแฟ?", "bangkok", "현지인이 추천한 장소", "https://example.com/place?id=1&view=map"),
        )

        ordinary = services.create_post(
            self.user,
            self.food_payload(title="Ordinary post", category="free"),
        )
        self.assertEqual(
            (ordinary.place_name, ordinary.place_region, ordinary.place_note, ordinary.place_url),
            ("", "", "", ""),
        )

        from .board_versions import board_data_version
        services.update_post(self.user, place, {"category": "free", "confirm_board_data_removal": True, "board_data_version": board_data_version(place)})
        place.refresh_from_db()
        self.assertEqual(
            (place.place_name, place.place_region, place.place_note, place.place_url),
            ("", "", "", ""),
        )

    def test_foodtravel_place_details_round_trip_through_api(self):
        api = APIClient()
        api.force_authenticate(self.user)
        response = api.post("/api/v1/posts/", self.food_payload(title="API foodtravel place"), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(
            (response.data["place_name"], response.data["place_region"], response.data["place_note"], response.data["place_url"]),
            ("카페 & ร้านกาแฟ?", "bangkok", "현지인이 추천한 장소", "https://example.com/place?id=1&view=map"),
        )

        unsafe = self.food_payload(title="API unsafe place URL", place_url="javascript:alert(1)")
        rejected = api.post("/api/v1/posts/", unsafe, format="json")
        self.assertEqual(rejected.status_code, 400)
        self.assertFalse(Post.objects.filter(title="API unsafe place URL").exists())

    def test_maps_link_renders_as_safe_external_link(self):
        self.assertTrue({"place_name", "place_region", "place_note", "place_url"}.issubset(PostForm().fields))
        place = services.create_post(self.user, self.food_payload())
        response = self.client.get(f"/community/{place.pk}/")
        self.assertEqual(response.status_code, 200)

        parser = AnchorCollector()
        parser.feed(response.content.decode())
        expected_map = build_google_maps_search_url("카페 & ร้านกาแฟ?", "Bangkok")
        external_links = [anchor for anchor in parser.anchors if anchor.get("href") in {expected_map, place.place_url}]
        self.assertEqual({anchor.get("href") for anchor in external_links}, {expected_map, place.place_url})
        for anchor in external_links:
            self.assertEqual(anchor.get("target"), "_blank")
            self.assertEqual(set(anchor.get("rel", "").split()), {"noopener", "noreferrer"})

        listing = self.client.get("/community/?category=foodtravel")
        listing_parser = AnchorCollector()
        listing_parser.feed(listing.content.decode())
        self.assertTrue(any(anchor.get("href") == expected_map for anchor in listing_parser.anchors))


class FoodTravelMigrationPreservationTests(TransactionTestCase):
    reset_sequences = True

    def test_existing_post_rows_survive_place_migration(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        old_target = ("community", "0024_alter_post_market_kind_alter_post_market_region_and_more")
        try:
            executor.migrate([old_target])
            old_apps = executor.loader.project_state([old_target]).apps
            User = old_apps.get_model(*settings.AUTH_USER_MODEL.split("."))
            PostBefore = old_apps.get_model("community", "Post")
            user = User.objects.create(username="legacy-place-row")
            legacy = PostBefore.objects.create(
                author_id=user.pk,
                title="Existing post before place migration",
                body="Original title, author, and body must survive.",
                category="visa",
                region="common",
            )
            old_pk = legacy.pk

            MigrationExecutor(connection).migrate(leaves)
            PostAfter = MigrationExecutor(connection).loader.project_state(leaves).apps.get_model("community", "Post")
            migrated = PostAfter.objects.get(pk=old_pk)
            self.assertEqual(
                (migrated.author_id, migrated.title, migrated.body, migrated.category, migrated.region),
                (user.pk, "Existing post before place migration", "Original title, author, and body must survive.", "visa", "common"),
            )
            self.assertEqual(
                (migrated.place_name, migrated.place_region, migrated.place_note, migrated.place_url),
                ("", "", "", ""),
            )

            old_write = PostBefore.objects.create(
                author_id=user.pk,
                title="Legacy post insert after place migration",
                body="An older release should keep writing posts.",
                category="foodtravel",
                region="common",
            )
            inserted = PostAfter.objects.get(pk=old_write.pk)
            self.assertEqual(
                (inserted.place_name, inserted.place_region, inserted.place_note, inserted.place_url),
                ("", "", "", ""),
            )
        finally:
            MigrationExecutor(connection).migrate(leaves)
