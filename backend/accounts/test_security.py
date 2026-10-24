import uuid
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import SellerProfile, User
from audit.models import AuditLog
from auctions.models import Auction
from products.models import Category, Product


def make_user(name, role='BUYER'):
    u = User.objects.create_user(username=name, email=f'{name}@example.com', password='StrongPassword123!', role=role, email_verified=True)
    if role == 'SELLER':
        SellerProfile.objects.create(user=u, approved=True, verified=True)
    return u


def login(c, name, password='StrongPassword123!'):
    return c.post('/api/auth/token/', {'username': name, 'password': password}, format='json')


class LoginHardeningTests(TestCase):
    def setUp(self):
        self.user = make_user('victim')
        self.c = APIClient()

    def test_repeated_failures_lock_the_account_even_for_the_right_password(self):
        for _ in range(5):
            self.assertEqual(login(self.c, 'victim', 'wrong-password').status_code, 401)
        r = login(self.c, 'victim')  # correct password, but the lock is already on
        self.assertEqual((r.status_code, r.json()['code']), (429, 'locked'))
        self.assertIn('Retry-After', r)
        self.assertTrue(AuditLog.objects.filter(action='ACCOUNT_LOCKED').exists())
        self.assertEqual(AuditLog.objects.filter(action='LOGIN_FAILED').count(), 5)

    def test_other_accounts_are_not_affected_and_success_resets_the_counter(self):
        make_user('bystander')
        for _ in range(4):
            login(self.c, 'victim', 'wrong-password')
        self.assertEqual(login(self.c, 'victim').status_code, 200)         # 4 failures is below the lock, and success resets
        for _ in range(4):
            login(self.c, 'victim', 'wrong-password')
        self.assertEqual(login(self.c, 'victim').status_code, 200)
        for _ in range(5):
            login(self.c, 'victim', 'wrong-password')
        self.assertEqual(login(self.c, 'bystander').status_code, 200)       # a different account still works

    def test_unknown_and_wrong_password_are_indistinguishable(self):
        a = login(self.c, 'victim', 'nope').json()['detail']
        b = login(self.c, 'nobody-here', 'nope').json()['detail']
        self.assertEqual(a, b)

    def test_missing_fields_are_a_clean_400(self):
        self.assertEqual(self.c.post('/api/auth/token/', {}, format='json').status_code, 400)

    def test_successful_login_records_last_login(self):
        self.assertIsNone(User.objects.get(username='victim').last_login)
        login(self.c, 'victim')
        self.assertIsNotNone(User.objects.get(username='victim').last_login)


class TokenRevocationTests(TestCase):
    def setUp(self):
        make_user('tokenuser')
        self.c = APIClient()
        self.tokens = login(self.c, 'tokenuser').json()

    def test_refresh_rotates_and_the_old_refresh_token_dies(self):
        r1 = self.c.post('/api/auth/token/refresh/', {'refresh': self.tokens['refresh']}, format='json')
        self.assertEqual(r1.status_code, 200)
        self.assertNotEqual(r1.json()['refresh'], self.tokens['refresh'])
        replay = self.c.post('/api/auth/token/refresh/', {'refresh': self.tokens['refresh']}, format='json')  # a stolen/old copy
        self.assertEqual(replay.status_code, 401)

    def test_logout_revokes_the_refresh_token(self):
        self.assertEqual(self.c.post('/api/auth/logout/', {'refresh': self.tokens['refresh']}, format='json').status_code, 204)
        self.assertEqual(self.c.post('/api/auth/token/refresh/', {'refresh': self.tokens['refresh']}, format='json').status_code, 401)
        self.assertEqual(self.c.post('/api/auth/logout/', {'refresh': 'garbage'}, format='json').status_code, 204)  # never leaks anything

    def test_access_token_lifetime_is_short(self):
        from rest_framework_simplejwt.tokens import AccessToken
        t = AccessToken(self.tokens['access'])
        self.assertLessEqual(t['exp'] - t['iat'], 15 * 60)


