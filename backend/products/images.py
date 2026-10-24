"""Uploaded product photos: never trust the browser's claimed type or filename."""
import io
import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework import serializers

MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_SIDE = 2400
FORMATS = {'JPEG': ('jpg', 'image/jpeg'), 'PNG': ('png', 'image/png'), 'WEBP': ('webp', 'image/webp')}


def sanitize_upload(f):
    """Open the file with Pillow (so only real images pass), strip metadata by re-encoding, cap the size and
    return a new upload with a random server-chosen name."""
    if f.size > MAX_BYTES:
        raise serializers.ValidationError('Image must be 5MB or smaller.')
    try:
        img = Image.open(f)
        fmt = img.format
        if fmt not in FORMATS:
            raise serializers.ValidationError('Only JPEG, PNG, or WebP images are allowed.')
        if img.width * img.height > MAX_PIXELS:
            raise serializers.ValidationError('Image dimensions are too large.')
        img.load()
        img = ImageOps.exif_transpose(img)
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        if fmt == 'JPEG' and img.mode != 'RGB':
            img = img.convert('RGB')
        out = io.BytesIO()
        img.save(out, fmt, **({'quality': 88} if fmt in ('JPEG', 'WEBP') else {}))  # re-encoding drops EXIF/GPS and any appended payload
    except serializers.ValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise serializers.ValidationError('This file is not a valid image.')
    ext, mime = FORMATS[fmt]
    return SimpleUploadedFile(f'{uuid.uuid4().hex}.{ext}', out.getvalue(), content_type=mime)
