import ipaddress
import json
import logging
import re
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, connection, transaction
from django.db.models import Avg, F, Q
from django.shortcuts import get_object_or_404
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .asset_models import UploadedAsset
from .mentor_models import MentorProfile, MentorSession
from .mentor_serializers import MentorProfileSerializer, MentorSessionSerializer
from .models import *
from .publishing import published_courses, course_is_published
from .permissions import Verified, EditorOnly, StaffOnly
from .serializers import *
from .video import youtube_embed_url


logger = logging.getLogger(__name__)


def staff(user):
    return is_staff_user(user)


def approved(user):
    return bool(user and user.is_authenticated and user.is_active and user.role == 'instructor' and user.instructor_approved)


def require_editor(user, course):
    if not owns_course(user, course):
        raise PermissionDenied('Only the course instructor or an administrator can change this content.')


def review_after_edit(user, course):
    if not staff(user) and course.status != 'pending':
        Course.objects.filter(pk=course.pk).update(status='pending')


def attach_thumbnail_asset(course, user):
    """Link a pre-uploaded thumbnail asset to its course.

    An instructor can upload a thumbnail on the Create course page before
    the course exists, so the asset is created unattached. Once the course
    is created/updated with that asset's URL as its thumbnail, attach it
    here, otherwise learners can never see the image: AssetContentView
    only serves a thumbnail publicly when it belongs to a published course.
    A URL that is not one of this user's uploaded thumbnails is ignored.
    """
    if not course.thumbnail:
        return
    match = re.search(r'/api/uploads/([0-9a-f-]{36})/content/', course.thumbnail)
    if not match:
        return
    UploadedAsset.objects.filter(
        pk=match.group(1), owner=user, purpose='thumbnail'
    ).filter(Q(course__isnull=True) | Q(course=course)).update(course=course)


def activity(user):
    today = timezone.localdate()
    DailyActivity.objects.get_or_create(user=user, day=today)
    days = set(DailyActivity.objects.filter(user=user, day__gte=today-timedelta(days=3650)).values_list('day', flat=True))
    streak, day = 0, today
    while day in days:
        streak += 1
        day -= timedelta(days=1)
    User.objects.filter(pk=user.pk).update(current_streak=streak)
    user.current_streak = streak


def client_ip(request):
    raw = request.META.get('HTTP_X_REAL_IP') if settings.TRUST_PROXY else None
    raw = raw or request.META.get('REMOTE_ADDR', '127.0.0.1')
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return '127.0.0.1'


def rate_attempt(email, ip, now):
    attempt, _ = LoginAttempt.objects.select_for_update().get_or_create(email=email, ip=ip)
    if (attempt.locked_until and attempt.locked_until <= now) or (not attempt.locked_until and now - attempt.updated_at >= timedelta(minutes=15)):
        attempt.failures = 0
        attempt.locked_until = None
        attempt.save(update_fields=['failures', 'locked_until', 'updated_at'])
    return attempt


def throttle_action(request, action_name, maximum=10):
    now = timezone.now()
    with transaction.atomic():
        attempt = rate_attempt(f'{action_name}@rate.invalid', client_ip(request), now)
        if attempt.locked_until and attempt.locked_until > now:
            return True
        attempt.failures += 1
        if attempt.failures >= maximum:
            attempt.locked_until = now + timedelta(minutes=15)
        attempt.save(update_fields=['failures', 'locked_until', 'updated_at'])
    return False


def require_object_body(request):
    if not isinstance(request.data, Mapping):
        raise ValidationError({'detail': 'Request body must be a JSON object.'})


def user_action_throttled(user, action_name, cooldown=timedelta(seconds=60)):
    """Return whether this account has requested the action during its cooldown.

    LoginAttempt is deliberately keyed separately from login attempts so this
    does not change authentication lockout behaviour.  The row lock also makes
    concurrent resend requests for one account serialize safely.
    """
    now = timezone.now()
    key = f'{action_name}-{user.pk}@rate.invalid'
    with transaction.atomic():
        attempt, created = LoginAttempt.objects.select_for_update().get_or_create(email=key, ip='0.0.0.0')
        if not created and attempt.updated_at and now - attempt.updated_at < cooldown:
            return True
        attempt.failures = 1
        attempt.locked_until = None
        attempt.save(update_fields=['failures', 'locked_until', 'updated_at'])
    return False


def send_account_email(user, kind, token):
    path = f'/verify/{token.token}' if kind == 'verify' else f'/reset/{token.token}'
    title = 'Verify your Venus Learning account' if kind == 'verify' else 'Reset your Venus Learning password'
    send_mail(title, f'{title}: {settings.FRONTEND_URL.rstrip("/")}{path}', settings.DEFAULT_FROM_EMAIL, [user.email])


class CsrfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        response = Response({'csrfToken': get_token(request)})
        response['Cache-Control'] = 'no-store'
        return response


