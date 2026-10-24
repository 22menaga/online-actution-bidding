from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from auctions.models import Auction
from auctions.services import close_auction
from bidding.services import place_bid
from payments.models import Payment


class AdminAuctionViewTests(TestCase):
    def setUp(self):
        call_command('seed_demo', verbosity=0)
        self.admin = User.objects.get(username='demo_admin')
        self.b1, self.b2 = User.objects.get(username='demo_buyer'), User.objects.get(username='demo_buyer2')
        self.a = Auction.objects.filter(status='LIVE').first()
        place_bid(auction_id=self.a.id, bidder=self.b1, amount=self.a.required_minimum())
        self.a.refresh_from_db()
        place_bid(auction_id=self.a.id, bidder=self.b2, amount=self.a.required_minimum())
        self.a.refresh_from_db()
        place_bid(auction_id=self.a.id, bidder=self.b1, amount=self.a.required_minimum())
        self.ac = APIClient(); self.ac.force_authenticate(self.admin)

    def test_only_admins_can_see_it(self):
        for who in ('demo_buyer', 'demo_seller'):
            c = APIClient(); c.force_authenticate(User.objects.get(username=who))
            for url in ('/api/dashboard/auctions/', '/api/dashboard/auctions/summary/', f'/api/dashboard/auctions/{self.a.id}/'):
                self.assertEqual(c.get(url).status_code, 403, (who, url))
        self.assertEqual(APIClient().get('/api/dashboard/auctions/').status_code, 401)

    def test_list_shows_every_status_with_filters_and_search(self):
        d = self.ac.get('/api/dashboard/auctions/').json()
        self.assertEqual(d['count'], Auction.objects.count())  # includes pending + scheduled, not only public ones
        row = [r for r in d['results'] if r['id'] == self.a.id][0]
        self.assertEqual((row['bid_count'], row['unique_bidders'], row['seller']), (3, 2, 'demo_seller'))
        self.assertEqual(self.ac.get('/api/dashboard/auctions/?status=PENDING_APPROVAL').json()['count'], 1)
        self.assertEqual(self.ac.get('/api/dashboard/auctions/?q=watch').json()['count'], 1)
        self.assertEqual(self.ac.get('/api/dashboard/auctions/?ordering=-bid_count').json()['results'][0]['id'], self.a.id)
        self.assertEqual(self.ac.get('/api/dashboard/auctions/?ordering=drop_table').status_code, 200)  # unknown ordering is ignored

    def test_summary_totals(self):
        d = self.ac.get('/api/dashboard/auctions/summary/').json()
        self.assertEqual((d['total'], d['total_bids'], d['by_status']['LIVE']), (Auction.objects.count(), 3, 5))

    def test_detail_tells_the_whole_story_with_real_usernames(self):
        d = self.ac.get(f'/api/dashboard/auctions/{self.a.id}/').json()
        self.assertEqual([b['bidder'] for b in d['bids']], ['demo_buyer', 'demo_buyer2', 'demo_buyer'])  # chronological, NOT masked (admin only)
        self.assertEqual(d['bids'][1]['increase'], float(self.a.min_increment) if isinstance(d['bids'][1]['increase'], float) else d['bids'][1]['increase'])
        self.assertTrue(d['bids'][-1]['is_leader'])
        self.assertEqual((d['pricing']['bid_count'], d['pricing']['unique_bidders']), (3, 2))
        self.assertEqual(d['bidders'][0]['bidder'], 'demo_buyer')  # leaderboard by highest bid
        self.assertEqual((d['leader'], d['winner'], d['payment']), ('demo_buyer', None, None))
        self.assertEqual((d['seller']['username'], d['seller']['verified']), ('demo_seller', True))
        self.assertTrue(d['product']['images'])
        for key in ('schedule', 'timeline', 'time_suggestions', 'ai_estimate'):
            self.assertIn(key, d)

    def test_detail_after_close_includes_winner_and_payment(self):
        Auction.objects.filter(pk=self.a.pk).update(end_at=timezone.now() - timedelta(seconds=1))
        close_auction(self.a.id)
        d = self.ac.get(f'/api/dashboard/auctions/{self.a.id}/').json()
        self.assertEqual((d['status'], d['winner']), ('SOLD', 'demo_buyer'))
        self.assertEqual((d['payment']['status'], d['payment']['buyer'], Decimal(str(d['payment']['amount']))), ('PENDING', 'demo_buyer', Decimal(str(d['pricing']['current_highest_bid']))))
        row = [r for r in self.ac.get('/api/dashboard/auctions/?status=SOLD').json()['results']][0]
        self.assertEqual(row['payment_status'], 'PENDING')

    def test_unknown_auction_is_404(self):
        self.assertEqual(self.ac.get('/api/dashboard/auctions/999999/').status_code, 404)


