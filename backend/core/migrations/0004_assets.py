from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid
import core.asset_models
class Migration(migrations.Migration):
    dependencies=[('core','0003_contest_prizes')]
    operations=[migrations.CreateModel(name='UploadedAsset',fields=[('id',models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),('purpose',models.CharField(choices=[('avatar','Avatar'),('thumbnail','Course thumbnail'),('document','Document')],max_length=20)),('file',models.FileField(upload_to=core.asset_models.asset_upload_to)),('content_type',models.CharField(max_length=100)),('original_name',models.CharField(blank=True,max_length=255)),('createdat',models.DateTimeField(auto_now_add=True)),('approved',models.BooleanField(default=False)),('course',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name='uploaded_assets',to='core.course')),('owner',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='uploaded_assets',to=settings.AUTH_USER_MODEL))])]
