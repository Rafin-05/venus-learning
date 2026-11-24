from decimal import Decimal

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_user_is_demo_account'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MentorProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('qualifications', models.TextField(blank=True)),
                ('topics', models.CharField(blank=True, max_length=500)),
                ('hourly_rate', models.DecimalField(decimal_places=2, max_digits=10)),
                ('is_available', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='mentor_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ('user__full_name', 'id')},
        ),
        migrations.CreateModel(
            name='Wallet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('balance', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='wallet', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='SessionRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('topic', models.CharField(max_length=200)),
                ('problem', models.TextField()),
                ('tried', models.TextField(blank=True)),
                ('preferred_duration_hours', models.PositiveSmallIntegerField(choices=[(1, '1 hour'), (2, '2 hours')], default=1)),
                ('preferred_times', models.JSONField(blank=True, default=list)),
                ('status', models.CharField(choices=[('open', 'Open'), ('booked', 'Booked'), ('closed', 'Closed')], default='open', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='session_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ('-created_at', '-id')},
        ),
        migrations.CreateModel(
            name='MentorOffer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hourly_rate', models.DecimalField(decimal_places=2, max_digits=10)),
                ('proposed_time', models.DateTimeField()),
                ('message', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('declined', 'Declined')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('mentor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mentor_offers', to=settings.AUTH_USER_MODEL)),
                ('mentor_profile', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='offers', to='core.mentorprofile')),
                ('session_request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='offers', to='core.sessionrequest')),
            ],
            options={'ordering': ('created_at', 'id')},
        ),
        migrations.CreateModel(
            name='MentorSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(choices=[('browse', 'Browse Mentors'), ('request', 'Session Request')], default='browse', max_length=10)),
                ('topic', models.CharField(max_length=200)),
                ('duration_hours', models.PositiveSmallIntegerField(choices=[(1, '1 hour'), (2, '2 hours')], default=1)),
                ('hourly_rate', models.DecimalField(decimal_places=2, max_digits=10)),
                ('total_fee', models.DecimalField(decimal_places=2, max_digits=12)),
                ('scheduled_at', models.DateTimeField()),
                ('meet_link', models.URLField(blank=True)),
                ('status', models.CharField(choices=[('pending', 'Pending mentor confirmation'), ('confirmed', 'Confirmed'), ('cancelled', 'Cancelled'), ('completed', 'Completed')], default='pending', max_length=20)),
                ('payment_status', models.CharField(choices=[('unpaid', 'Unpaid'), ('paid', 'Paid'), ('refunded', 'Refunded')], default='unpaid', max_length=20)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('mentor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mentor_sessions_as_mentor', to=settings.AUTH_USER_MODEL)),
                ('mentor_profile', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sessions', to='core.mentorprofile')),
                ('offer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sessions', to='core.mentoroffer')),
                ('session_request', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sessions', to='core.sessionrequest')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mentor_sessions_as_student', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ('-scheduled_at', '-id')},
        ),
        migrations.CreateModel(
            name='WalletTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('top_up', 'Top-up'), ('session_payment', 'Session payment'), ('mentor_credit', 'Mentor credit'), ('platform_deduction', 'Platform deduction'), ('refund', 'Refund')], max_length=20)),
                ('status', models.CharField(choices=[('completed', 'Completed'), ('paid', 'Paid'), ('credited', 'Credited to mentor'), ('refunded', 'Refunded'), ('deduction', 'Deduction applied')], default='completed', max_length=20)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('fee_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('deduction_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('credited_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('note', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('session', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='wallet_transactions', to='core.mentorsession')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='wallet_transactions', to=settings.AUTH_USER_MODEL)),
                ('wallet', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='core.wallet')),
            ],
            options={'ordering': ('-created_at', '-id')},
        ),
        migrations.CreateModel(
            name='SessionRating',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('comment', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('mentor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='session_ratings_received', to=settings.AUTH_USER_MODEL)),
                ('session', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='rating', to='core.mentorsession')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='session_ratings_given', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ('-created_at', '-id')},
        ),
        migrations.AddConstraint(
            model_name='mentoroffer',
            constraint=models.UniqueConstraint(fields=('session_request', 'mentor'), name='unique_offer_per_mentor_request'),
        ),
    ]
