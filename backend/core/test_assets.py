import io
import tempfile
from PIL import Image, PngImagePlugin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase
from .models import User, Course, Enrollment
from .asset_models import UploadedAsset


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AssetWorkflowTests(APITestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='venus-upload-tests-')
        self.addCleanup(directory.cleanup)
        media = override_settings(MEDIA_ROOT=directory.name)
        media.enable(); self.addCleanup(media.disable)
        self.user = User.objects.create_user('owner@example.test', 'SafePassword123!', is_verified=True)
        self.other = User.objects.create_user('other@example.test', 'SafePassword123!', is_verified=True)
        self.instructor = User.objects.create_user('teacher@example.test', 'SafePassword123!', role='instructor', is_verified=True, instructor_approved=True)
        self.course = Course.objects.create(title='Course', description='Content', instructor=self.instructor)

    def image(self, fmt='PNG', metadata=False):
        output = io.BytesIO(); info = PngImagePlugin.PngInfo()
        info.add_text('Comment', '<script>untrusted-metadata</script>')
        Image.new('RGB', (3, 4), 'red').save(output, format=fmt, **({'pnginfo': info} if metadata else {}))
        return SimpleUploadedFile('image.'+fmt.lower(), output.getvalue(), content_type={'PNG':'image/png', 'WEBP':'image/webp', 'JPEG':'image/jpeg'}[fmt])

    def test_fake_image_oversize_svg_and_bad_pdf_rejected(self):
        self.client.force_authenticate(self.user)
        for upload in (SimpleUploadedFile('fake.png', b'not an image', content_type='image/png'), SimpleUploadedFile('huge.png', b'x'*(5*1024*1024+1), content_type='image/png'), SimpleUploadedFile('script.svg', b'<svg onload="alert(1)"/>', content_type='image/svg+xml')):
            self.assertEqual(self.client.post('/api/uploads/', {'purpose':'avatar', 'file':upload}).status_code, 400)
        self.client.force_authenticate(self.instructor)
        response = self.client.post('/api/uploads/', {'purpose':'document', 'course':self.course.id, 'file':SimpleUploadedFile('bad.pdf', b'not a PDF', content_type='application/pdf')})
        self.assertEqual(response.status_code, 400)

    def test_raster_conversion_changes_stored_bytes_to_png(self):
        self.client.force_authenticate(self.user)
        response = self.client.post('/api/uploads/', {'purpose':'avatar', 'file':self.image('WEBP')})
        self.assertEqual(response.status_code, 201)
        asset = UploadedAsset.objects.get(pk=response.data['id'])
        with asset.file.open('rb') as file:
            self.assertEqual(file.read(8), b'\x89PNG\r\n\x1a\n')
        self.client.force_authenticate(None)
        result = self.client.get(response.data['url'])
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result['Content-Type'], 'image/png')
        b''.join(result.streaming_content)

    def test_metadata_is_removed(self):
        self.client.force_authenticate(self.user)
        response = self.client.post('/api/uploads/', {'purpose':'avatar', 'file':self.image(metadata=True)})
        self.assertEqual(response.status_code, 201)
        asset = UploadedAsset.objects.get(pk=response.data['id'])
        with asset.file.open('rb') as file:
            self.assertNotIn(b'untrusted-metadata', file.read())

    def test_private_pdf_requires_enrollment_and_current_publisher_approval(self):
        self.client.force_authenticate(self.instructor)
        response = self.client.post('/api/uploads/', {'purpose':'document', 'course':self.course.id, 'file':SimpleUploadedFile('lesson.pdf', b'%PDF-1.7 test fixture', content_type='application/pdf')})
        self.assertEqual(response.status_code, 201)
        self.client.force_authenticate(self.other)
        self.assertIn(self.client.get(response.data['url']).status_code, (403, 404))
        self.course.status = 'approved'; self.course.save(update_fields=['status'])
        Enrollment.objects.create(learner=self.other, course=self.course)
        result = self.client.get(response.data['url'])
        self.assertEqual(result.status_code, 200)
        self.assertIn('attachment', result['Content-Disposition'])
        self.assertEqual(result['X-Content-Type-Options'], 'nosniff')
        self.assertIn('no-store', result['Cache-Control']); b''.join(result.streaming_content)
        self.instructor.instructor_approved = False; self.instructor.save(update_fields=['instructor_approved'])
        self.assertIn(self.client.get(response.data['url']).status_code, (403, 404))

    def test_upload_permissions_and_invalid_course_are_controlled(self):
        self.assertIn(self.client.post('/api/uploads/', {'purpose':'avatar', 'file':self.image()}).status_code, (401, 403))
        unverified = User.objects.create_user('unverified@example.test', 'SafePassword123!')
        self.client.force_authenticate(unverified)
        self.assertEqual(self.client.post('/api/uploads/', {'purpose':'avatar', 'file':self.image()}).status_code, 403)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post('/api/uploads/', {'purpose':'thumbnail', 'course':self.course.id, 'file':self.image()}).status_code, 403)
        self.assertEqual(self.client.post('/api/uploads/', {'purpose':'thumbnail', 'course':'not-a-number', 'file':self.image()}).status_code, 400)

    def test_thumbnail_edit_requires_reapproval(self):
        self.course.status = 'approved'; self.course.save(update_fields=['status'])
        self.client.force_authenticate(self.instructor)
        response = self.client.post('/api/uploads/', {'purpose':'thumbnail', 'course':self.course.id, 'file':self.image()})
        self.assertEqual(response.status_code, 201)
        self.course.refresh_from_db(); self.assertEqual(self.course.status, 'pending')
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(response.data['url']).status_code, (403, 404))
        self.course.status = 'approved'; self.course.save(update_fields=['status'])
        result = self.client.get(response.data['url']); self.assertEqual(result.status_code, 200); b''.join(result.streaming_content)

    def test_authenticated_multipart_upload_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post('/api/uploads/', {'purpose':'avatar', 'file':self.image()}).status_code, 403)
        token = client.get('/api/auth/csrf/').data['csrfToken']
        self.assertEqual(client.post('/api/uploads/', {'purpose':'avatar', 'file':self.image()}, HTTP_X_CSRFTOKEN=token).status_code, 201)
