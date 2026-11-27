from rest_framework import serializers

from .proctor_models import ProctoredExamSession, ProctorEvent


class ProctorEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProctorEvent
        fields = ("id", "session", "event_type", "severity", "detail", "created_at")
        read_only_fields = fields


class ProctoredExamSessionSerializer(serializers.ModelSerializer):
    learner_name = serializers.CharField(source="learner.full_name", read_only=True)
    quiz_title = serializers.CharField(source="quiz.title", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    risk_band = serializers.CharField(source="band", read_only=True)
    event_count = serializers.SerializerMethodField()
    # Method fields (not a nested related field): the viewset prefetches
    # events, and a prefetched related manager would serve a stale cached
    # list right after new events are ingested. Fresh querysets here keep
    # the response correct after POST /events/.
    events = serializers.SerializerMethodField()

    class Meta:
        model = ProctoredExamSession
        fields = (
            "id", "learner", "learner_name", "quiz", "quiz_title", "course",
            "course_title", "quiz_attempt", "status", "consent_given",
            "consent_at", "started_at", "ended_at", "risk_score", "risk_band",
            "event_count", "events", "review_note", "reviewed_by", "reviewed_at",
        )
        read_only_fields = fields

    def get_event_count(self, instance):
        return ProctorEvent.objects.filter(session=instance).count()

    def get_events(self, instance):
        events = ProctorEvent.objects.filter(session=instance).order_by("-created_at", "-id")
        return ProctorEventSerializer(events, many=True).data


class ProctoredExamSessionStartSerializer(serializers.ModelSerializer):
    """Start a session. Consent is mandatory: without consent_given=true
    the API refuses to start monitoring (400)."""

    class Meta:
        model = ProctoredExamSession
        fields = ("quiz", "consent_given")

    def validate_consent_given(self, value):
        if not value:
            raise serializers.ValidationError(
                "Camera consent is required before exam monitoring can start."
            )
        return value
