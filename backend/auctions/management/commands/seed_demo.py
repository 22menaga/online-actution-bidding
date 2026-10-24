import io
import random
from datetime import timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFilter

from accounts.models import BuyerProfile, SellerProfile, User
from auctions.models import Auction
from products.models import Category, Product, ProductImage

# name, category, start price, increment, description, palette (top, bottom, accent), motif, hours until end (negative start offset for upcoming)
ITEMS = [
    ('Vintage Film Camera', 'Antiques', '300', '10', 'Fully restored 1960s rangefinder with original leather case and a sharp 45mm f/1.8 lens. Shutter speeds verified.', ('#2b1d4e', '#0e0a1f', '#ffd27a'), 'camera', 3),
    ('Gold Pocket Watch', 'Jewellery', '900', '50', '18k hunter-case pocket watch, Swiss movement, serviced this year. Comes with a period chain.', ('#3a2a12', '#120c05', '#ffd27a'), 'watch', 9),
    ('Oil Painting - Harbour at Dusk', 'Art', '500', '25', 'Signed oil on canvas, 60 x 90 cm, in a hand-carved gilt frame. Provenance letter included.', ('#12304a', '#060b18', '#ff9a62'), 'painting', 15),
    ('Rare Jazz Vinyl Collection', 'Music', '150', '5', 'Twelve first-pressing jazz LPs in excellent condition, with original sleeves and liner notes.', ('#3b1230', '#0d0614', '#ff5c9a'), 'vinyl', 22),
    ('Antique Porcelain Vase', 'Antiques', '700', '20', 'Hand-painted early twentieth-century vase, no chips or restoration. Display stand included.', ('#102f3a', '#050f14', '#6ee7d8'), 'vase', 30),
    ('Art Deco Table Lamp', 'Antiques', '240', '10', 'Chrome and frosted-glass lamp from the 1930s, rewired to modern safety standards.', ('#2a1f5c', '#0b0820', '#7c5cff'), 'lamp', -26),
]


def hex2rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def artwork(palette, motif, seed):
    """Procedural product artwork so the demo looks finished without stock photos. Drawn at 2x then downsampled."""
    rnd = random.Random(seed)
    W, H = 1600, 1200
    top, bottom, accent = (hex2rgb(c) for c in palette)
    img = Image.new('RGB', (W, H))
    px = ImageDraw.Draw(img)
    for y in range(H):  # vertical gradient
        t = y / H
        px.line([(0, y), (W, y)], fill=tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)))
    glow = Image.new('RGB', (W, H), (0, 0, 0))
    ImageDraw.Draw(glow).ellipse((W * .2, H * .15, W * .8, H * .85), fill=tuple(int(c * .55) for c in accent))
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    img = Image.blend(img, Image.composite(glow, img, glow.convert('L')), .75)
    d = ImageDraw.Draw(img, 'RGBA')
    for _ in range(60):  # dust / bokeh
        x, y, r = rnd.randrange(W), rnd.randrange(H), rnd.randrange(3, 14)
        d.ellipse((x - r, y - r, x + r, y + r), fill=accent + (rnd.randrange(30, 90),))
    cx, cy = W // 2, H // 2
    a, dark = accent + (255,), (14, 10, 28, 255)
    if motif == 'camera':
        d.rounded_rectangle((cx - 380, cy - 190, cx + 380, cy + 210), 50, fill=dark, outline=a, width=10)
        d.rounded_rectangle((cx - 380, cy - 190, cx + 380, cy - 70), 40, fill=accent + (60,))
        for r, w in ((170, 14), (115, 8), (60, 0)):
            d.ellipse((cx - r, cy + 10 - r, cx + r, cy + 10 + r), outline=a, width=w, fill=dark if r > 60 else accent + (200,))
        d.rectangle((cx + 220, cy - 260, cx + 320, cy - 190), fill=a)
    elif motif == 'watch':
        d.rounded_rectangle((cx - 60, cy - 470, cx + 60, cy - 250), 30, fill=a)
        d.ellipse((cx - 300, cy - 300, cx + 300, cy + 300), fill=dark, outline=a, width=16)
        d.ellipse((cx - 250, cy - 250, cx + 250, cy + 250), outline=accent + (120,), width=4)
        for k in range(12):
            import math
            ang = k * math.pi / 6
            d.line((cx + 205 * math.sin(ang), cy - 205 * math.cos(ang), cx + 235 * math.sin(ang), cy - 235 * math.cos(ang)), fill=a, width=10)
        d.line((cx, cy, cx + 20, cy - 150), fill=a, width=14)
        d.line((cx, cy, cx + 120, cy + 60), fill=a, width=10)
    elif motif == 'painting':
        d.rectangle((cx - 480, cy - 340, cx + 480, cy + 340), fill=a)
        d.rectangle((cx - 440, cy - 300, cx + 440, cy + 300), fill=(10, 20, 40, 255))
        d.rectangle((cx - 440, cy + 30, cx + 440, cy + 300), fill=(18, 60, 90, 255))
        d.ellipse((cx - 110, cy - 150, cx + 110, cy + 70), fill=(255, 170, 90, 255))
        d.polygon([(cx - 440, cy + 30), (cx - 200, cy - 90), (cx + 60, cy + 30)], fill=(30, 25, 55, 255))
        for y in range(cy + 60, cy + 290, 36):
            d.line((cx - 400, y, cx + 400, y), fill=(255, 170, 90, 70), width=6)
    elif motif == 'vinyl':
        d.rectangle((cx - 120, cy - 360, cx + 520, cy + 360), fill=accent + (110,))
        d.ellipse((cx - 400, cy - 360, cx + 320, cy + 360), fill=(12, 8, 20, 255))
        for r in range(120, 350, 24):
            d.ellipse((cx - 40 - r, cy - r, cx - 40 + r, cy + r), outline=(255, 255, 255, 28), width=3)
        d.ellipse((cx - 130, cy - 90, cx + 50, cy + 90), fill=a)
        d.ellipse((cx - 55, cy - 15, cx - 25, cy + 15), fill=dark)
    elif motif == 'vase':
        d.polygon([(cx - 90, cy - 380), (cx + 90, cy - 380), (cx + 60, cy - 220), (cx + 300, cy + 40), (cx + 190, cy + 380), (cx - 190, cy + 380), (cx - 300, cy + 40), (cx - 60, cy - 220)], fill=(235, 240, 245, 255))
        d.polygon([(cx - 70, cy - 380), (cx + 70, cy - 380), (cx + 60, cy - 330), (cx - 60, cy - 330)], fill=a)
        for k in range(5):
            d.ellipse((cx - 60 + k * 6 - 120, cy - 40 + k * 40, cx + 60 - k * 6 + 120, cy + 20 + k * 40), outline=accent + (160,), width=6)
    else:  # lamp
        d.polygon([(cx - 240, cy - 130), (cx + 240, cy - 130), (cx + 150, cy - 400), (cx - 150, cy - 400)], fill=accent + (200,), outline=a)
        d.rectangle((cx - 28, cy - 130, cx + 28, cy + 280), fill=a)
        d.ellipse((cx - 220, cy + 250, cx + 220, cy + 360), fill=a)
    img = img.filter(ImageFilter.GaussianBlur(.6)).resize((1000, 750), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=88)
    return buf.getvalue()


