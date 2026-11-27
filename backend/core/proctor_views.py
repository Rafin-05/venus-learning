"""API for exam monitoring (AI proctoring v1).

Endpoints (all under /api/proctoring/, session-authenticated):
- POST   /                      start a session (learner, enrolled, consent required)
- GET    /                      list sessions (own for learners; own courses for
                                instructors; all for staff/admin)
- GET    /<id>/                 session detail with its event timeline
- POST   /<id>/events/          batch-ingest alert events (own active session only)
- POST   /<id>/end/             end a session (own session only)
- POST   /<id>/review/          mark reviewed (course instructor or staff only)

No video is accepted or stored by any endpoint here.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .mentor_views import staff
from .models import Enrollment
from .permissions import Verified
from .proctor_models import (
    EVENT_SEVERITY,
    EVENT_TYPES,
    FLAG_THRESHOLD,
    ProctoredExamSession,
    ProctorEvent,
)
from .proctor_serializers import (
    ProctoredExamSessionSerializer,
    ProctoredExamSessionStartSerializer,
)

VALID_EVENT_TYPES = {event_type for event_type, _ in EVENT_TYPES}
MAX_EVENTS_PER_REQUEST = 50


class ProctoredExamViewSet(viewsets.ModelViewSet):
    permission_classes = [Verified]
    serializer_class = ProctoredExamSessionSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = ProctoredExamSession.objects.select_related(
            "learner", "quiz", "course"
        ).prefetch_related("events").order_by("-started_at", "-id")
        if staff(user):
            return queryset
        if user.role == "instructor":
            return queryset.filter(quiz__course__instructor=user)
        return queryset.filter(learner=user)

    def get_serializer_class(self):
        if self.action == "create":
            return ProctoredExamSessionStartSerializer
        return ProctoredExamSessionSerializer

    def perform_create(self, serializer):
        user = self.request.user
        if user.role != "learner":
            raise PermissionDenied("Only learners start a proctored exam session.")
        quiz = serializer.validated_data["quiz"]
        if not Enrollment.objects.filter(learner=user, course=quiz.course).exists():
            raise PermissionDenied("Enrollment is required.")
        if ProctoredExamSession.objects.filter(
            learner=user, quiz=quiz, status="active"
        ).exists():
            raise ValidationError("You already have an active proctored session for this exam.")
        serializer.save(learner=user, course=quiz.course, consent_at=timezone.now())

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        session = ProctoredExamSession.objects.get(pk=serializer.instance.pk)
        return Response(ProctoredExamSessionSerializer(session).data, status=201)

    def update(self, request, *args, **kwargs):
        raise PermissionDenied("Proctored sessions cannot be edited.")

    def partial_update(self, request, *args, **kwargs):
        raise PermissionDenied("Proctored sessions cannot be edited.")

    def destroy(self, request, *args, **kwargs):
        raise PermissionDenied("Proctored sessions cannot be deleted.")

    @action(detail=True, methods=["post"])
    def events(self, request, pk=None):
        session = self.get_object()
        if session.learner_id != request.user.id:
            raise PermissionDenied("You can only report events for your own session.")
        if session.status != "active":
            raise ValidationError("This session is no longer active.")
        items = request.data.get("events")
        if not isinstance(items, list) or not items or len(items) > MAX_EVENTS_PER_REQUEST:
            raise ValidationError("Provide a list of 1 to 50 events.")
        created = []
        for item in items:
            if not isinstance(item, dict) or item.get("event_type") not in VALID_EVENT_TYPES:
                raise ValidationError("Unknown event type.")
            detail = item.get("detail") or {}
            if not isinstance(detail, dict):
                raise ValidationError("Event detail must be an object.")
            created.append(
                ProctorEvent(
                    session=session,
                    event_type=item["event_type"],
                    severity=EVENT_SEVERITY[item["event_type"]],
                    detail=detail,
                )
            )
        ProctorEvent.objects.bulk_create(created)
        session.recompute_risk_score()
        session.save(update_fields=["risk_score"])
        return Response(ProctoredExamSessionSerializer(session).data, status=201)

    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        session = self.get_object()
        if session.learner_id != request.user.id:
            raise PermissionDenied("You can only end your own session.")
        if session.status != "active":
            raise ValidationError("This session is no longer active.")
        session.ended_at = timezone.now()
        # Flag for instructor review at 60+; this never changes the quiz result.
        session.status = "flagged" if session.risk_score >= FLAG_THRESHOLD else "completed"
        session.save(update_fields=["ended_at", "status"])
        return Response(ProctoredExamSessionSerializer(session).data)

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        session = self.get_object()
        user = request.user
        is_course_instructor = (
            user.role == "instructor" and session.quiz.course.instructor_id == user.id
        )
        if not (staff(user) or is_course_instructor):
            raise PermissionDenied(
                "Only the course instructor or an administrator can review this session."
            )
        if session.status == "active":
            raise ValidationError("End the session before reviewing it.")
        session.status = "reviewed"
        session.review_note = str(request.data.get("review_note") or "")[:500]
        session.reviewed_by = user
        session.reviewed_at = timezone.now()
        session.save(update_fields=["status", "review_note", "reviewed_by", "reviewed_at"])
        return Response(ProctoredExamSessionSerializer(session).data)


def proctor_session_or_404(session_id, user):
    """Helper for reuse by other views: same scoping as the viewset."""
    if staff(user):
        return get_object_or_404(ProctoredExamSession, pk=session_id)
    if user.role == "instructor":
        return get_object_or_404(
            ProctoredExamSession, pk=session_id, quiz__course__instructor=user
        )
    return get_object_or_404(ProctoredExamSession, pk=session_id, learner=user)
