"""Exam monitoring (AI proctoring v1) for Venus Learning.

When a learner takes an exam, the browser watches (camera + tab focus)
and reports short alert *events* to the server. The server stores only
those events and a deterministic 0-100 risk score.

What this v1 deliberately does NOT do:
- No video is recorded, uploaded, or stored anywhere. There is no video
  upload endpoint and no video field on either model.
- No server-side video analysis (no YOLOv8 / MediaPipe on the server).
  Face presence is checked in the learner's browser only, on a
  best-effort basis, and the browser sends only "face seen / not seen".
- The score NEVER auto-fails, auto-submits, or changes a quiz result.
  It is a review flag for the course instructor only: 0-29 Low,
  30-59 Medium, 60+ High. A session that ends at 60+ is marked
  "flagged" so an instructor can review the event timeline.
"""

from django.conf import settings
from django.db import models

# Event types the API accepts. LOOKING_AWAY is reserved: the v1 browser
# client does not emit it (no gaze tracking is wired up), and
# AUDIO_SUSPICION is not in the list at all (v1 does not listen to audio).
EVENT_TYPES = (
    ("NO_FACE", "No face visible in the camera"),
    ("MULTIPLE_FACES", "More than one face visible"),
    ("LOOKING_AWAY", "Learner looking away (reserved, not emitted by v1 client)"),
    ("TAB_SWITCH", "Exam tab hidden or window lost focus"),
    ("FULLSCREEN_EXIT", "Left fullscreen during the exam"),
    ("CAMERA_BLOCKED", "Camera unavailable or permission denied"),
    ("COPY_ATTEMPT", "Copy, cut, or paste attempted during the exam"),
)

# Deterministic weights used for the risk score. The score is the sum of
# the weights of every event in the session, capped at 100. Documented
# here and in the PR so instructors can see exactly how it is computed.
EVENT_WEIGHTS = {
    "NO_FACE": 15,
    "MULTIPLE_FACES": 20,
    "LOOKING_AWAY": 5,
    "TAB_SWITCH": 10,
    "FULLSCREEN_EXIT": 10,
    "CAMERA_BLOCKED": 15,
    "COPY_ATTEMPT": 10,
}

EVENT_SEVERITY = {
    "NO_FACE": "high",
    "MULTIPLE_FACES": "high",
    "LOOKING_AWAY": "low",
    "TAB_SWITCH": "medium",
    "FULLSCREEN_EXIT": "medium",
    "CAMERA_BLOCKED": "high",
    "COPY_ATTEMPT": "medium",
}

LOW_MAX = 29
MEDIUM_MAX = 59
FLAG_THRESHOLD = 60


def risk_band(score):
    """Low 0-29, Medium 30-59, High 60-100."""
    if score >= FLAG_THRESHOLD:
        return "high"
    if score > LOW_MAX:
        return "medium"
    return "low"


class ProctoredExamSession(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("completed", "Completed"),
        ("flagged", "Flagged for review"),
        ("reviewed", "Reviewed"),
    )

    learner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="proctored_exam_sessions"
    )
    quiz = models.ForeignKey("core.Quiz", on_delete=models.CASCADE, related_name="proctored_sessions")
    course = models.ForeignKey(
        "core.Course", on_delete=models.CASCADE, related_name="proctored_sessions"
    )
    # Linked after the learner submits the quiz; kept nullable because the
    # monitoring session starts before the quiz is submitted.
    quiz_attempt = models.ForeignKey(
        "core.QuizAttempt",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proctored_sessions",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    consent_given = models.BooleanField(default=False)
    consent_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    # Deterministic weighted sum of event weights, capped at 100. Never
    # changes a quiz result; see the module docstring.
    risk_score = models.PositiveSmallIntegerField(default=0)
    review_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_proctored_sessions",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-started_at", "-id")

    def __str__(self):
        return f"Proctored exam for {self.learner} on {self.quiz} ({self.status})"

    def recompute_risk_score(self):
        """Recompute the score from stored events. Returns the new score."""
        # Fresh queryset (not the possibly prefetched related manager),
        # so events created just before this call are always counted.
        total = sum(
            EVENT_WEIGHTS.get(event_type, 0)
            for event_type in ProctorEvent.objects.filter(session=self).values_list(
                "event_type", flat=True
            )
        )
        self.risk_score = min(100, total)
        return self.risk_score

    @property
    def band(self):
        return risk_band(self.risk_score)


class ProctorEvent(models.Model):
    SEVERITY_CHOICES = (("low", "Low"), ("medium", "Medium"), ("high", "High"))

    session = models.ForeignKey(
        ProctoredExamSession, on_delete=models.CASCADE, related_name="events"
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    # Small machine-readable context only, e.g. {"faces": 0} or
    # {"reason": "tab-hidden"}. Never contains images or video.
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return f"{self.event_type} in session {self.session_id} ({self.severity})"