@method_decorator(csrf_protect, name='dispatch')
class AuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, action):
        require_object_body(request)
        if action == 'register':
            if throttle_action(request, 'register', 10):
                return Response({'detail': 'Too many registration attempts. Try again later.'}, status=429)
            serializer = RegisterSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            try:
                with transaction.atomic():
                    user = serializer.save()
            except IntegrityError:
                raise ValidationError('Registration could not be completed for this address.')
            # Email verification is disabled: accounts are usable immediately,
            # no verification token is created and no verification email is sent.
            return Response({'detail': 'Registered. You can sign in now.'}, status=201)
        if action != 'login':
            return Response(status=405)
        email = str(request.data.get('email', '')).strip().lower()
        password = request.data.get('password', '')
        if len(email) > 254 or not isinstance(password, str) or len(password) > 128:
            return Response({'detail': 'Invalid credentials.'}, status=400)
        now = timezone.now()
        with transaction.atomic():
            # Account lockouts survive IP changes; independent source-IP limits stop password spraying.
            account = rate_attempt(email, '0.0.0.0', now)
            source = rate_attempt('login-source@rate.invalid', client_ip(request), now)
            if any(item.locked_until and item.locked_until > now for item in (account, source)):
                return Response({'detail': 'Too many attempts. Try again later.'}, status=429)
            user = authenticate(request, email=email, password=password)
            valid = bool(user and user.is_active and (user.role != 'instructor' or user.instructor_approved))
            if not valid:
                for item, threshold in ((account, 5), (source, 30)):
                    item.failures += 1
                    if item.failures >= threshold:
                        item.locked_until = now + timedelta(minutes=15)
                    item.save(update_fields=['failures', 'locked_until', 'updated_at'])
                return Response({'detail': 'Invalid credentials or account is not available.'}, status=400)
            account.failures = 0
            account.locked_until = None
            account.save(update_fields=['failures', 'locked_until', 'updated_at'])
        login(request, user)
        activity(user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [Verified]

    def post(self, request):
        logout(request)
        return Response({'detail': 'Logged out.'})


class MeView(APIView):
    permission_classes = [Verified]

    def get(self, request):
        user = request.user
        # A streak from before yesterday is no longer current, even before the next activity.
        last = DailyActivity.objects.filter(user=user).order_by('-day').values_list('day', flat=True).first()
        if last and last < timezone.localdate()-timedelta(days=1):
            user.current_streak = 0
        return Response(UserSerializer(user).data)

    def patch(self, request):
        require_object_body(request)
        forbidden = {'email', 'role', 'is_staff', 'is_superuser', 'is_verified', 'instructor_approved', 'is_active', 'points', 'current_streak', 'password'}
        if forbidden.intersection(request.data):
            raise ValidationError('Only name, title, biography, expertise, and profile image can be edited here.')
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ProfileSummaryView(APIView):
    """Role-aware data for the signed-in user's profile view.

    Learners get enrollments with progress, certificates and upcoming
    mentor sessions; instructors get their courses, student totals,
    average rating and mentor profile; admins get site counts.
    """
    permission_classes = [Verified]

    def get(self, request):
        user = request.user
        data = {'user': UserSerializer(user).data}
        now = timezone.now()
        if staff(user):
            data.update({'users': User.objects.count(), 'courses': Course.objects.count(), 'pending_courses': Course.objects.filter(status='pending').count(), 'issues': SupportTicket.objects.filter(status='open').count()})
            return Response(data)
        if approved(user):
            courses = Course.objects.filter(instructor=user)
            mentor = MentorProfile.objects.filter(user=user).first()
            data.update({
                'courses': CourseSerializer(courses, many=True).data,
                'students': Enrollment.objects.filter(course__instructor=user).values('learner').distinct().count(),
                'average_rating': Rating.objects.filter(course__instructor=user).aggregate(avg=Avg('rating'))['avg'],
                'reviews': Rating.objects.filter(course__instructor=user).count(),
                'mentor_profile': MentorProfileSerializer(mentor).data if mentor else None,
                'sessions_completed': MentorSession.objects.filter(mentor=user, status='completed').count(),
                'upcoming_sessions': MentorSessionSerializer(MentorSession.objects.filter(mentor=user, status__in=('pending', 'confirmed'), scheduled_at__gte=now).order_by('scheduled_at'), many=True).data,
            })
            return Response(data)
        data.update({
            'enrollments': EnrollmentSerializer(Enrollment.objects.filter(learner=user).select_related('course'), many=True).data,
            'certificates': CertificateSerializer(Certificate.objects.filter(learner=user).select_related('course'), many=True).data,
            'upcoming_sessions': MentorSessionSerializer(MentorSession.objects.filter(student=user, status__in=('pending', 'confirmed'), scheduled_at__gte=now).order_by('scheduled_at'), many=True).data,
        })
        return Response(data)


class InstructorProfileView(APIView):
    """Public profile for one approved instructor: who they are, what they
    teach, how learners rated them, and their mentor offer."""
    permission_classes = [Verified]

    def get(self, request, user_id):
        instructor = get_object_or_404(User, id=user_id, role='instructor', instructor_approved=True)
        courses = Course.objects.filter(instructor=instructor, status='approved')
        mentor = MentorProfile.objects.filter(user=instructor).first()
        return Response({
            'user': PublicInstructorSerializer(instructor).data,
            'courses': CourseSerializer(courses, many=True).data,
            'students': Enrollment.objects.filter(course__instructor=instructor).values('learner').distinct().count(),
            'average_rating': Rating.objects.filter(course__instructor=instructor).aggregate(avg=Avg('rating'))['avg'],
            'reviews': Rating.objects.filter(course__instructor=instructor).count(),
            'mentor_profile': MentorProfileSerializer(mentor).data if mentor else None,
            'sessions_completed': MentorSession.objects.filter(mentor=instructor, status='completed').count(),
        })


class ChangePasswordView(APIView):
    permission_classes = [Verified]

    def post(self, request):
        require_object_body(request)
        if not request.user.check_password(str(request.data.get('current_password', ''))):
            raise ValidationError({'current_password': 'Current password is incorrect.'})
        value = request.data.get('new_password', '')
        if not isinstance(value, str) or len(value) > 128:
            raise ValidationError({'new_password': 'Invalid password.'})
        try:
            validate_password(value, request.user)
        except DjangoValidationError as error:
            raise ValidationError({'new_password': error.messages})
        request.user.set_password(value)
        request.user.save(update_fields=['password'])
        logout(request)
        return Response({'detail': 'Password changed. Sign in again on your devices.'})


class VerifyView(APIView):
    # Email verification is disabled: accounts are usable immediately.
    # Kept so old verification links fail cleanly instead of 404ing.
    permission_classes = [AllowAny]

    def get(self, request, token):
        return Response({'detail': 'Email verification is disabled. You can sign in directly.'})


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()


@method_decorator(csrf_protect, name='dispatch')
class ResendVerificationView(APIView):
    # Email verification is disabled: no verification email is ever sent.
    # Kept so old links/forms fail cleanly instead of 404ing.
    permission_classes = [AllowAny]
    generic_detail = 'Email verification is disabled. You can sign in directly.'

    def post(self, request):
        return Response({'detail': self.generic_detail})


@method_decorator(csrf_protect, name='dispatch')
class PasswordResetView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, token=None):
        require_object_body(request)
        if throttle_action(request, 'password-reset', 10):
            return Response({'detail': 'Too many reset attempts. Try again later.'}, status=429)
        if token is None:
            email = str(request.data.get('email', '')).strip().lower()
            user = User.objects.filter(email=email, is_active=True).first() if len(email) <= 254 else None
            if user:
                try:
                    with transaction.atomic():
                        EmailToken.objects.filter(user=user, kind='reset', used_at__isnull=True).update(used_at=timezone.now())
                        record = EmailToken.objects.create(user=user, kind='reset', expires_at=timezone.now()+timedelta(hours=1))
                        send_account_email(user, 'reset', record)
                except Exception:
                    # Preserve generic responses; operators monitor mail delivery failures.
                    pass
            return Response({'detail': 'If the account is available, a reset link was sent.'})
        with transaction.atomic():
            record = EmailToken.objects.select_for_update().filter(token=token, kind='reset', used_at__isnull=True, expires_at__gt=timezone.now(), user__is_active=True).select_related('user').first()
            if not record:
                return Response({'detail': 'Invalid, expired, or already used reset link.'}, status=400)
            password = request.data.get('password', '')
            if not isinstance(password, str) or len(password) > 128:
                raise ValidationError({'password': 'Invalid password.'})
            try:
                validate_password(password, record.user)
            except DjangoValidationError as error:
                raise ValidationError({'password': error.messages})
            record.user.set_password(password)
            record.user.save(update_fields=['password'])
            EmailToken.objects.filter(user=record.user, kind='reset', used_at__isnull=True).update(used_at=timezone.now())
        return Response({'detail': 'Password updated. Sign in with your new password.'})


