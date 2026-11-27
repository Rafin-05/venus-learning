# Exam monitoring (AI proctoring v1): alert-event sessions + risk score.
# No video is recorded or stored; see backend/core/proctor_models.py.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_alter_wallettransaction_kind_withdrawalrequest_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProctoredExamSession",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("completed", "Completed"),
                            ("flagged", "Flagged for review"),
                            ("reviewed", "Reviewed"),
                        ],
                        default="active",
                        max_length=20,
                    ),
                ),
                ("consent_given", models.BooleanField(default=False)),
                ("consent_at", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("risk_score", models.PositiveSmallIntegerField(default=0)),
                ("review_note", models.TextField(blank=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="proctored_sessions",
                        to="core.course",
                    ),
                ),
                (
                    "learner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="proctored_exam_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "quiz",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="proctored_sessions",
                        to="core.quiz",
                    ),
                ),
                (
                    "quiz_attempt",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="proctored_sessions",
                        to="core.quizattempt",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_proctored_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-started_at", "-id"),
            },
        ),
        migrations.CreateModel(
            name="ProctorEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("NO_FACE", "No face visible in the camera"),
                            ("MULTIPLE_FACES", "More than one face visible"),
                            (
                                "LOOKING_AWAY",
                                "Learner looking away (reserved, not emitted by v1 client)",
                            ),
                            ("TAB_SWITCH", "Exam tab hidden or window lost focus"),
                            ("FULLSCREEN_EXIT", "Left fullscreen during the exam"),
                            ("CAMERA_BLOCKED", "Camera unavailable or permission denied"),
                            (
                                "COPY_ATTEMPT",
                                "Copy, cut, or paste attempted during the exam",
                            ),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("low", "Low"),
                            ("medium", "Medium"),
                            ("high", "High"),
                        ],
                        max_length=10,
                    ),
                ),
                ("detail", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="core.proctoredexamsession",
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at", "-id"),
            },
        ),
    ]