class Command(BaseCommand):
    help = 'Create demo users (password: DemoPass12345!), artwork and auctions for local development. Safe to re-run.'

    def handle(self, *args, **opts):
        pw = 'DemoPass12345!'
        admin, _ = User.objects.get_or_create(username='demo_admin', defaults={'email': 'admin@example.com', 'role': 'ADMIN', 'email_verified': True, 'is_staff': True, 'is_superuser': True})
        seller, _ = User.objects.get_or_create(username='demo_seller', defaults={'email': 'seller@example.com', 'role': 'SELLER', 'email_verified': True})
        for u in (admin, seller):
            u.set_password(pw); u.save()
        SellerProfile.objects.update_or_create(user=seller, defaults={'approved': True, 'verified': True, 'business_name': 'Demo Antiques & Co.'})
        for n in ('demo_buyer', 'demo_buyer2'):
            u, _ = User.objects.get_or_create(username=n, defaults={'email': f'{n}@example.com', 'role': 'BUYER', 'email_verified': True})
            u.set_password(pw); u.save(); BuyerProfile.objects.get_or_create(user=u)

        now = timezone.now()
        for i, (name, cat, price, inc, desc, palette, motif, hours) in enumerate(ITEMS):
            c, _ = Category.objects.get_or_create(slug=cat.lower(), defaults={'name': cat})
            upcoming = hours < 0
            p, made = Product.objects.get_or_create(seller=seller, name=name, defaults={'category': c, 'description': desc, 'starting_price': Decimal(price), 'condition': 'Excellent', 'status': 'AUCTION'})
            if made:
                ProductImage.objects.create(product=p, alt_text=name).image.save(f'demo_{motif}.jpg', ContentFile(artwork(palette, motif, i)), save=True)
                start, end = (now + timedelta(hours=2), now + timedelta(hours=2 - hours)) if upcoming else (now - timedelta(hours=1), now + timedelta(hours=hours))
                Auction.objects.create(product=p, seller=seller, starting_price=Decimal(price), min_increment=Decimal(inc), start_at=start, end_at=end, status='SCHEDULED' if upcoming else 'LIVE')
        # One listing waiting in the admin's scheduling queue (seller asked for 24/7; admin picks the time).
        c, _ = Category.objects.get_or_create(slug='music', defaults={'name': 'Music'})
        p, made = Product.objects.get_or_create(seller=seller, name='Signed Concert Poster', defaults={'category': c, 'description': 'Original 1974 tour poster signed by the band, framed behind UV-protective glass. Certificate of authenticity included.', 'starting_price': Decimal('400'), 'condition': 'Very good', 'status': 'APPROVED'})
        if made:
            ProductImage.objects.create(product=p, alt_text=p.name).image.save('demo_poster.jpg', ContentFile(artwork(('#3b1230', '#0d0614', '#ff5c9a'), 'painting', 11)), save=True)
            Auction.objects.create(product=p, seller=seller, starting_price=Decimal('400'), min_increment=Decimal('20'), status='PENDING_APPROVAL', is_24_7=True, seller_note='Happy to run 24/7 for a week.')
        self.stdout.write(self.style.SUCCESS('Seeded. Logins (password DemoPass12345!): demo_buyer, demo_buyer2, demo_seller, demo_admin (Django admin at /admin/)'))
