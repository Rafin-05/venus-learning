# Generated for mentor live sessions (start/end + negotiated pricing).
# Renumbered 0013 -> 0014: PR #18 (looking-away detection) also shipped a
# 0013 depending on 0012_focus_session, so two 0013 leaves made Django
# refuse to migrate ("conflicting migrations"). This file now depends on
# that 0013, giving one linear chain: 0012 -> 0013_alter_proctorevent -> 0014.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_alter_proctorevent_event_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='mentoroffer',
            name='pricing_type',
            field=models.CharField(choices=[('hourly', 'Hourly'), ('fixed', 'Fixed amount')], default='hourly', max_length=10),
        ),
        migrations.AddField(
            model_name='mentoroffer',
            name='agreed_amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='mentorsession',
            name='pricing_type',
            field=models.CharField(choices=[('hourly', 'Hourly'), ('fixed', 'Fixed amount')], default='hourly', max_length=10),
        ),
        migrations.AddField(
            model_name='mentorsession',
            name='agreed_amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='mentorsession',
            name='started_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='mentorsession',
            name='ended_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='mentorsession',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending mentor confirmation'), ('confirmed', 'Confirmed'), ('live', 'Live'), ('cancelled', 'Cancelled'), ('completed', 'Completed')], default='pending', max_length=20),
        ),
    ]
