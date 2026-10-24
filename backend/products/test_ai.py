import io
from unittest.mock import MagicMock, patch

import anthropic
import httpx2 as httpx
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import User
from products import ai_valuation as ai
from products.models import AIEstimate, Category, Product

URL = '/api/products/ai-estimate/'
KEY = dict(ANTHROPIC_API_KEY='sk-test', AI_VALUATION_MODEL='claude-opus-5-5', PAYMENT_CURRENCY='INR')


def jpeg(size=(400, 300), mode='RGB', fmt='JPEG'):
    buf = io.BytesIO()
    Image.new(mode, size, (200, 120, 40) if mode == 'RGB' else (200, 120, 40, 128)).save(buf, fmt)
    return SimpleUploadedFile('photo.' + fmt.lower(), buf.getvalue(), content_type='image/' + fmt.lower())


def valuation(**over):
    base = dict(is_sellable_item=True, item_name='Brass ship compass', maker_or_brand='', category='antiques', condition='Good',
                description='A brass compass in a wooden case.', estimated_low=2400.0, estimated_high=3600.0, confidence='medium',
                value_drivers=['Brass body', 'Original case'], risks=['No maker mark visible'], questions_for_seller=['Does it work?'])
    base.update(over)
    return ai.Valuation(**base)


def fake_client(parsed=None, stop_reason='end_turn', error=None):
    client = MagicMock()
    if error:
        client.messages.parse.side_effect = error
    else:
        client.messages.parse.return_value = MagicMock(parsed_output=parsed, stop_reason=stop_reason)
    return client


class AIEstimateApiTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username='sel', email='s@example.com', password='StrongPassword123!', role='SELLER', email_verified=True)
        self.buyer = User.objects.create_user(username='buy', email='b@example.com', password='StrongPassword123!', role='BUYER', email_verified=True)
        Category.objects.create(name='Antiques', slug='antiques-t')
        self.c = APIClient(); self.c.force_authenticate(self.seller)

    def post(self, files=None, client=None, **extra):
        files = [jpeg()] if files is None else files
        return client.post(URL, {'images': files, **extra}, format='multipart') if client else self.c.post(URL, {'images': files, **extra}, format='multipart')

    # ---- access
    @override_settings(**KEY)
    def test_only_sellers_can_use_it(self):
        b = APIClient(); b.force_authenticate(self.buyer)
        self.assertEqual(self.post(client=b).status_code, 403)
        self.assertEqual(self.post(client=APIClient()).status_code, 401)

    @override_settings(**{**KEY, 'ANTHROPIC_API_KEY': ''})
    def test_clear_503_when_no_api_key(self):
        r = self.post()
        self.assertEqual((r.status_code, r.json()['code']), (503, 'not_configured'))
        self.assertEqual(self.c.get(URL + 'status/').json(), {'enabled': False})

    # ---- upload validation
    @override_settings(**KEY)
    def test_rejects_missing_too_many_and_non_image_files(self):
        self.assertEqual(self.c.post(URL, {}, format='multipart').status_code, 400)
        self.assertEqual(self.post(files=[jpeg() for _ in range(5)]).status_code, 400)
        fake = SimpleUploadedFile('x.jpg', b'<?php echo 1; ?>', content_type='image/jpeg')  # claims to be a JPEG, is not
        r = self.post(files=[fake])
        self.assertEqual(r.status_code, 400)
        self.assertIn('not a readable image', r.json()['detail'])

    @override_settings(**KEY)
    def test_rejects_oversized_file(self):
        big = SimpleUploadedFile('big.jpg', b'0' * (5 * 1024 * 1024 + 1), content_type='image/jpeg')
        self.assertEqual(self.post(files=[big]).status_code, 400)

    # ---- success path and stored result
    @override_settings(**KEY)
    def test_success_is_sanitised_stored_and_audited(self):
        with patch('anthropic.Anthropic', return_value=fake_client(valuation())) as cls:
            r = self.post(hint='  bought it at a flea market  ')
        self.assertEqual(r.status_code, 201)
        d = r.json()
        self.assertEqual((d['sellable'], d['category'], d['currency']), (True, 'Antiques', 'INR'))  # category mapped to the real one
        self.assertTrue(d['estimated_low'] < d['estimated_mid'] < d['estimated_high'])
        self.assertEqual(d['suggested_start_price'], ai.nice_round(d['estimated_low'] * 0.6))
        self.assertTrue(AIEstimate.objects.filter(pk=d['id'], user=self.seller).exists())
        sent = cls.return_value.messages.parse.call_args.kwargs
        self.assertEqual(sent['model'], 'claude-opus-5-5')
        text = [b for b in sent['messages'][0]['content'] if b['type'] == 'text'][0]['text']
        self.assertIn('untrusted', text)
        self.assertEqual(sum(b['type'] == 'image' for b in sent['messages'][0]['content']), 1)

    @override_settings(**KEY)
    def test_unsellable_photo_is_reported_without_a_price(self):
        with patch('anthropic.Anthropic', return_value=fake_client(valuation(is_sellable_item=False))):
            d = self.post().json()
        self.assertFalse(d['sellable'])
        self.assertNotIn('estimated_low', d)

    @override_settings(**KEY)
    def test_unusable_numbers_are_refused_not_stored(self):
        for lo, hi in ((0, 0), (-5, 10), (float('nan'), 5)):
            with patch('anthropic.Anthropic', return_value=fake_client(valuation(estimated_low=lo, estimated_high=hi))):
                self.assertEqual(self.post().status_code, 422)
        self.assertEqual(AIEstimate.objects.count(), 0)

    # ---- failures never leak internals
    @override_settings(**KEY)
    def test_rejected_credentials_give_a_safe_message(self):
        resp = httpx.Response(401, request=httpx.Request('POST', 'https://api.anthropic.com'))
        err = anthropic.AuthenticationError('invalid x-api-key sk-secret', response=resp, body=None)
        with patch('anthropic.Anthropic', return_value=fake_client(error=err)):
            r = self.post()
        self.assertEqual(r.status_code, 503)
        self.assertNotIn('sk-secret', r.json()['detail'])

    @override_settings(**KEY)
    def test_model_refusal_is_a_clear_422(self):
        with patch('anthropic.Anthropic', return_value=fake_client(parsed=None, stop_reason='refusal')):
            r = self.post()
        self.assertEqual((r.status_code, r.json()['code']), (422, 'refused'))

    # ---- attaching to a product
    @override_settings(**KEY)
    def test_estimate_is_attached_to_the_product_only_if_it_is_the_sellers_own(self):
        with patch('anthropic.Anthropic', return_value=fake_client(valuation())):
            est_id = self.post().json()['id']
        cat = Category.objects.get(slug='antiques-t')
        body = {'category': cat.id, 'name': 'Compass', 'description': 'Brass compass in a case, working.', 'starting_price': '3000', 'condition': 'Good'}
        ok = self.c.post('/api/products/products/', {**body, 'ai_estimate_id': est_id}, format='json')
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(ok.json()['ai_estimate']['estimated_high'], 3600)
        # another seller cannot borrow that analysis
        other = User.objects.create_user(username='sel2', email='s2@example.com', password='StrongPassword123!', role='SELLER', email_verified=True)
        c2 = APIClient(); c2.force_authenticate(other)
        stolen = c2.post('/api/products/products/', {**body, 'name': 'Other', 'ai_estimate_id': est_id}, format='json')
        self.assertEqual(stolen.status_code, 201)
        self.assertIsNone(stolen.json()['ai_estimate'])
        self.assertIsNone(Product.objects.get(pk=stolen.json()['id']).ai_estimate)


