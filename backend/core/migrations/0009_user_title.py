from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0008_course_creation_workflow')]
    operations = [
        migrations.AddField(
            model_name='user',
            name='title',
            field=models.CharField(blank=True, max_length=150),
        ),
    ]
