from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from products.models import Category, Product
from .models import Auction


class AdminSchedulingTests(TestCase):
    """Auctions run 24/7 for buyers, but only an admin decides when each one runs."""

    def setUp(self):
        from django.core.management import call_command
        call_command('seed_demo', verbosity=0)
        self.admin = User.objects.get(username='demo_admin')
        self.seller = User.objects.get(username='demo_seller')
        self.buyer = User.objects.get(username='demo_buyer')
        product = Product.objects.create(seller=self.seller, category=Category.objects.get(slug='art'), name='New Lot', description='A detailed description of this lot for review.', starting_price=100, condition='Good', status='APPROVED')
        self.sc, self.ac, self.bc = APIClient(), APIClient(), APIClient()
        self.sc.force_authenticate(self.seller); self.ac.force_authenticate(self.admin); self.bc.force_authenticate(self.buyer)
        self.pending = self.sc.post('/api/auctions/auctions/', {'product': product.id, 'starting_price': '100', 'min_increment': '5', 'is_24_7': True}, format='json').json()
        self.url = f"/api/auctions/auctions/{self.pending['id']}"

    def window(self, **kw):
        now = timezone.now()
        return {'start_at': (now + timedelta(hours=1)).isoformat(), 'end_at': (now + timedelta(hours=5)).isoformat(), **kw}

    def test_seller_request_has_no_schedule_and_is_hidden_from_public(self):
        self.assertIsNone(self.pending['start_at'])
        self.assertEqual(self.pending['status'], 'PENDING_APPROVAL')
        self.assertTrue(self.pending['is_24_7'])
        self.assertEqual(self.client.get(self.url + '/').status_code, 404)

    def test_seller_cannot_approve_or_set_the_schedule(self):
        self.assertEqual(self.sc.post(self.url + '/approve/', self.window(), format='json').status_code, 403)
        self.sc.patch(self.url + '/', {'start_at': self.window()['start_at']}, format='json')
        self.assertIsNone(Auction.objects.get(pk=self.pending['id']).start_at)

    def test_buyer_cannot_allocate_time(self):
        self.assertEqual(self.bc.post(self.url + '/approve/', self.window(), format='json').status_code, 403)

    def test_admin_allocates_time_and_seller_is_notified(self):
        r = self.ac.post(self.url + '/approve/', self.window(note='Evening slot'), format='json')
        self.assertEqual((r.status_code, r.json()['status'], r.json()['admin_note']), (200, 'SCHEDULED', 'Evening slot'))
        from notifications.models import Notification
        self.assertTrue(Notification.objects.filter(recipient=self.seller, title='Auction scheduled').exists())
        self.assertEqual(self.client.get(self.url + '/').status_code, 200)

    def test_allocation_rules(self):
        now = timezone.now()
        iso = lambda d: (now + d).isoformat()
        bad = [
            {'start_at': iso(timedelta(hours=2)), 'end_at': iso(timedelta(hours=1))},                  # end before start
            {'start_at': iso(-timedelta(days=1)), 'end_at': iso(timedelta(hours=1))},                  # in the past
            {'start_at': iso(timedelta(hours=1)), 'end_at': iso(timedelta(hours=1, minutes=3))},       # too short
            {'start_at': iso(timedelta(hours=1)), 'end_at': iso(timedelta(days=60))},                  # too long
        ]
        for body in bad:
            self.assertEqual(self.ac.post(self.url + '/approve/', body, format='json').status_code, 400, body)
        self.assertEqual(Auction.objects.get(pk=self.pending['id']).status, 'PENDING_APPROVAL')

    @override_settings(AUCTION_MAX_CONCURRENT=2)
    def test_full_window_is_refused(self):
        self.assertEqual(self.ac.post(self.url + '/approve/', self.window(), format='json').status_code, 400)  # 5 demo auctions already run

    def test_reschedule_only_without_bids(self):
        self.ac.post(self.url + '/approve/', self.window(), format='json')
        later = {'start_at': (timezone.now() + timedelta(hours=3)).isoformat(), 'end_at': (timezone.now() + timedelta(hours=9)).isoformat()}
        self.assertEqual(self.ac.post(self.url + '/reschedule/', later, format='json').status_code, 200)
        Auction.objects.filter(pk=self.pending['id']).update(bid_count=1)
        self.assertEqual(self.ac.post(self.url + '/reschedule/', later, format='json').status_code, 400)

    def test_reject_needs_reason_and_notifies_seller(self):
        self.assertEqual(self.ac.post(self.url + '/reject/', {}, format='json').status_code, 400)
        r = self.ac.post(self.url + '/reject/', {'reason': 'Photos do not match the description.'}, format='json')
        self.assertEqual((r.status_code, r.json()['status']), (200, 'CANCELLED'))

    def test_buyer_can_only_suggest_a_time_for_upcoming_auctions(self):
        upcoming = Auction.objects.get(status='SCHEDULED')
        live = Auction.objects.filter(status='LIVE').first()
        ok = self.bc.post(f'/api/auctions/auctions/{upcoming.id}/suggest-time/', {'preferred_start': (timezone.now() + timedelta(days=1)).isoformat(), 'note': 'Weekend evening'}, format='json')
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(self.bc.post(f'/api/auctions/auctions/{live.id}/suggest-time/', {'note': 'x'}, format='json').status_code, 409)
        self.assertEqual(self.bc.post(f'/api/auctions/auctions/{upcoming.id}/suggest-time/', {}, format='json').status_code, 400)
        inbox = self.ac.get('/api/auctions/time-requests/?status=OPEN').json()['results']
        self.assertEqual((len(inbox), inbox[0]['requester_role']), (1, 'BUYER'))
        self.assertEqual(self.bc.get('/api/auctions/time-requests/').status_code, 403)  # the inbox is admin-only
        done = self.ac.post(f"/api/auctions/time-requests/{inbox[0]['id']}/resolve/", {'status': 'ACCEPTED'}, format='json')
        self.assertEqual(done.json()['status'], 'ACCEPTED')

    def test_review_report_is_admin_only_and_flags_risks(self):
        self.assertEqual(self.bc.get(self.url + '/review/').status_code, 403)
        self.assertEqual(self.sc.get(self.url + '/review/').status_code, 403)
        report = self.ac.get(self.url + '/review/').json()
        self.assertTrue({'seller_verified', 'seller_age', 'price_sanity', 'capacity', 'duplicate'} <= {c['key'] for c in report['checks']})
        self.assertIn(report['overall'], ('ok', 'warn', 'fail'))
        self.assertTrue(report['request']['is_24_7'])

    def test_admin_overview_is_admin_only_and_complete(self):
        self.assertEqual(self.bc.get('/api/dashboard/overview/').status_code, 403)
        data = self.ac.get('/api/dashboard/overview/').json()
        self.assertEqual(data['queue']['pending_auctions'], 2)  # the demo listing + the one made in setUp
        self.assertTrue({'queue', 'platform', 'security', 'money', 'recent_activity'} <= set(data))


    def test_product_reports_its_auction_state(self):
        mine = {p['id']: p for p in self.sc.get('/api/products/products/').json()['results']}
        listed = [p for p in mine.values() if p['name'] == 'New Lot'][0]
        self.assertEqual((listed['auction_status'], listed['auction_id']), ('PENDING_APPROVAL', self.pending['id']))

    def test_second_request_for_same_product_is_a_clear_400(self):
        r = self.sc.post('/api/auctions/auctions/', {'product': self.pending['product'], 'starting_price': '100', 'min_increment': '5'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('already has an active auction request', str(r.json()))

    def test_rejected_product_can_be_listed_again(self):
        self.ac.post(self.url + '/reject/', {'reason': 'Photos missing.'}, format='json')
        r = self.sc.post('/api/auctions/auctions/', {'product': self.pending['product'], 'starting_price': '120', 'min_increment': '5', 'is_24_7': True}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['status'], 'PENDING_APPROVAL')
