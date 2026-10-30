import io
import warnings
from urllib.parse import urlsplit

from PIL import Image, ImageOps, UnidentifiedImageError
from django.core.exceptions import ValidationError

from .models import PostImage

MAX_POST_IMAGES = 5
MAX_IMAGE_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_IMAGE_SIDE = 8_000
OUTPUT_IMAGE_SIDE = 2_048


def sanitize_post_image(upload):
    if not upload or upload.size > MAX_IMAGE_UPLOAD_BYTES:
        raise ValueError("사진은 한 장당 5MB 이하로 올려 주세요.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(upload) as source:
                if source.format not in ('PNG', 'JPEG', 'WEBP') or getattr(source, 'n_frames', 1) != 1:
                    raise ValueError("JPG, PNG, WebP 사진만 올릴 수 있어요.")
                width, height = source.size
                if width < 1 or height < 1 or width > MAX_IMAGE_SIDE or height > MAX_IMAGE_SIDE or width * height > MAX_IMAGE_PIXELS:
                    raise ValueError("사진의 크기가 너무 커요. 2,000만 픽셀 이하의 사진을 선택해 주세요.")
                source.load()
                image = ImageOps.exif_transpose(source)
                if 'A' in image.getbands() or 'transparency' in image.info:
                    rgba = image.convert('RGBA')
                    clean = Image.new('RGB', rgba.size, 'white')
                    clean.paste(rgba, mask=rgba.getchannel('A'))
                else:
                    clean = image.convert('RGB')
                clean.thumbnail((OUTPUT_IMAGE_SIDE, OUTPUT_IMAGE_SIDE), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                clean.save(output, format='JPEG', quality=86, optimize=True, progressive=True)
                return {'image_data': output.getvalue(), 'content_type': 'image/jpeg'}
    except ValueError:
        raise
    except (OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError) as exc:
        raise ValueError("사진 파일을 읽을 수 없어요. JPG, PNG, WebP 파일인지 확인해 주세요.") from exc


def validate_post_image_url(value):
    value = (value or '').strip()
    if not value:
        return ''
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme.lower() == 'https'
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
            and len(value) <= 2048
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValidationError("이미지 링크는 https://로 시작하는 공개 이미지 주소를 입력해 주세요.")
    return value


def save_post_images(post, uploads=(), image_urls=(), remove_ids=()):
    remove_ids = list(dict.fromkeys(remove_ids))
    current_count = post.images.count()
    removed_count = post.images.filter(pk__in=remove_ids).count() if remove_ids else 0
    position = current_count - removed_count
    additions = []
    for image in uploads:
        additions.append(PostImage(post=post, position=position, **image))
        position += 1
    for image_url in image_urls:
        additions.append(PostImage(post=post, position=position, image_url=image_url))
        position += 1
    if position > MAX_POST_IMAGES:
        raise ValidationError("게시글 사진은 최대 5장까지 등록할 수 있어요.")
    if remove_ids:
        post.images.filter(pk__in=remove_ids).delete()
    PostImage.objects.bulk_create(additions)
