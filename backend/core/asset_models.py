import uuid
from django.conf import settings
from django.db import models

def asset_upload_to(instance, filename):
    return f'assets/{uuid.uuid4().hex}'

class UploadedAsset(models.Model):
    PURPOSES = (('avatar','Avatar'),('thumbnail','Course thumbnail'),('document','Document'))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='uploaded_assets')
    course = models.ForeignKey('core.Course', null=True, blank=True, on_delete=models.CASCADE, related_name='uploaded_assets')
    purpose = models.CharField(max_length=20, choices=PURPOSES)
    file = models.FileField(upload_to=asset_upload_to)
    content_type = models.CharField(max_length=100)
    original_name = models.CharField(max_length=255, blank=True)
    createdat = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)
    class Meta:
        ordering = ('-createdat',)