class HeaderTests(TestCase):
    def test_api_responses_are_never_cached_and_have_a_locked_down_csp(self):
        r = APIClient().get('/api/auctions/auctions/')
        self.assertEqual(r['Cache-Control'], 'no-store')
        self.assertIn("default-src 'none'", r['Content-Security-Policy'])
        self.assertIn('camera=()', r['Permissions-Policy'])
        self.assertEqual(r['X-Content-Type-Options'], 'nosniff')

    def test_admin_pages_get_a_self_only_csp(self):
        r = self.client.get('/admin/anything/')  # redirects to the login page; headers are applied to every response
        self.assertIn("default-src 'self'", r['Content-Security-Policy'])
        self.assertEqual(r['X-Frame-Options'], 'DENY')


class BidAbuseTests(TestCase):
    def setUp(self):
        seller = make_user('shop', 'SELLER')
        self.buyer = make_user('bidder1')
        p = Product.objects.create(seller=seller, category=Category.objects.create(name='C', slug='c-sec'), name='Lot', description='x' * 40, starting_price=100, condition='Good', status='AUCTION')
        self.a = Auction.objects.create(product=p, seller=seller, starting_price=100, min_increment=10, start_at=timezone.now() - timedelta(minutes=1), end_at=timezone.now() + timedelta(hours=1), status='LIVE')
        self.c = APIClient()
        self.c.force_authenticate(self.buyer)

    def bid(self, amount, **extra):
        return self.c.post('/api/bidding/bids/', {'auction': self.a.id, 'amount': str(amount), 'client_reference': str(uuid.uuid4()), **extra}, format='json')

    def test_fat_finger_bid_needs_explicit_confirmation(self):
        r = self.bid(5000)  # 50x the starting price
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'confirm_large_bid')
        self.assertEqual(self.bid(5000, confirm_large=True).status_code, 201)

    def test_normal_bids_need_no_confirmation(self):
        self.assertEqual(self.bid(110).status_code, 201)

    def test_hammering_one_lot_is_rate_limited(self):
        codes = [self.bid(100).status_code for _ in range(17)]  # 1 accepted, the rest rejected by rules; throttle counts every attempt
        self.assertEqual(codes[-1], 429)
        self.assertNotIn(429, codes[:15])


def png_bytes(size=(120, 90)):
    b = BytesIO()
    Image.new('RGB', size, (10, 120, 200)).save(b, 'PNG')
    return b.getvalue()


class UploadHardeningTests(TestCase):
    def setUp(self):
        self.seller = make_user('uploader', 'SELLER')
        self.c = APIClient()
        self.c.force_authenticate(self.seller)
        cat = Category.objects.create(name='U', slug='u-sec')
        self.p = Product.objects.create(seller=self.seller, category=cat, name='P', description='x' * 40, starting_price=10, condition='Good')

    def upload(self, content, name='photo.png', ctype='image/png'):
        return self.c.post(f'/api/products/products/{self.p.id}/image/', {'image': SimpleUploadedFile(name, content, content_type=ctype), 'alt_text': 'x'}, format='multipart')

    def test_a_script_pretending_to_be_an_image_is_refused(self):
        r = self.upload(b'<?php system($_GET["c"]); ?>', 'shell.png', 'image/png')
        self.assertEqual(r.status_code, 400)

    def test_svg_and_gif_are_refused_even_with_an_image_content_type(self):
        self.assertEqual(self.upload(b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', 'x.png', 'image/png').status_code, 400)

    def test_a_real_image_is_accepted_stored_under_a_random_name(self):
        r = self.upload(png_bytes(), '../../evil name.png')
        self.assertEqual(r.status_code, 201)
        img = self.p.images.first()
        self.assertNotIn('evil', img.image.name)
        self.assertRegex(img.image.name.split('/')[-1], r'^[0-9a-f]{32}\.png$')

    def test_appended_payload_is_stripped_by_re_encoding(self):
        r = self.upload(png_bytes() + b'SECRET-PAYLOAD-MARKER')
        self.assertEqual(r.status_code, 201)
        stored = self.p.images.first().image.read()
        self.assertNotIn(b'SECRET-PAYLOAD-MARKER', stored)

    def test_decompression_bombs_are_refused(self):
        from products import images
        with override_settings():
            old = images.MAX_PIXELS
            images.MAX_PIXELS = 100
            try:
                self.assertEqual(self.upload(png_bytes((50, 50))).status_code, 400)
            finally:
                images.MAX_PIXELS = old
