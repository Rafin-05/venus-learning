from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0005_alter_uploadedasset_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_demo_account',
            field=models.BooleanField(default=False),
        ),
    ]
