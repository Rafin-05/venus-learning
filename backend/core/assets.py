import io
import uuid
import warnings
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import FileResponse, Http404
from PIL import Image, UnidentifiedImageError
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from .asset_models import UploadedAsset
from .models import Course, Enrollment
from .permissions import Verified
from .publishing import account_is_verified, course_is_published

MAX_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {'image/jpeg': 'JPEG', 'image/png': 'PNG', 'image/webp': 'WEBP'}


def staff(user):
    return bool(user.is_authenticated and (user.is_staff or user.role == 'admin'))


def canonical_image(upload):
    if upload.content_type not in IMAGE_TYPES:
        raise ValidationError('Choose a JPEG, PNG, or WEBP raster image. SVG and HTML are not accepted.')
    try:
        raw = upload.read(MAX_BYTES + 1)
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(raw))
            if image.format != IMAGE_TYPES[upload.content_type]:
                raise ValidationError('The file content does not match its image type.')
            width, height = image.size
            if width > 4096 or height > 4096 or width * height > 16 * 1024 * 1024:
                raise ValidationError('Images must be no larger than 4096 pixels on either side.')
            image.verify()
            image = Image.open(io.BytesIO(raw))
            image.seek(0)
            image = image.convert('RGBA' if image.mode == 'RGBA' or 'transparency' in image.info else 'RGB')
            clean = Image.frombytes(image.mode, image.size, image.tobytes())
            output = io.BytesIO()
            clean.save(output, format='PNG')
        if output.tell() > MAX_BYTES:
            raise ValidationError('The decoded image is too large. Reduce its dimensions.')
        return ContentFile(output.getvalue(), name=uuid.uuid4().hex + '.png')
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning, OSError, ValueError, SyntaxError):
        raise ValidationError('The image cannot be safely decoded.')


class AssetUploadView(APIView):
    permission_classes = [Verified]

    def post(self, request):
        upload, purpose = request.FILES.get('file'), request.data.get('purpose')
        if not upload or purpose not in ('avatar', 'thumbnail', 'document'):
            raise ValidationError('A file and a valid purpose are required.')
        if upload.size > MAX_BYTES:
            raise ValidationError('Files must be no larger than 5 MiB.')
        course = None
        if purpose == 'avatar':
            if request.data.get('course'):
                raise ValidationError('Avatars cannot be attached to a course.')
        else:
            course_id = str(request.data.get('course', ''))
            if not course_id.isdigit():
                raise ValidationError('A numeric course ID is required.')
            course = Course.objects.filter(pk=course_id).first()
            if not course:
                raise ValidationError('Course not found.')
            if not (staff(request.user) or (request.user.role == 'instructor' and request.user.instructor_approved and course.instructor_id == request.user.id)):
                raise PermissionDenied('Only the course instructor or staff can upload course assets.')
        if purpose in ('avatar', 'thumbnail'):
            file = canonical_image(upload)
            content_type, original_name = 'image/png', 'image.png'
        else:
            header = upload.read(5); upload.seek(0)
            if header != b'%PDF-':
                raise ValidationError('Choose a PDF document.')
            file, content_type, original_name = upload, 'application/pdf', 'course-document.pdf'
        asset = UploadedAsset(owner=request.user, course=course, purpose=purpose, content_type=content_type, original_name=original_name, approved=staff(request.user))
        try:
            with transaction.atomic():
                asset.file.save(uuid.uuid4().hex, file, save=False)
                asset.save()
                url = f'{settings.FRONTEND_URL}/api/uploads/{asset.id}/content/'
                if purpose == 'avatar':
                    request.user.profile_pic = url
                    request.user.save(update_fields=['profile_pic'])
                elif purpose == 'thumbnail':
                    course.thumbnail = url
                    if not staff(request.user):
                        course.status = 'pending'
                    course.save(update_fields=['thumbnail', 'status'])
        except Exception:
            if asset.file:
                asset.file.delete(save=False)
            raise
        return Response({'id': str(asset.id), 'url': url, 'purpose': purpose}, status=201)


class AssetContentView(APIView):
    permission_classes = []

    def get(self, request, asset_id):
        asset = UploadedAsset.objects.select_related('owner', 'course__instructor').filter(pk=asset_id).first()
        if not asset:
            raise Http404
        user = request.user
        verified = account_is_verified(user)
        privileged = verified and (staff(user) or user.id == asset.owner_id or (asset.course_id and user.id == asset.course.instructor_id))
        published = bool(asset.course_id and course_is_published(asset.course))
        public = (asset.purpose == 'avatar' and account_is_verified(asset.owner)) or (asset.purpose == 'thumbnail' and published)
        enrolled = bool(verified and published and user.role == 'learner' and Enrollment.objects.filter(course=asset.course, learner=user).exists())
        if not (privileged or (enrolled if asset.purpose == 'document' else public)):
            raise PermissionDenied('This file is not available to your account.')
        try:
            file = asset.file.open('rb')
        except FileNotFoundError:
            raise Http404
        return FileResponse(file, content_type=asset.content_type, as_attachment=asset.purpose == 'document', filename='course-document.pdf' if asset.purpose == 'document' else 'image.png')