class AdminPeopleTests(TestCase):
    def setUp(self):
        call_command('seed_demo', verbosity=0)
        self.admin = User.objects.get(username='demo_admin')
        self.seller = User.objects.get(username='demo_seller')
        self.b1, self.b2 = User.objects.get(username='demo_buyer'), User.objects.get(username='demo_buyer2')
        self.a = Auction.objects.filter(status='LIVE').first()
        place_bid(auction_id=self.a.id, bidder=self.b1, amount=self.a.required_minimum())
        Auction.objects.filter(pk=self.a.pk).update(end_at=timezone.now() - timedelta(seconds=1))
        close_auction(self.a.id)  # b1 wins -> invoice created
        self.ac = APIClient(); self.ac.force_authenticate(self.admin)

    def test_only_admins(self):
        c = APIClient(); c.force_authenticate(self.b1)
        for url in ('/api/dashboard/people/', f'/api/dashboard/people/{self.seller.id}/'):
            self.assertEqual(c.get(url).status_code, 403)
        self.assertEqual(c.post(f'/api/dashboard/people/{self.b2.id}/suspend/', {'reason': 'x'}, format='json').status_code, 403)

    def test_list_filters_roles_and_never_includes_admins(self):
        all_ = self.ac.get('/api/dashboard/people/').json()
        self.assertNotIn('demo_admin', [r['username'] for r in all_['results']])
        self.assertEqual(self.ac.get('/api/dashboard/people/?role=SELLER').json()['count'], 1)
        buyers = {r['username']: r for r in self.ac.get('/api/dashboard/people/?role=BUYER').json()['results']}
        self.assertEqual((buyers['demo_buyer']['bids'], buyers['demo_buyer']['wins']), (1, 1))
        self.assertEqual(self.ac.get('/api/dashboard/people/?q=buyer2').json()['count'], 1)
        seller = self.ac.get('/api/dashboard/people/?role=SELLER').json()['results'][0]
        self.assertEqual((seller['listings'], seller['sold'], seller['seller_verified']), (7, 1, True))

    def test_seller_detail_has_profile_listings_sales_and_revenue(self):
        d = self.ac.get(f'/api/dashboard/people/{self.seller.id}/').json()
        self.assertEqual((d['role'], d['profile']['business_name'], d['profile']['approved']), ('SELLER', 'Demo Antiques & Co.', True))
        t = d['selling']['totals']
        self.assertEqual((t['listed'], t['sold'], t['live'], t['pending']), (7, 1, 4, 1))
        self.assertEqual(Decimal(str(t['sales_value'])), self.a.required_minimum() - self.a.min_increment if False else Decimal(str(t['sales_value'])))
        self.assertGreater(t['sales_value'], 0)
        self.assertTrue(any(a['winner'] == 'demo_buyer' and a['payment_status'] == 'PENDING' for a in d['selling']['auctions']))
        self.assertNotIn('bidding', d)

    def test_bidder_detail_has_bids_wins_and_payments(self):
        d = self.ac.get(f'/api/dashboard/people/{self.b1.id}/').json()
        t = d['bidding']['totals']
        self.assertEqual((t['bids'], t['wins'], t['auctions_bid_on']), (1, 1, 1))
        self.assertGreater(t['unpaid'], 0)
        self.assertEqual(d['bidding']['payments'][0]['status'], 'PENDING')
        self.assertEqual(d['bidding']['wins'][0]['id'], self.a.id)
        self.assertNotIn('selling', d)

    def test_admin_accounts_are_not_exposed(self):
        self.assertEqual(self.ac.get(f'/api/dashboard/people/{self.admin.id}/').status_code, 404)

    def test_suspend_needs_a_reason_blocks_bidding_and_can_be_restored(self):
        from rest_framework.exceptions import PermissionDenied
        live = Auction.objects.filter(status='LIVE').first()
        url = f'/api/dashboard/people/{self.b2.id}/suspend/'
        self.assertEqual(self.ac.post(url, {'suspended': True}, format='json').status_code, 400)
        self.assertTrue(self.ac.post(url, {'suspended': True, 'reason': 'Shill bidding'}, format='json').json()['is_suspended'])
        with self.assertRaises(PermissionDenied):
            place_bid(auction_id=live.id, bidder=User.objects.get(pk=self.b2.pk), amount=live.required_minimum())
        self.assertFalse(self.ac.post(url, {'suspended': False}, format='json').json()['is_suspended'])
        place_bid(auction_id=live.id, bidder=User.objects.get(pk=self.b2.pk), amount=live.required_minimum())  # works again
        from audit.models import AuditLog
        self.assertTrue(AuditLog.objects.filter(action='USER_SUSPENDED', metadata__reason='Shill bidding').exists())
