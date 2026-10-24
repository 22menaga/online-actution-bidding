from django.test import Client, SimpleTestCase, TestCase, override_settings


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class WebPageSmokeTests(SimpleTestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="localhost")

    def test_public_and_dashboard_pages_render(self):
        paths = [
            "/",
            "/login/",
            "/register/",
            "/buyer-dashboard/",
            "/seller-dashboard/",
            "/admin-dashboard/",
            "/products/",
            "/product-details/",
            "/auction-details/",
            "/live-bidding/",
            "/my-bids/",
            "/won-auctions/",
            "/payment/",
            "/notifications/",
            "/profile/",
            "/seller-verification/",
            "/product-management/",
            "/auction-management/",
            "/seller-approval/",
            "/product-approval/",
            "/user-management/",
            "/audit-logs/",
            "/analytics/",
            "/dashboard/",
        ]

        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)

    def test_signup_and_login_use_local_styles_and_offer_navigation(self):
        login = self.client.get("/login/")
        registration = self.client.get("/register/")

        self.assertContains(login, "/static/css/bootstrap.min.css")
        self.assertContains(login, "/static/css/app.css")
        self.assertContains(login, 'href="/register/"')
        self.assertContains(login, 'name="username"')
        self.assertContains(registration, "/static/css/bootstrap.min.css")
        self.assertContains(registration, "/static/css/app.css")
        self.assertContains(registration, 'id="register"')
        self.assertContains(registration, 'name="role"')
        self.assertContains(registration, 'href="/login/"')

    def test_marketplace_pages_use_real_workflows_instead_of_placeholders(self):
        for path in [
            "/products/",
            "/buyer-dashboard/",
            "/seller-dashboard/",
            "/admin-dashboard/",
            "/product-approval/",
            "/seller-approval/",
            "/auction-approval/",
            "/analytics/",
            "/notifications/",
            "/profile/",
            "/user-management/",
            "/audit-logs/",
            "/product-management/",
            "/auction-management/",
            "/live-bidding/",
            "/my-bids/",
            "/won-auctions/",
            "/payment/",
            "/seller-verification/",
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "Secure architecture")
                self.assertNotContains(response, "API-backed responsive interface")
                self.assertContains(response, "/static/js/marketplace.js")

        self.assertContains(self.client.get("/products/"), "/api/auctions/auctions/")
        self.assertContains(self.client.get("/product-management/"), "Submit product for review")
        self.assertContains(self.client.get("/auction-management/"), "Submit auction for approval")
        self.assertContains(self.client.get("/live-bidding/"), "/api/bidding/bids/")
        self.assertContains(self.client.get("/product-approval/"), "Approve product")
        self.assertContains(self.client.get("/seller-approval/"), "Approve seller")
        self.assertContains(self.client.get("/auction-approval/"), "Approve auction")
        self.assertContains(self.client.get("/dashboard/"), "Platform analytics")


class AdminAnalyticsTests(TestCase):
    def test_analytics_includes_pending_auctions_for_admin_review(self):
        from datetime import timedelta

        from django.utils import timezone
        from rest_framework.test import APIClient

        from accounts.models import User
        from auctions.models import Auction
        from products.models import Category, Product

        seller = User.objects.create_user(
            username="pending-auction-seller",
            email="pending-auction-seller@example.com",
            password="StrongPassword123!",
            role="SELLER",
        )
        admin = User.objects.create_user(
            username="pending-auction-admin",
            email="pending-auction-admin@example.com",
            password="StrongPassword123!",
            role="ADMIN",
        )
        category = Category.objects.create(name="Pending queue", slug="pending-queue")
        product = Product.objects.create(
            seller=seller,
            category=category,
            name="Pending item",
            description="Item awaiting auction review",
            starting_price=10,
            condition="Good",
            status="APPROVED",
        )
        Auction.objects.create(
            product=product,
            seller=seller,
            starting_price=10,
            min_increment=1,
            start_at=timezone.now() + timedelta(hours=1),
            end_at=timezone.now() + timedelta(hours=2),
            status="PENDING_APPROVAL",
        )
        client = APIClient()
        client.force_authenticate(admin)

        response = client.get("/api/dashboard/analytics/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pending_auctions"], 1)