class AIHelpersTests(SimpleTestCase):
    def test_images_are_normalised_downscaled_and_stripped(self):
        out, _ = ai.prepare_image(jpeg(size=(4000, 3000)))
        img = Image.open(io.BytesIO(out))
        self.assertEqual(img.format, 'JPEG')
        self.assertLessEqual(max(img.size), ai.MAX_SIDE)
        self.assertFalse(img.getexif())  # EXIF/GPS dropped by re-encoding

    def test_transparent_png_is_accepted(self):
        out, _ = ai.prepare_image(jpeg(mode='RGBA', fmt='PNG'))
        self.assertEqual(Image.open(io.BytesIO(out)).mode, 'RGB')

    def test_sanitize_fixes_swapped_and_absurd_ranges(self):
        v = ai.sanitize(valuation(estimated_low=9000, estimated_high=1000), ['Antiques'], 'INR')
        self.assertLess(v['estimated_low'], v['estimated_high'])
        wide = ai.sanitize(valuation(estimated_low=100, estimated_high=100000), ['Antiques'], 'INR')
        self.assertLessEqual(wide['estimated_high'] / wide['estimated_low'], 4.5)
        self.assertTrue(any('rough guess' in r for r in wide['risks']))

    def test_sanitize_caps_lengths_and_unknown_category(self):
        v = ai.sanitize(valuation(item_name='x' * 500, category='Spaceships', value_drivers=['a'] * 20), ['Antiques'], 'INR')
        self.assertLessEqual(len(v['item_name']), 120)
        self.assertEqual(v['category'], '')
        self.assertLessEqual(len(v['value_drivers']), 5)

    def test_nice_round(self):
        self.assertEqual([ai.nice_round(x) for x in (7, 1247, 18300, 123456)], [7, 1250, 18300, 123500])


class ReviewReportUsesAIEstimateTests(TestCase):
    def test_review_flags_a_starting_price_above_the_ai_estimate(self):
        from django.utils import timezone
        from auctions.models import Auction
        from auctions.review import build_report
        seller = User.objects.create_user(username='rs', email='rs@example.com', password='StrongPassword123!', role='SELLER', email_verified=True)
        est = AIEstimate.objects.create(user=seller, data={'sellable': True, 'estimated_low': 1000, 'estimated_high': 2000, 'currency': 'INR', 'confidence': 'high'})
        p = Product.objects.create(seller=seller, category=Category.objects.create(name='C', slug='c-t'), name='Lot', description='x' * 40, starting_price=1500, condition='Good', status='APPROVED', ai_estimate=est)
        a = Auction.objects.create(product=p, seller=seller, starting_price=5000, min_increment=10, status='PENDING_APPROVAL')
        check = [c for c in build_report(a)['checks'] if c['key'] == 'ai_estimate'][0]
        self.assertEqual(check['status'], 'warn')
        self.assertIn('ABOVE', check['detail'])
