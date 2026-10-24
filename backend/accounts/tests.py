from django.test import TestCase
from rest_framework.test import APIClient
from .models import User
class AccountTests(TestCase):
    def test_registration_creates_role_profile(self):
        c=APIClient(); r=c.post('/api/accounts/register/',{'username':'buyer1','email':'buyer@example.com','password':'StrongPassword123!','role':'BUYER'},format='json')
        self.assertEqual(r.status_code,201); self.assertTrue(User.objects.filter(email='buyer@example.com',role='BUYER').exists())

    def test_registered_account_can_authenticate_with_jwt(self):
        client=APIClient()
        registration=client.post('/api/accounts/register/',{'username':'jwtbuyer','email':'jwtbuyer@example.com','password':'StrongPassword123!','role':'BUYER'},format='json')
        self.assertEqual(registration.status_code,201)
        tokens=client.post('/api/auth/token/',{'username':'jwtbuyer','password':'StrongPassword123!'},format='json')
        self.assertEqual(tokens.status_code,200)
        self.assertIn('access',tokens.data)
        self.assertIn('refresh',tokens.data)
        profile=client.get('/api/accounts/me/',HTTP_AUTHORIZATION=f"Bearer {tokens.data['access']}")
        self.assertEqual(profile.status_code,200)
        self.assertEqual(profile.data['role'],'BUYER')

    def test_admin_role_cannot_self_register(self):
        r=APIClient().post('/api/accounts/register/',{'username':'badadmin','email':'a@example.com','password':'StrongPassword123!','role':'ADMIN'},format='json')
        self.assertEqual(r.status_code,400)



from django.test import override_settings as _override


class LocalEmailVerificationTests(TestCase):
    def _register(self, name):
        from rest_framework.test import APIClient
        return APIClient().post('/api/accounts/register/', {'username': name, 'email': f'{name}@example.com', 'password': 'StrongPassword123!', 'role': 'BUYER'}, format='json')

    @_override(AUTO_VERIFY_EMAIL=True)
    def test_local_mode_verifies_new_accounts_so_they_can_bid(self):
        r = self._register('localuser')
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.json()['auto_verified'])
        self.assertTrue(User.objects.get(username='localuser').email_verified)

    @_override(AUTO_VERIFY_EMAIL=False)
    def test_production_mode_still_requires_the_email_link(self):
        r = self._register('produser')
        self.assertFalse(r.json()['auto_verified'])
        self.assertFalse(User.objects.get(username='produser').email_verified)

    @_override(AUTO_VERIFY_EMAIL=False)
    def test_resend_verification_sends_an_email_and_is_login_only(self):
        from django.core import mail
        from rest_framework.test import APIClient
        self._register('resender')
        c = APIClient()
        self.assertEqual(c.post('/api/accounts/resend-verification/').status_code, 401)
        c.force_authenticate(User.objects.get(username='resender'))
        mail.outbox.clear()
        r = c.post('/api/accounts/resend-verification/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/verify/', mail.outbox[0].body)



class RoleProfileTests(TestCase):
    def _user(self, name, role):
        return User.objects.create_user(username=name, email=f'{name}@example.com', password='StrongPassword123!', role=role, email_verified=True)

    def test_seller_and_bidder_get_different_profiles(self):
        seller, buyer = self._user('s1', 'SELLER'), self._user('b1', 'BUYER')
        c = APIClient(); c.force_authenticate(seller)
        d = c.get('/api/accounts/profile/').json()
        self.assertEqual(d['role'], 'SELLER'); self.assertIn('business_name', d); self.assertIn('approved', d)
        c.force_authenticate(buyer)
        d = c.get('/api/accounts/profile/').json()
        self.assertEqual(d['role'], 'BUYER'); self.assertIn('phone', d); self.assertNotIn('business_name', d); self.assertNotIn('approved', d)

    def test_profile_updates_only_role_fields_and_validates(self):
        buyer = self._user('b2', 'BUYER'); c = APIClient(); c.force_authenticate(buyer)
        r = c.patch('/api/accounts/profile/', {'phone': '+91 98765 43210', 'address': 'MG Road, Bengaluru', 'business_name': 'sneaky', 'role': 'ADMIN'}, format='json')
        self.assertEqual(r.status_code, 200); self.assertEqual(r.json()['phone'], '+91 98765 43210')
        buyer.refresh_from_db(); self.assertEqual(buyer.role, 'BUYER')  # role cannot be changed here
        self.assertEqual(c.patch('/api/accounts/profile/', {'phone': '9' * 40}, format='json').status_code, 400)

    def test_seller_cannot_self_approve_through_profile(self):
        seller = self._user('s2', 'SELLER'); c = APIClient(); c.force_authenticate(seller)
        c.patch('/api/accounts/profile/', {'business_name': 'Acme Antiques', 'approved': True, 'verified': True}, format='json')
        d = c.get('/api/accounts/profile/').json()
        self.assertEqual(d['business_name'], 'Acme Antiques'); self.assertFalse(d['approved'])

    def test_sellers_and_admins_cannot_bid(self):
        from datetime import timedelta
        from decimal import Decimal
        from django.utils import timezone
        from rest_framework.exceptions import PermissionDenied
        from auctions.models import Auction
        from bidding.services import place_bid
        from products.models import Category, Product
        owner = self._user('own', 'SELLER'); other_seller = self._user('s3', 'SELLER'); admin = self._user('adm', 'ADMIN')
        p = Product.objects.create(seller=owner, category=Category.objects.create(name='Z', slug='z-r'), name='X', description='x', starting_price=10, condition='Good', status='AUCTION')
        a = Auction.objects.create(product=p, seller=owner, starting_price=10, min_increment=1, start_at=timezone.now() - timedelta(minutes=1), end_at=timezone.now() + timedelta(hours=1), status='LIVE')
        for who in (other_seller, admin):
            with self.assertRaises(PermissionDenied):
                place_bid(auction_id=a.id, bidder=who, amount=Decimal('10'))