class CourseViewSet(viewsets.ModelViewSet):
    serializer_class = CourseSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'curriculum', 'reviews'):
            return [AllowAny()]
        return [EditorOnly()] if self.action in ('create', 'update', 'partial_update', 'destroy') else [Verified()]

    def get_queryset(self):
        user = self.request.user
        queryset = Course.objects.select_related('instructor').order_by('-created_at', '-id')
        if staff(user):
            pass
        elif approved(user) and (self.request.query_params.get('mine') == '1' or self.action not in ('list',)):
            queryset = queryset.filter(published_courses() | Q(instructor=user))
            if self.request.query_params.get('mine') == '1':
                queryset = queryset.filter(instructor=user)
        else:
            queryset = queryset.filter(published_courses())
        search = self.request.query_params.get('search', '').strip()[:200]
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search) | Q(instructor__full_name__icontains=search))
        category = self.request.query_params.get('category', '').strip()[:100]
        if category:
            queryset = queryset.filter(category=category)
        return queryset

    def get_serializer_class(self):
        return CourseDetailSerializer if self.action == 'retrieve' else CourseSerializer

    def perform_create(self, serializer):
        if not (approved(self.request.user) or staff(self.request.user)):
            raise PermissionDenied('Approved instructors only.')
        serializer.save(instructor=self.request.user, status='pending')
        attach_thumbnail_asset(serializer.instance, self.request.user)

    def perform_update(self, serializer):
        require_editor(self.request.user, serializer.instance)
        serializer.save(status='pending' if not staff(self.request.user) else serializer.instance.status)
        attach_thumbnail_asset(serializer.instance, self.request.user)

    def perform_destroy(self, course):
        require_editor(self.request.user, course)
        course.delete()

    @action(detail=True, methods=['get'])
    def curriculum(self, request, pk=None):
        course = self.get_object()
        return Response({'course': CourseSerializer(course, context=self.get_serializer_context()).data, 'units': CurriculumUnitSerializer(course.units.all(), many=True).data})

    @action(detail=True, methods=['get'])
    def students(self, request, pk=None):
        course = self.get_object()
        require_editor(request.user, course)
        rows = []
        for enrollment in course.enrollments.select_related('learner'):
            rows.append({**UserSerializer(enrollment.learner).data, 'enrolled_at': enrollment.enrolled_at, 'progress_percent': EnrollmentSerializer(enrollment).data['progress_percent']})
        return Response(rows)

    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        course = self.get_object()
        return Response(RatingSerializer(course.ratings.select_related('learner').order_by('-created_at'), many=True).data)

    @action(detail=True, methods=['get', 'post'])
    def enroll(self, request, pk=None):
        course = self.get_object()
        if not course_is_published(course) or request.user.role != 'learner':
            raise PermissionDenied('Learners can enroll in approved courses only.')
        if not course.enrollment_open:
            raise PermissionDenied('Enrollment for this course is closed.')
        if not course.is_free:
            raise PermissionDenied('This is a paid course. Payment is not available in this build yet, so enrollment is not open.')
        enrollment = Enrollment.objects.filter(learner=request.user, course=course).first()
        if request.method == 'GET':
            return Response(EnrollmentSerializer(enrollment).data if enrollment else {})
        enrollment, created = Enrollment.objects.get_or_create(learner=request.user, course=course)
        return Response(EnrollmentSerializer(enrollment).data, status=201 if created else 200)

    @action(detail=True, methods=['post'], url_path='submit-review')
    def submit_review(self, request, pk=None):
        """Wizard step H (PDF §4/§13): instructor submits a draft for admin review."""
        course = self.get_object()
        require_editor(request.user, course)
        require_object_body(request)
        if not course.units.exists():
            raise ValidationError('Add at least one section before submitting for review.')
        if not Lesson.objects.filter(unit__course=course).exists():
            raise ValidationError('Add at least one lesson before submitting for review.')
        review = CourseReview.objects.create(course=course, reviewer=None, decision='submitted', notes=str(request.data.get('notes', ''))[:5000])
        return Response(CourseReviewSerializer(review).data, status=201)

    @action(detail=True, methods=['get'], url_path='review-history')
    def review_history(self, request, pk=None):
        course = self.get_object()
        require_editor(request.user, course)
        return Response(CourseReviewSerializer(course.course_reviews.all(), many=True).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Admin review (PDF §13): approve and publish, with an audit record."""
        if not staff(request.user):
            raise PermissionDenied('Only an administrator can approve a course.')
        course = self.get_object()
        require_object_body(request)
        course.status = 'approved'
        course.save(update_fields=['status', 'updated_at'])
        review = CourseReview.objects.create(course=course, reviewer=request.user, decision='approved', notes=str(request.data.get('notes', ''))[:5000])
        return Response({'course': CourseSerializer(course, context=self.get_serializer_context()).data, 'review': CourseReviewSerializer(review).data})

    @action(detail=True, methods=['post'], url_path='request-changes')
    def request_changes(self, request, pk=None):
        """Admin review (PDF §13): send the course back for revision, with fixes listed."""
        if not staff(request.user):
            raise PermissionDenied('Only an administrator can request changes to a course.')
        course = self.get_object()
        require_object_body(request)
        notes = str(request.data.get('notes', '')).strip()
        if not notes:
            raise ValidationError({'notes': 'List the required fixes for the instructor.'})
        course.status = 'pending'
        course.save(update_fields=['status', 'updated_at'])
        review = CourseReview.objects.create(course=course, reviewer=request.user, decision='changes_requested', notes=notes[:5000])
        return Response({'course': CourseSerializer(course, context=self.get_serializer_context()).data, 'review': CourseReviewSerializer(review).data})

    @action(detail=True, methods=['post'])
    def certificate(self, request, pk=None):
        course = self.get_object()
        enrollment = Enrollment.objects.filter(learner=request.user, course=course).first()
        if not enrollment or request.user.role != 'learner':
            raise PermissionDenied('Enroll in this course first.')
        lesson_ids = list(Lesson.objects.filter(unit__course=course, is_required=True).values_list('id', flat=True))
        if not lesson_ids:
            lesson_ids = list(Lesson.objects.filter(unit__course=course).values_list('id', flat=True))
        completed = enrollment.progress.filter(lesson_id__in=lesson_ids, progress=100).count()
        if not lesson_ids or completed != len(lesson_ids):
            raise ValidationError('Complete every required lesson, including coding challenges, first.')
        if any(not QuizAttempt.objects.filter(learner=request.user, quiz=quiz, passed=True).exists() for quiz in course.quizzes.all()):
            raise ValidationError('Pass all course quizzes first.')
        if any(not AssignmentSubmission.objects.filter(learner=request.user, assignment=assignment, status='graded').exists() for assignment in course.assignments.filter(is_required=True)):
            raise ValidationError('Complete all required assignments first.')
        certificate, created = Certificate.objects.get_or_create(learner=request.user, course=course)
        if enrollment.completed_at is None:
            enrollment.completed_at = timezone.now()
            enrollment.save(update_fields=['completed_at'])
        return Response(CertificateSerializer(certificate).data, status=201 if created else 200)


class UnitViewSet(viewsets.ModelViewSet):
    serializer_class = UnitSerializer
    permission_classes = [Verified]

    def get_permissions(self):
        return [EditorOnly()] if self.action in ('create', 'update', 'partial_update', 'destroy') else [Verified()]

    def get_queryset(self):
        user = self.request.user
        queryset = Unit.objects.select_related('course').order_by('position', 'id')
        if staff(user):
            return queryset
        if approved(user):
            return queryset.filter(course__instructor=user)
        return queryset.filter(published_courses('course__'), course__enrollments__learner=user).distinct()

    def perform_create(self, serializer):
        course = serializer.validated_data['course']
        require_editor(self.request.user, course)
        serializer.save()
        review_after_edit(self.request.user, course)

    def perform_update(self, serializer):
        require_editor(self.request.user, serializer.instance.course)
        course = serializer.validated_data.get('course', serializer.instance.course)
        require_editor(self.request.user, course)
        serializer.save()
        review_after_edit(self.request.user, course)

    def perform_destroy(self, unit):
        course = unit.course
        require_editor(self.request.user, course)
        unit.delete()
        review_after_edit(self.request.user, course)


class LessonViewSet(viewsets.ModelViewSet):
    serializer_class = LessonSerializer
    permission_classes = [Verified]

    def get_permissions(self):
        return [EditorOnly()] if self.action in ('create', 'update', 'partial_update', 'destroy') else [Verified()]

    def get_queryset(self):
        user = self.request.user
        queryset = Lesson.objects.select_related('unit__course').order_by('unit__position', 'position', 'id')
        course = self.request.query_params.get('course')
        if course:
            if not course.isdigit():
                raise ValidationError({'course': 'Course ID must be numeric.'})
            queryset = queryset.filter(unit__course_id=course)
        if staff(user):
            return queryset
        if approved(user):
            return queryset.filter(unit__course__instructor=user)
        return queryset.filter(
            Q(published_courses('unit__course__'), unit__course__enrollments__learner=user) |
            Q(published_courses('unit__course__'), is_preview=True)
        ).distinct()

    def perform_create(self, serializer):
        course = serializer.validated_data['unit'].course
        require_editor(self.request.user, course)
        serializer.save()
        review_after_edit(self.request.user, course)

    def perform_update(self, serializer):
        require_editor(self.request.user, serializer.instance.unit.course)
        course = serializer.validated_data.get('unit', serializer.instance.unit).course
        require_editor(self.request.user, course)
        serializer.save()
        review_after_edit(self.request.user, course)

    def perform_destroy(self, lesson):
        course = lesson.unit.course
        require_editor(self.request.user, course)
        lesson.delete()
        review_after_edit(self.request.user, course)

    @action(detail=True, methods=['get'])
    def playback(self, request, pk=None):
        """Enrollment authorization flow (PDF §6): return the embed identifier
        only after the backend confirms enrollment / ownership / preview access."""
        lesson = self.get_object()
        course = lesson.unit.course
        is_owner = owns_course(request.user, course)
        enrolled = bool(request.user.is_authenticated and request.user.role == 'learner' and Enrollment.objects.filter(learner=request.user, course=course).exists())
        preview = bool(lesson.is_preview and course_is_published(course))
        if not (is_owner or enrolled or preview):
            raise PermissionDenied('Enrollment is required to play this lesson.')
        row = None
        if enrolled:
            row = LessonProgress.objects.filter(enrollment__learner=request.user, lesson=lesson).first()
        return Response({
            'lesson': lesson.id,
            'provider': lesson.provider,
            'provider_video_id': lesson.provider_video_id,
            'embed_url': youtube_embed_url(lesson.provider_video_id) if lesson.provider == 'youtube' else '',
            'video_url': lesson.video_url if (is_owner or enrolled) else '',
            'duration_seconds': lesson.duration_seconds,
            'resume_position_seconds': row.resume_position_seconds if row else 0,
            'watch_percentage': row.watch_percentage if row else 0,
            'completion_threshold': course.completion_threshold,
        })

    @action(detail=True, methods=['patch'])
    def progress(self, request, pk=None):
        require_object_body(request)
        lesson = self.get_object()
        enrollment = Enrollment.objects.filter(learner=request.user, course=lesson.unit.course).first()
        if not enrollment or request.user.role != 'learner':
            raise PermissionDenied('Enrollment is required.')
        course = lesson.unit.course
        watched = request.data.get('watched_seconds')
        duration = request.data.get('duration_seconds')
        resume = request.data.get('resume_position_seconds')
        if lesson.lesson_type == 'coding':
            raise ValidationError('Coding progress is awarded only after a successful execution.')
        with transaction.atomic():
            progress, _ = LessonProgress.objects.select_for_update().get_or_create(enrollment=enrollment, lesson=lesson)
            if watched is not None or duration is not None or resume is not None:
                # PDF §7: watched time is accumulated while playing, capped at
                # the video duration, and never double-counted by replaying.
                int_field = serializers.IntegerField(min_value=0, max_value=10000000)
                new_duration = int_field.run_validation(duration) if duration is not None else (progress.duration_seconds or lesson.duration_seconds)
                if new_duration:
                    progress.duration_seconds = new_duration
                if watched is not None:
                    new_watched = int_field.run_validation(watched)
                    if new_duration:
                        new_watched = min(new_watched, new_duration)
                    progress.watched_seconds = max(progress.watched_seconds, new_watched)
                    progress.watch_percentage = min(100, round(progress.watched_seconds * 100 / new_duration)) if new_duration else progress.watch_percentage
                if resume is not None:
                    new_resume = int_field.run_validation(resume)
                    if new_duration:
                        new_resume = min(new_resume, new_duration)
                    progress.resume_position_seconds = new_resume
                progress.progress = max(progress.progress, progress.watch_percentage)
                if progress.watch_percentage >= course.completion_threshold:
                    progress.progress = 100
                progress.completed_at = timezone.now() if progress.progress == 100 else None
                progress.save(update_fields=['progress', 'completed_at', 'watched_seconds', 'duration_seconds', 'watch_percentage', 'resume_position_seconds', 'updated_at'])
                activity(request.user)
                return Response({'progress': progress.progress, 'watch_percentage': progress.watch_percentage, 'watched_seconds': progress.watched_seconds, 'resume_position_seconds': progress.resume_position_seconds})
            field = serializers.IntegerField(min_value=0, max_value=100)
            value = field.run_validation(request.data.get('progress'))
            progress.progress = max(progress.progress, value)
            progress.completed_at = timezone.now() if progress.progress == 100 else None
            progress.save(update_fields=['progress', 'completed_at'])
        activity(request.user)
        return Response({'progress': progress.progress})

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        require_object_body(request)
        lesson = self.get_object()
        enrollment = Enrollment.objects.filter(learner=request.user, course=lesson.unit.course).first()
        if request.user.role != 'learner' or not enrollment:
            raise PermissionDenied('Enrollment is required.')
        if lesson.lesson_type != 'coding':
            raise ValidationError('This is not a coding lesson.')
        if throttle_action(request, f'lesson-run-{request.user.id}', 30):
            return Response({'detail': 'Too many code submissions. Try later.'}, status=429)
        code, language = validate_program(request.data, lesson.coding_language)
        try:
            result = execute_program(code, language, '', lesson.coding_expected_output)
        except RunnerUnavailable:
            return Response({'detail': 'The isolated code runner is unavailable or did not complete.'}, status=503)
        if result['passed']:
            LessonProgress.objects.update_or_create(enrollment=enrollment, lesson=lesson, defaults={'progress': 100, 'completed_at': timezone.now()})
            activity(request.user)
        return Response(result)


class EnrollmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EnrollmentSerializer
    permission_classes = [Verified]

    def get_queryset(self):
        return Enrollment.objects.filter(learner=self.request.user).select_related('course__instructor').order_by('-enrolled_at', '-id')


class CertificateViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CertificateSerializer
    permission_classes = [Verified]

    def get_queryset(self):
        return Certificate.objects.filter(learner=self.request.user).select_related('course__instructor', 'learner').order_by('-issued_at', '-id')


class CourseResourceViewSet(viewsets.ModelViewSet):
    """Learning resources (PDF §8). Download links are issued only after
    the backend checks enrollment / ownership — hiding a button is not access control."""
    serializer_class = CourseResourceSerializer
    permission_classes = [Verified]

    def get_permissions(self):
        return [EditorOnly()] if self.action in ('create', 'update', 'partial_update', 'destroy') else [Verified()]

    def get_queryset(self):
        user = self.request.user
        queryset = CourseResource.objects.select_related('course', 'lesson', 'asset').order_by('created_at', 'id')
        course = self.request.query_params.get('course')
        if course:
            if not course.isdigit():
                raise ValidationError({'course': 'Course ID must be numeric.'})
            queryset = queryset.filter(course_id=course)
        lesson = self.request.query_params.get('lesson')
        if lesson:
            if not lesson.isdigit():
                raise ValidationError({'lesson': 'Lesson ID must be numeric.'})
            queryset = queryset.filter(lesson_id=lesson)
        if staff(user):
            return queryset
        if approved(user):
            return queryset.filter(course__instructor=user)
        return queryset.filter(
            Q(course__instructor=user) |
            Q(course__instructor__role='admin') |
            Q(course__enrollments__learner=user, course__status='approved') |
            Q(lesson__is_preview=True, course__status='approved')
        ).distinct()

    def _course(self, resource_or_data):
        if isinstance(resource_or_data, CourseResource):
            return resource_or_data.course
        return resource_or_data.get('course')

    def perform_create(self, serializer):
        course = serializer.validated_data['course']
        require_editor(self.request.user, course)
        asset = serializer.validated_data.get('asset')
        if asset and asset.owner_id != self.request.user.id and not staff(self.request.user):
            raise PermissionDenied('That uploaded file belongs to someone else.')
        if asset and asset.course_id and asset.course_id != course.id:
            raise ValidationError({'asset': 'That uploaded file belongs to a different course.'})
        resource = serializer.save()
        if asset:
            resource.original_name = asset.original_name or resource.original_name
            resource.mime_type = asset.content_type or resource.mime_type
            try:
                resource.size_bytes = asset.file.size
            except Exception:
                pass
            resource.save(update_fields=['original_name', 'mime_type', 'size_bytes'])
        review_after_edit(self.request.user, course)

    def perform_update(self, serializer):
        require_editor(self.request.user, serializer.instance.course)
        course = serializer.validated_data.get('course', serializer.instance.course)
        require_editor(self.request.user, course)
        serializer.save()
        review_after_edit(self.request.user, course)

    def perform_destroy(self, resource):
        course = resource.course
        require_editor(self.request.user, course)
        if resource.lesson_id and course_is_published(course) and self.request.query_params.get('confirm') != '1':
            raise ValidationError('This resource is attached to a published lesson. Confirm the deletion (?confirm=1) so learners are not left with a broken lesson.')
        resource.delete()
        review_after_edit(self.request.user, course)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        resource = self.get_object()
        if not resource.downloadable and not owns_course(request.user, resource.course):
            raise PermissionDenied('This resource is view-only.')
        if resource.asset_id:
            return Response({'download_url': f'/api/uploads/{resource.asset_id}/content/'})
        if resource.external_url:
            return Response({'download_url': resource.external_url})
        raise ValidationError('This resource has no file attached.')


class AssignmentViewSet(viewsets.ModelViewSet):
    """Homework assignments (PDF §10)."""
    serializer_class = AssignmentSerializer
    permission_classes = [Verified]

    def get_permissions(self):
        return [EditorOnly()] if self.action in ('create', 'update', 'partial_update', 'destroy') else [Verified()]

    def get_queryset(self):
        user = self.request.user
        queryset = Assignment.objects.select_related('course', 'lesson').order_by('created_at', 'id')
        course = self.request.query_params.get('course')
        if course:
            if not course.isdigit():
                raise ValidationError({'course': 'Course ID must be numeric.'})
            queryset = queryset.filter(course_id=course)
        if staff(user):
            return queryset
        if approved(user):
            return queryset.filter(course__instructor=user)
        return queryset.filter(published_courses('course__'), course__enrollments__learner=user).distinct()

    def perform_create(self, serializer):
        course = serializer.validated_data['course']
        require_editor(self.request.user, course)
        serializer.save()
        review_after_edit(self.request.user, course)

    def perform_update(self, serializer):
        require_editor(self.request.user, serializer.instance.course)
        course = serializer.validated_data.get('course', serializer.instance.course)
        require_editor(self.request.user, course)
        serializer.save()
        review_after_edit(self.request.user, course)

    def perform_destroy(self, assignment):
        course = assignment.course
        require_editor(self.request.user, course)
        assignment.delete()
        review_after_edit(self.request.user, course)


class AssignmentSubmissionViewSet(viewsets.ModelViewSet):
    """Assignment submissions and grading (PDF §10). History is kept — a
    resubmission is a new attempt, it never silently overwrites the old one."""
    serializer_class = AssignmentSubmissionSerializer
    permission_classes = [Verified]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        queryset = AssignmentSubmission.objects.select_related('assignment__course', 'learner').order_by('-submitted_at', '-id')
        assignment = self.request.query_params.get('assignment')
        if assignment:
            if not assignment.isdigit():
                raise ValidationError({'assignment': 'Assignment ID must be numeric.'})
            queryset = queryset.filter(assignment_id=assignment)
        if staff(user):
            return queryset
        if approved(user):
            return queryset.filter(assignment__course__instructor=user)
        return queryset.filter(learner=user)

    def perform_create(self, serializer):
        require_object_body(self.request)
        assignment = serializer.validated_data['assignment']
        course = assignment.course
        if self.request.user.role != 'learner' or not course_is_published(course) or not Enrollment.objects.filter(learner=self.request.user, course=course).exists():
            raise PermissionDenied('Enrollment is required to submit homework.')
        asset = serializer.validated_data.get('asset')
        text = str(serializer.validated_data.get('text_response', '')).strip()
        if assignment.accepted_types == 'file' and not asset:
            raise ValidationError({'asset': 'This assignment requires a file upload.'})
        if assignment.accepted_types == 'text' and not text:
            raise ValidationError({'text_response': 'This assignment requires a text response.'})
        if assignment.accepted_types == 'both' and not asset and not text:
            raise ValidationError('Upload a file or enter a text response.')
        if asset and asset.owner_id != self.request.user.id:
            raise PermissionDenied('That uploaded file belongs to someone else.')
        attempt_no = AssignmentSubmission.objects.filter(assignment=assignment, learner=self.request.user).count() + 1
        status = 'late' if assignment.due_at and timezone.now() > assignment.due_at else 'submitted'
        serializer.save(learner=self.request.user, attempt_no=attempt_no, status=status)
        activity(self.request.user)

    @action(detail=True, methods=['post'])
    def grade(self, request, pk=None):
        submission = self.get_object()
        require_editor(request.user, submission.assignment.course)
        require_object_body(request)
        score = request.data.get('score')
        status = str(request.data.get('status', 'graded'))
        if status not in ('graded', 'needs_resubmission'):
            raise ValidationError({'status': 'Choose graded or needs_resubmission.'})
        if status == 'graded':
            if score is None:
                raise ValidationError({'score': 'A grade needs a score.'})
            field = serializers.IntegerField(min_value=0, max_value=submission.assignment.max_points)
            score = field.run_validation(score)
        submission.score = score if status == 'graded' else None
        submission.feedback = str(request.data.get('feedback', ''))[:10000]
        submission.status = status
        submission.graded_by = request.user
        submission.graded_at = timezone.now()
        submission.save(update_fields=['score', 'feedback', 'status', 'graded_by', 'graded_at'])
        return Response(AssignmentSubmissionSerializer(submission).data)


class RatingViewSet(viewsets.ModelViewSet):
    serializer_class = RatingSerializer
    permission_classes = [Verified]

    def get_queryset(self):
        user = self.request.user
        queryset = Rating.objects.all() if staff(user) else Rating.objects.filter(course__instructor=user) if approved(user) else Rating.objects.filter(learner=user)
        course = self.request.query_params.get('course')
        if course:
            if not course.isdigit():
                raise ValidationError('Invalid course ID.')
            queryset = queryset.filter(course_id=course)
        return queryset.order_by('-created_at', '-id')

    def validate_enrollment(self, course):
        if self.request.user.role != 'learner' or not course_is_published(course) or not Enrollment.objects.filter(learner=self.request.user, course=course).exists():
            raise PermissionDenied('Enroll in an approved course before reviewing it.')

    def perform_create(self, serializer):
        course = serializer.validated_data['course']
        self.validate_enrollment(course)
        if Rating.objects.filter(learner=self.request.user, course=course).exists():
            raise ValidationError('You already reviewed this course. Edit your existing rating.')
        serializer.save(learner=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.learner_id != self.request.user.id:
            raise PermissionDenied()
        self.validate_enrollment(serializer.validated_data.get('course', serializer.instance.course))
        serializer.save()

    def perform_destroy(self, rating):
        if rating.learner_id != self.request.user.id and not staff(self.request.user):
            raise PermissionDenied()
        rating.delete()


class QuizViewSet(viewsets.ModelViewSet):
    serializer_class = QuizSerializer
    permission_classes = [Verified]

    def get_permissions(self):
        return [EditorOnly()] if self.action in ('create', 'update', 'partial_update', 'destroy') else [Verified()]

    def get_queryset(self):
        user = self.request.user
        queryset = Quiz.objects.select_related('course').prefetch_related('questions').order_by('id')
        if not staff(user):
            queryset = queryset.filter(course__instructor=user) if approved(user) else queryset.filter(published_courses('course__'), course__enrollments__learner=user).distinct()
        course = self.request.query_params.get('course')
        if course:
            if not course.isdigit():
                raise ValidationError('Invalid course ID.')
            queryset = queryset.filter(course_id=course)
        return queryset

    def perform_create(self, serializer):
        course = serializer.validated_data['course']
        require_editor(self.request.user, course)
        serializer.save(owner=self.request.user)
        review_after_edit(self.request.user, course)

    def perform_update(self, serializer):
        require_editor(self.request.user, serializer.instance.course)
        course = serializer.validated_data.get('course', serializer.instance.course)
        require_editor(self.request.user, course)
        serializer.save()
        review_after_edit(self.request.user, course)

    def perform_destroy(self, quiz):
        course = quiz.course
        require_editor(self.request.user, course)
        quiz.delete()
        review_after_edit(self.request.user, course)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        quiz = self.get_object()
        if request.user.role != 'learner' or not course_is_published(quiz.course) or not Enrollment.objects.filter(learner=request.user, course=quiz.course).exists():
            raise PermissionDenied('Enrollment is required.')
        require_object_body(request)
        if quiz.attempts_allowed is not None and QuizAttempt.objects.filter(learner=request.user, quiz=quiz).count() >= quiz.attempts_allowed:
            return Response({'detail': 'No attempts remain for this quiz.'}, status=409)
        questions = list(quiz.questions.all())
        if not questions:
            raise ValidationError('This quiz has no questions.')
        answers = validated_answers(request.data.get('answers'), questions)
        score = sum(answers.get(str(question.id)) == question.correct_answer for question in questions)
        percentage = score * 100 / len(questions)
        attempt = QuizAttempt.objects.create(learner=request.user, quiz=quiz, score=score, total=len(questions), percentage=percentage, passed=percentage >= quiz.pass_percentage, answers=answers)
        activity(request.user)
        return Response(AttemptSerializer(attempt).data)


def validated_answers(value, questions):
    if not isinstance(value, dict):
        raise ValidationError({'answers': 'Answers must be an object keyed by question ID.'})
    allowed = {str(question['id'] if isinstance(question, dict) else question.id) for question in questions}
    if set(value) - allowed:
        raise ValidationError({'answers': 'Unknown question ID.'})
    if any(not isinstance(answer, str) or answer not in tuple('abcd') for answer in value.values()):
        raise ValidationError({'answers': 'Answer values must be a, b, c, or d.'})
    return value


class QuizAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AttemptSerializer
    permission_classes = [Verified]

    def get_queryset(self):
        return QuizAttempt.objects.filter(learner=self.request.user).select_related('quiz').order_by('-created_at', '-id')


class RunnerUnavailable(Exception):
    pass


LANGUAGES = {'python': 71, 'javascript': 63, 'java': 62, 'cpp': 54, 'c++': 54, 'c': 50, 'go': 60, 'rust': 73}
ALLOWED_LANGUAGE_IDS = {50, 54, 60, 62, 63, 71, 73, 74, 78}


def validate_program(data, default_language=None):
    code = data.get('code', '')
    if not isinstance(code, str) or not code.strip() or len(code) > 100000:
        raise ValidationError({'code': 'Provide nonempty source code up to 100,000 characters.'})
    raw = data.get('language_id', data.get('language', default_language))
    raw = LANGUAGES.get(str(raw).lower(), raw)
    try:
        language = int(raw)
    except (TypeError, ValueError):
        raise ValidationError({'language_id': 'Unsupported execution language.'})
    if language not in ALLOWED_LANGUAGE_IDS:
        raise ValidationError({'language_id': 'Unsupported execution language.'})
    return code, language


def normalized_output(value):
    return str(value or '').replace('\r\n', '\n').rstrip()


def execute_program(code, language, stdin, expected):
    base = settings.JUDGE0_URL or settings.CODING_RUNNER_URL
    if not base:
        raise RunnerUnavailable()
    payload = {'source_code': code, 'language_id': language, 'stdin': stdin, 'expected_output': expected, 'cpu_time_limit': 2, 'wall_time_limit': 5, 'memory_limit': 128000, 'max_file_size': 1024, 'enable_network': False}
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    if settings.JUDGE0_API_KEY:
        headers[settings.JUDGE0_AUTH_HEADER] = settings.JUDGE0_API_KEY
    request = urllib.request.Request(base.rstrip('/') + '/submissions?base64_encoded=false&wait=true', data=json.dumps(payload).encode(), headers=headers)
    try:
        response = urllib.request.urlopen(request, timeout=10)
        raw = response.read(1048577)
        if len(raw) > 1048576:
            raise RunnerUnavailable()
        result = json.loads(raw)
        state = result.get('status')
        if not isinstance(state, dict) or state.get('id') in (1, 2) or not isinstance(state.get('id'), int):
            raise RunnerUnavailable()
        stdout = result.get('stdout') or ''
        if not isinstance(stdout, str):
            raise RunnerUnavailable()
        passed = state.get('id') == 3 and normalized_output(stdout) == normalized_output(expected)
        return {'passed': passed, 'status': str(state.get('description', 'Execution completed'))[:200], 'output': stdout[:20000], 'stderr': str(result.get('stderr') or result.get('compile_output') or '')[:20000]}
    except (ValueError, TypeError, AttributeError, OSError, urllib.error.URLError):
        raise RunnerUnavailable()


class ProblemViewSet(viewsets.ModelViewSet):
    serializer_class = ProblemSerializer
    permission_classes = [Verified]

    def get_permissions(self):
        return [EditorOnly()] if self.action in ('create', 'update', 'partial_update', 'destroy') else [Verified()]

    def get_queryset(self):
        user = self.request.user
        queryset = Problem.objects.all().order_by('id')
        return queryset.filter(owner=user) if approved(user) else queryset

    def perform_create(self, serializer):
        if not (staff(self.request.user) or approved(self.request.user)):
            raise PermissionDenied()
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        if not staff(self.request.user) and not (approved(self.request.user) and serializer.instance.owner_id == self.request.user.id):
            raise PermissionDenied()
        serializer.save()

    def perform_destroy(self, problem):
        if not staff(self.request.user) and not (approved(self.request.user) and problem.owner_id == self.request.user.id):
            raise PermissionDenied()
        problem.delete()

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        problem = self.get_object()
        if request.user.role != 'learner':
            raise PermissionDenied('Learner submissions only.')
        require_object_body(request)
        if not settings.JUDGE0_URL and not settings.CODING_RUNNER_URL:
            return Response({'detail': 'The isolated code runner is not configured.'}, status=503)
        if throttle_action(request, f'problem-run-{request.user.id}', 30):
            return Response({'detail': 'Too many code submissions. Try later.'}, status=429)
        code, language = validate_program(request.data)
        if not problem.test_cases:
            raise ValidationError('This problem has no grading test cases. Contact the instructor.')
        submission = Submission.objects.create(problem=problem, learner=request.user, code=code, language=str(language))
        passed_count, started = 0, time.monotonic()
        try:
            for test in problem.test_cases:
                if time.monotonic() - started > 25:
                    raise RunnerUnavailable()
                result = execute_program(code, language, test.get('input', ''), test.get('output', test.get('expected_output', '')))
                if not result['passed']:
                    break
                passed_count += 1
        except (RunnerUnavailable, KeyError, TypeError):
            submission.status = 'runner_error'
            submission.result = 'The execution service did not complete grading.'
            submission.save(update_fields=['status', 'result'])
            return Response({'detail': submission.result, 'id': submission.id}, status=503)
        accepted = passed_count == len(problem.test_cases)
        submission.status = 'accepted' if accepted else 'failed'
        submission.result = json.dumps({'passed_tests': passed_count, 'total_tests': len(problem.test_cases)})
        submission.save(update_fields=['status', 'result'])
        if accepted:
            with transaction.atomic():
                user = User.objects.select_for_update().get(pk=request.user.pk)
                _, first_completion = ProblemCompletion.objects.get_or_create(learner=user, problem=problem)
                if first_completion:
                    User.objects.filter(pk=user.pk).update(points=F('points') + 10)
            activity(request.user)
        return Response(SubmissionSerializer(submission).data)


class SubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SubmissionSerializer
    permission_classes = [Verified]

    def get_queryset(self):
        return Submission.objects.filter(learner=self.request.user).select_related('problem').order_by('-created_at', '-id')


class ContestViewSet(viewsets.ModelViewSet):
    serializer_class = ContestSerializer
    permission_classes = [Verified]

    def get_permissions(self):
        return [StaffOnly()] if self.action in ('create', 'update', 'partial_update', 'destroy') else [Verified()]

    def get_queryset(self):
        # Ended contests must remain addressable for history and rankings.
        return Contest.objects.all().order_by('-starts_at', '-id')

    def perform_create(self, serializer):
        if not staff(self.request.user):
            raise PermissionDenied('Administrators manage contests.')
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        if not staff(self.request.user):
            raise PermissionDenied()
        if ContestAttempt.objects.filter(contest=serializer.instance).exists():
            raise ValidationError('A contest with submissions cannot be changed. Create a new contest instead.')
        serializer.save()

    def perform_destroy(self, contest):
        if not staff(self.request.user):
            raise PermissionDenied()
        contest.delete()

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        contest = self.get_object()
        if request.user.role != 'learner':
            raise PermissionDenied('Learner participation only.')
        require_object_body(request)
        now = timezone.now()
        if not contest.starts_at <= now < contest.ends_at:
            raise ValidationError('The contest is not active.')
        if not contest.questions:
            raise ValidationError('The contest has no questions.')
        answers = validated_answers(request.data.get('answers'), contest.questions)
        score = sum(answers.get(str(question['id'])) == question['correct_answer'] for question in contest.questions)
        try:
            with transaction.atomic():
                User.objects.select_for_update().get(pk=request.user.pk)
                attempt = ContestAttempt.objects.create(contest=contest, learner=request.user, score=score, total=len(contest.questions), percentage=score*100/len(contest.questions), answers=answers)
                User.objects.filter(pk=request.user.pk).update(points=F('points') + score)
        except IntegrityError:
            return Response({'detail': 'This contest has already been submitted.'}, status=409)
        activity(request.user)
        return Response(ContestAttemptSerializer(attempt).data)

    @action(detail=True, methods=['get'])
    def leaderboard(self, request, pk=None):
        contest = self.get_object()
        rows = ContestAttempt.objects.filter(contest=contest, learner__is_active=True).select_related('learner').order_by('-score', 'created_at', 'id')
        prizes = {prize['position']: prize['prize_label'] for prize in contest.prizes}
        return Response([{'rank': rank, 'learner': attempt.learner.full_name, 'score': attempt.score, 'percentage': attempt.percentage, 'prize_label': prizes.get(rank, '') if timezone.now() >= contest.ends_at else ''} for rank, attempt in enumerate(rows, 1)])


class ContestAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ContestAttemptSerializer
    permission_classes = [Verified]

    def get_queryset(self):
        return ContestAttempt.objects.filter(learner=self.request.user).select_related('contest').order_by('-created_at', '-id')


class IssueViewSet(viewsets.ModelViewSet):
    permission_classes = [Verified]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_serializer_class(self):
        return StaffTicketSerializer if staff(self.request.user) and self.action in ('update', 'partial_update') else TicketSerializer

    def get_queryset(self):
        queryset = SupportTicket.objects.all() if staff(self.request.user) else SupportTicket.objects.filter(user=self.request.user)
        return queryset.select_related('user').order_by('-created_at', '-id')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if not staff(self.request.user):
            raise PermissionDenied('Only administrators can respond to a report.')
        serializer.save()


class StaffUserViewSet(viewsets.ModelViewSet):
    serializer_class = StaffUserSerializer
    permission_classes = [StaffOnly]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        return User.objects.all().order_by('-created_at', '-id') if staff(self.request.user) else User.objects.none()

    def perform_update(self, serializer):
        if not staff(self.request.user):
            raise PermissionDenied()
        forbidden = {'role', 'is_staff', 'is_superuser', 'password', 'is_verified', 'email', 'points'}
        if forbidden.intersection(self.request.data):
            raise ValidationError('This endpoint cannot change credentials or privileges.')
        if serializer.instance.pk == self.request.user.pk and serializer.validated_data.get('is_active') is False:
            raise ValidationError('You cannot block your own administrative account.')
        serializer.save()


class StaffCourseViewSet(CourseViewSet):
    def get_permissions(self):
        return [StaffOnly()]

    def get_queryset(self):
        return Course.objects.select_related('instructor').order_by('-created_at', '-id') if staff(self.request.user) else Course.objects.none()

    def get_serializer_class(self):
        return CourseDetailSerializer if self.action == 'retrieve' else StaffCourseSerializer

    def perform_update(self, serializer):
        if not staff(self.request.user):
            raise PermissionDenied()
        old_status = serializer.instance.status
        serializer.save()
        new_status = serializer.instance.status
        if new_status != old_status:
            decision = {'approved': 'approved', 'rejected': 'rejected'}.get(new_status)
            if decision:
                notes = ''
                if isinstance(self.request.data, Mapping):
                    notes = str(self.request.data.get('review_notes', ''))[:5000]
                CourseReview.objects.create(course=serializer.instance, reviewer=self.request.user, decision=decision, notes=notes)


class StaffIssueViewSet(IssueViewSet):
    permission_classes = [StaffOnly]

    def get_queryset(self):
        return SupportTicket.objects.select_related('user').order_by('-created_at', '-id') if staff(self.request.user) else SupportTicket.objects.none()


class DashboardView(APIView):
    permission_classes = [Verified]

    def get(self, request):
        user = request.user
        if staff(user):
            return Response({'users': User.objects.count(), 'courses': Course.objects.count(), 'pending_courses': Course.objects.filter(status='pending').count(), 'issues': SupportTicket.objects.filter(status='open').count()})
        if approved(user):
            return Response({'courses': Course.objects.filter(instructor=user).count(), 'students': Enrollment.objects.filter(course__instructor=user).values('learner').distinct().count(), 'lessons': Lesson.objects.filter(unit__course__instructor=user).count(), 'reviews': Rating.objects.filter(course__instructor=user).count()})
        return Response({'enrollments': Enrollment.objects.filter(learner=user).count(), 'certificates': Certificate.objects.filter(learner=user).count(), 'points': user.points, 'streak': user.current_streak})


class StaffDashboardView(DashboardView):
    permission_classes = [StaffOnly]

    def get(self, request):
        return Response({'users': User.objects.count(), 'courses': Course.objects.count(), 'pending_courses': Course.objects.filter(status='pending').count(), 'issues': SupportTicket.objects.filter(status='open').count()})


class LeaderboardView(APIView):
    permission_classes = [Verified]

    def get(self, request):
        return Response([{'id': user.id, 'full_name': user.full_name, 'points': user.points, 'streak': user.current_streak} for user in User.objects.filter(is_active=True, role='learner').order_by('-points', '-current_streak', 'id')[:100]])


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
        except Exception:
            return Response({'status': 'unavailable'}, status=503)
        return Response({'status': 'ok', 'database': 'ok'})
