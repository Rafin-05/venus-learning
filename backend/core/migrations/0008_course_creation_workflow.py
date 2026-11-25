from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_mentor_hiring'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='access_duration_days',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='course',
            name='completion_threshold',
            field=models.PositiveSmallIntegerField(default=90),
        ),
        migrations.AddField(
            model_name='course',
            name='enrollment_open',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='course',
            name='is_free',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='course',
            name='language',
            field=models.CharField(default='en', max_length=20),
        ),
        migrations.AddField(
            model_name='course',
            name='outcomes',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='course',
            name='prerequisites',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='course',
            name='price',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10),
        ),
        migrations.AddField(
            model_name='course',
            name='promo_provider_video_id',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='course',
            name='promo_video_url',
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name='course',
            name='subcategory',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='course',
            name='subtitle',
            field=models.CharField(blank=True, max_length=300),
        ),
        migrations.AddField(
            model_name='course',
            name='target_audience',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='course',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='course',
            name='level',
            field=models.CharField(blank=True, choices=[('beginner', 'Beginner'), ('intermediate', 'Intermediate'), ('advanced', 'Advanced')], max_length=50),
        ),
        migrations.AddField(
            model_name='lesson',
            name='description',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='lesson',
            name='duration_seconds',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='lesson',
            name='is_preview',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='lesson',
            name='is_required',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='lesson',
            name='provider',
            field=models.CharField(default='youtube', max_length=20),
        ),
        migrations.AddField(
            model_name='lesson',
            name='provider_video_id',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='lesson_type',
            field=models.CharField(choices=[('video', 'Video'), ('document', 'Document'), ('coding', 'Coding'), ('resource', 'Resource'), ('quiz', 'Quiz'), ('assignment', 'Assignment')], default='document', max_length=20),
        ),
        migrations.AddField(
            model_name='lessonprogress',
            name='duration_seconds',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='lessonprogress',
            name='resume_position_seconds',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='lessonprogress',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='lessonprogress',
            name='watch_percentage',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='lessonprogress',
            name='watched_seconds',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='quiz',
            name='attempts_allowed',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='quiz',
            name='lesson',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='quizzes', to='core.lesson'),
        ),
        migrations.AddField(
            model_name='quiz',
            name='show_answers',
            field=models.CharField(choices=[('immediate', 'Immediately'), ('after_review', 'After review'), ('never', 'Never')], default='after_review', max_length=20),
        ),
        migrations.AddField(
            model_name='quiz',
            name='shuffle_options',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='quiz',
            name='shuffle_questions',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='quiz',
            name='time_limit_minutes',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='CourseReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('decision', models.CharField(choices=[('submitted', 'Submitted for review'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('changes_requested', 'Changes requested')], max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='course_reviews', to='core.course')),
                ('reviewer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='course_reviews', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at', '-id']},
        ),
        migrations.CreateModel(
            name='CourseResource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('external_url', models.URLField(blank=True)),
                ('downloadable', models.BooleanField(default=True)),
                ('original_name', models.CharField(blank=True, max_length=255)),
                ('mime_type', models.CharField(blank=True, max_length=100)),
                ('size_bytes', models.PositiveIntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('asset', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='course_resources', to='core.uploadedasset')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='resources', to='core.course')),
                ('lesson', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='resources', to='core.lesson')),
            ],
            options={'ordering': ['created_at', 'id']},
        ),
        migrations.CreateModel(
            name='Assignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('instructions', models.TextField()),
                ('due_at', models.DateTimeField(blank=True, null=True)),
                ('max_points', models.PositiveIntegerField(default=100)),
                ('rubric', models.TextField(blank=True)),
                ('accepted_types', models.CharField(choices=[('file', 'File upload'), ('text', 'Text response'), ('both', 'File or text')], default='both', max_length=10)),
                ('is_required', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='core.course')),
                ('lesson', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assignments', to='core.lesson')),
            ],
            options={'ordering': ['created_at', 'id']},
        ),
        migrations.CreateModel(
            name='AssignmentSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text_response', models.TextField(blank=True)),
                ('attempt_no', models.PositiveIntegerField(default=1)),
                ('status', models.CharField(choices=[('submitted', 'Submitted'), ('late', 'Late'), ('under_review', 'Under review'), ('graded', 'Graded'), ('needs_resubmission', 'Needs resubmission')], default='submitted', max_length=20)),
                ('score', models.PositiveIntegerField(blank=True, null=True)),
                ('feedback', models.TextField(blank=True)),
                ('graded_at', models.DateTimeField(blank=True, null=True)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('asset', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assignment_submissions', to='core.uploadedasset')),
                ('assignment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submissions', to='core.assignment')),
                ('graded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='graded_submissions', to=settings.AUTH_USER_MODEL)),
                ('learner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignment_submissions', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-submitted_at', '-id']},
        ),
    ]
