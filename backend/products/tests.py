from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import User
from products.models import Category,Product
class ProductPermissionTests(TestCase):
    def test_default_categories_are_available_for_seller_listings(self):
        self.assertGreaterEqual(Category.objects.filter(active=True).count(), 6)
        self.assertTrue(Category.objects.filter(slug='electronics-technology',active=True).exists())

    def setUp(self):
        self.seller=User.objects.create_user(username='product-seller',email='product-seller@example.com',password='StrongPassword123!',role='SELLER')
        self.buyer=User.objects.create_user(username='product-buyer',email='product-buyer@example.com',password='StrongPassword123!',role='BUYER')
        self.category=Category.objects.create(name='Product tools',slug='product-tools')
        self.product=Product.objects.create(seller=self.seller,category=self.category,name='Tool',description='x',starting_price=10,condition='New',status='APPROVED')
        self.client=APIClient()

    def test_draft_product_is_not_public(self):
        s=User.objects.create_user(username='s',email='s@x.com',password='StrongPassword123!',role='SELLER')
        c=Category.objects.create(name='Tools',slug='tools'); product=Product.objects.create(seller=s,category=c,name='Tool',description='x',starting_price=10,condition='New')
        self.assertEqual(product.status,Product.Status.DRAFT)

    def test_buyer_cannot_submit_edit_or_delete_public_product(self):
        self.client.force_authenticate(self.buyer)
        submit=self.client.post(f'/api/products/products/{self.product.id}/submit/')
        update=self.client.patch(f'/api/products/products/{self.product.id}/',{'name':'Changed'},format='json')
        delete=self.client.delete(f'/api/products/products/{self.product.id}/')
        self.assertEqual(submit.status_code,403)
        self.assertEqual(update.status_code,403)
        self.assertEqual(delete.status_code,403)

    def test_seller_cannot_review_own_pending_product(self):
        self.product.status='PENDING_APPROVAL'
        self.product.save(update_fields=['status'])
        self.client.force_authenticate(self.seller)
        response=self.client.post(f'/api/products/products/{self.product.id}/review/',{'decision':'APPROVED'},format='json')
        self.assertEqual(response.status_code,403)

    def test_seller_cannot_edit_approved_product(self):
        self.client.force_authenticate(self.seller)
        response=self.client.patch(f'/api/products/products/{self.product.id}/',{'name':'Changed'},format='json')
        self.assertEqual(response.status_code,403)
