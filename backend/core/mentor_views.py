from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .mentor_models import MentorOffer, MentorProfile, MentorSession, SessionRating, SessionRequest, Wallet, WalletTransaction
from .mentor_serializers import MentorOfferSerializer, MentorProfileSerializer, MentorSessionSerializer, SessionRatingSerializer, SessionRequestSerializer, WalletTransactionSerializer
from .permissions import Verified

PLATFORM_DEDUCTION_RATE = Decimal('0.10')
CENT = Decimal('0.01')


def staff(user):
    return bool(user and (user.is_staff or user.role == 'admin'))


def is_mentor(user):
    return bool(user and (user.role == 'instructor' or staff(user)))


def get_or_create_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


def locked_wallet(user):
    wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)
    return wallet


def split_fee(fee):
    deduction = (fee * PLATFORM_DEDUCTION_RATE).quantize(CENT)
    return deduction, fee - deduction


class MentorProfileViewSet(viewsets.ModelViewSet):
    serializer_class = MentorProfileSerializer
    permission_classes = [Verified]

    def get_queryset(self):
        return MentorProfile.objects.select_related('user').all()

    def perform_create(self, serializer):
        if not is_mentor(self.request.user):
            raise PermissionDenied('Only instructors can create a mentor profile.')
        if MentorProfile.objects.filter(user=self.request.user).exists():
            raise ValidationError('You already have a mentor profile. Edit your existing profile.')
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.user_id != self.request.user.id and not staff(self.request.user):
            raise PermissionDenied()
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user_id != self.request.user.id and not staff(self.request.user):
            raise PermissionDenied()
        instance.delete()


class SessionRequestViewSet(viewsets.ModelViewSet):
    serializer_class = SessionRequestSerializer
    permission_classes = [Verified]

    def get_queryset(self):
        user = self.request.user
        queryset = SessionRequest.objects.select_related('student').prefetch_related('offers')
        if staff(user):
            return queryset.all()
        if user.role == 'instructor':
            return queryset.filter(Q(status='open') | Q(offers__mentor=user)).distinct()
        return queryset.filter(student=user)

    def perform_create(self, serializer):
        if self.request.user.role != 'learner':
            raise PermissionDenied('Only learners can post a session request.')
        serializer.save(student=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.student_id != self.request.user.id and not staff(self.request.user):
            raise PermissionDenied()
        if serializer.instance.status != 'open':
            raise ValidationError('Only an open request can be edited.')
        serializer.save()

    def perform_destroy(self, instance):
        if instance.student_id != self.request.user.id and not staff(self.request.user):
            raise PermissionDenied()
        instance.delete()


class MentorOfferViewSet(viewsets.ModelViewSet):
    serializer_class = MentorOfferSerializer
    permission_classes = [Verified]

    def get_queryset(self):
        user = self.request.user
        queryset = MentorOffer.objects.select_related('mentor', 'session_request')
        if staff(user):
            return queryset.all()
        if user.role == 'instructor':
            return queryset.filter(Q(mentor=user) | Q(session_request__status='open'))
        return queryset.filter(session_request__student=user)

    def perform_create(self, serializer):
        user = self.request.user
        if not is_mentor(user):
            raise PermissionDenied('Only instructors can offer to teach a session request.')
        session_request = serializer.validated_data['session_request']
        if session_request.status != 'open':
            raise ValidationError('This session request is no longer open.')
        if MentorOffer.objects.filter(session_request=session_request, mentor=user).exists():
            raise ValidationError('You already made an offer on this request.')
        profile = MentorProfile.objects.filter(user=user).first()
        pricing_type = serializer.validated_data.get('pricing_type') or 'hourly'
        agreed_amount = serializer.validated_data.get('agreed_amount')
        if pricing_type == 'fixed' and (agreed_amount is None or agreed_amount <= 0):
            raise ValidationError('A fixed-price offer needs an agreed amount above zero.')
        hourly_rate = serializer.validated_data.get('hourly_rate')
        if hourly_rate is None:
            if profile is None:
                raise ValidationError('Create a mentor profile with an hourly rate before making an offer.')
            hourly_rate = profile.hourly_rate
        serializer.save(mentor=user, mentor_profile=profile, hourly_rate=hourly_rate)

    def perform_update(self, serializer):
        if serializer.instance.mentor_id != self.request.user.id and not staff(self.request.user):
            raise PermissionDenied()
        serializer.save()

    def perform_destroy(self, instance):
        if instance.mentor_id != self.request.user.id and not staff(self.request.user):
            raise PermissionDenied()
        instance.delete()

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        offer = self.get_object()
        session_request = offer.session_request
        if session_request.student_id != request.user.id:
            raise PermissionDenied('Only the learner who posted this request can accept an offer.')
        if offer.status != 'pending' or session_request.status != 'open':
            raise ValidationError('This offer can no longer be accepted.')
        with transaction.atomic():
            duration = session_request.preferred_duration_hours
            if offer.pricing_type == 'fixed':
                total_fee = offer.agreed_amount
            else:
                total_fee = offer.hourly_rate * duration
            session = MentorSession.objects.create(
                student=request.user, mentor=offer.mentor, mentor_profile=offer.mentor_profile,
                source='request', session_request=session_request, offer=offer,
                topic=session_request.topic, duration_hours=duration,
                hourly_rate=offer.hourly_rate, pricing_type=offer.pricing_type,
                agreed_amount=offer.agreed_amount, total_fee=total_fee,
                scheduled_at=offer.proposed_time, status='confirmed')
            offer.status = 'accepted'
            offer.save(update_fields=['status'])
            MentorOffer.objects.filter(session_request=session_request, status='pending').update(status='declined')
            session_request.status = 'booked'
            session_request.save(update_fields=['status', 'updated_at'])
        return Response(MentorSessionSerializer(session).data, status=201)


class MentorSessionViewSet(viewsets.ModelViewSet):
    serializer_class = MentorSessionSerializer
    permission_classes = [Verified]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        queryset = MentorSession.objects.select_related('student', 'mentor', 'mentor_profile')
        if staff(user):
            return queryset.all()
        return queryset.filter(Q(student=user) | Q(mentor=user))

    def perform_create(self, serializer):
        user = self.request.user
        if user.role != 'learner':
            raise PermissionDenied('Only learners can book a mentor from the Browse Mentors list.')
        mentor = serializer.validated_data['mentor']
        if mentor.id == user.id:
            raise ValidationError('You cannot book a session with yourself.')
        profile = MentorProfile.objects.filter(user=mentor, is_available=True).first()
        if profile is None:
            raise ValidationError('This mentor does not have an available mentor profile.')
        duration = serializer.validated_data['duration_hours']
        serializer.save(student=user, mentor_profile=profile, source='browse', status='pending',
                        hourly_rate=profile.hourly_rate, total_fee=profile.hourly_rate * duration)

    def perform_update(self, serializer):
        instance = serializer.instance
        if staff(self.request.user):
            serializer.save()
            return
        if instance.mentor_id == self.request.user.id and set(self.request.data) <= {'meet_link'}:
            serializer.save()
            return
        raise PermissionDenied('Only the mentor can set the meeting link.')

    def _participant(self, request, session, mentor_too=True):
        if staff(request.user) or session.student_id == request.user.id or (mentor_too and session.mentor_id == request.user.id):
            return
        raise PermissionDenied()

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        session = self.get_object()
        if session.mentor_id != request.user.id and not staff(request.user):
            raise PermissionDenied('Only the mentor can confirm this booking.')
        if session.status != 'pending':
            raise ValidationError('Only a pending booking can be confirmed.')
        session.status = 'confirmed'
        session.save(update_fields=['status', 'updated_at'])
        return Response(MentorSessionSerializer(session).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        session = self.get_object()
        self._participant(request, session)
        if session.status not in ('pending', 'confirmed'):
            raise ValidationError('This session can no longer be cancelled.')
        if session.scheduled_at <= timezone.now():
            raise ValidationError('This session has already started and cannot be cancelled.')
        session.status = 'cancelled'
        session.save(update_fields=['status', 'updated_at'])
        return Response(MentorSessionSerializer(session).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        session = self.get_object()
        self._participant(request, session)
        if session.status != 'confirmed':
            raise ValidationError('Only a confirmed session can be marked completed.')
        session.status = 'completed'
        session.save(update_fields=['status', 'updated_at'])
        return Response(MentorSessionSerializer(session).data)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        session = self.get_object()
        if session.mentor_id != request.user.id and not staff(request.user):
            raise PermissionDenied('Only the mentor can start this session.')
        if session.status != 'confirmed':
            raise ValidationError('Only a confirmed session can be started.')
        if not session.meet_link:
            raise ValidationError('Add a Google Meet link before starting the session.')
        session.status = 'live'
        session.started_at = timezone.now()
        session.save(update_fields=['status', 'started_at', 'updated_at'])
        return Response(MentorSessionSerializer(session).data)

    @action(detail=True, methods=['post'])
    def end(self, request, pk=None):
        session = self.get_object()
        if session.mentor_id != request.user.id and not staff(request.user):
            raise PermissionDenied('Only the mentor can end this session.')
        if session.status != 'live':
            raise ValidationError('Only a live session can be ended.')
        ended_at = timezone.now()
        session.status = 'completed'
        session.ended_at = ended_at
        session.save(update_fields=['status', 'ended_at', 'updated_at'])
        elapsed_minutes = max(0, int((ended_at - session.started_at).total_seconds() // 60)) if session.started_at else 0
        deduction, credited = split_fee(session.total_fee)
        return Response({
            'session': MentorSessionSerializer(session).data,
            'elapsed_minutes': elapsed_minutes,
            'total_fee': str(session.total_fee),
            'platform_deduction': str(deduction),
            'credited_to_mentor': str(credited),
        })

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        session = self.get_object()
        if session.student_id != request.user.id:
            raise PermissionDenied('Only the learner who booked this session can pay for it.')
        if session.status != 'completed':
            raise ValidationError('The session must be completed before it can be paid.')
        if session.payment_status != 'unpaid':
            raise ValidationError('This session has already been paid.')
        fee = session.total_fee
        deduction, credited = split_fee(fee)
        with transaction.atomic():
            student_wallet = locked_wallet(session.student)
            if student_wallet.balance < fee:
                raise ValidationError('Insufficient balance. Top up your Finance account before paying.')
            mentor_wallet = locked_wallet(session.mentor)
            student_wallet.balance -= fee
            student_wallet.save(update_fields=['balance', 'updated_at'])
            mentor_wallet.balance += credited
            mentor_wallet.save(update_fields=['balance', 'updated_at'])
            breakdown = {'fee_amount': fee, 'deduction_amount': deduction, 'credited_amount': credited, 'session': session}
            WalletTransaction.objects.create(wallet=student_wallet, user=session.student, kind='session_payment', status='paid', amount=-fee, note=f'Session payment for "{session.topic}".', **breakdown)
            WalletTransaction.objects.create(wallet=mentor_wallet, user=session.mentor, kind='mentor_credit', status='credited', amount=credited, note=f'Session earning for "{session.topic}" after the 10% platform deduction.', **breakdown)
            WalletTransaction.objects.create(wallet=None, user=None, kind='platform_deduction', status='deduction', amount=deduction, note=f'Platform deduction (10%) for "{session.topic}".', **breakdown)
            session.payment_status = 'paid'
            session.paid_at = timezone.now()
            session.save(update_fields=['payment_status', 'paid_at', 'updated_at'])
        return Response({'session': MentorSessionSerializer(session).data, 'fee': str(fee), 'platform_deduction': str(deduction), 'credited_to_mentor': str(credited)})

    @action(detail=True, methods=['post'])
    def refund(self, request, pk=None):
        session = self.get_object()
        if session.student_id != request.user.id and not staff(request.user):
            raise PermissionDenied('Only the learner who paid, or an administrator, can refund this payment.')
        if session.payment_status != 'paid':
            raise ValidationError('Only a paid session can be refunded.')
        fee = session.total_fee
        deduction, credited = split_fee(fee)
        with transaction.atomic():
            student_wallet = locked_wallet(session.student)
            mentor_wallet = locked_wallet(session.mentor)
            student_wallet.balance += fee
            student_wallet.save(update_fields=['balance', 'updated_at'])
            mentor_wallet.balance -= credited
            mentor_wallet.save(update_fields=['balance', 'updated_at'])
            breakdown = {'fee_amount': fee, 'deduction_amount': deduction, 'credited_amount': credited, 'session': session}
            WalletTransaction.objects.filter(session=session, kind__in=('session_payment', 'mentor_credit', 'platform_deduction')).exclude(status='refunded').update(status='refunded')
            WalletTransaction.objects.create(wallet=student_wallet, user=session.student, kind='refund', status='refunded', amount=fee, note=f'Refund for "{session.topic}" — payment returned to the learner balance.', **breakdown)
            WalletTransaction.objects.create(wallet=mentor_wallet, user=session.mentor, kind='refund', status='refunded', amount=-credited, note=f'Refund reversal for "{session.topic}" — credited amount removed.', **breakdown)
            session.payment_status = 'refunded'
            session.save(update_fields=['payment_status', 'updated_at'])
        return Response(MentorSessionSerializer(session).data)


class SessionRatingViewSet(viewsets.ModelViewSet):
    serializer_class = SessionRatingSerializer
    permission_classes = [Verified]

    def get_queryset(self):
        user = self.request.user
        queryset = SessionRating.objects.select_related('student', 'mentor', 'session')
        if staff(user):
            return queryset.all()
        return queryset.filter(Q(student=user) | Q(mentor=user))

    def perform_create(self, serializer):
        session = serializer.validated_data['session']
        if session.student_id != self.request.user.id:
            raise PermissionDenied('Only the learner who took this session can rate it.')
        if session.status != 'completed':
            raise ValidationError('You can rate a session only after it is completed.')
        if SessionRating.objects.filter(session=session).exists():
            raise ValidationError('This session has already been rated.')
        serializer.save(student=self.request.user, mentor=session.mentor)

    def perform_update(self, serializer):
        if serializer.instance.student_id != self.request.user.id and not staff(self.request.user):
            raise PermissionDenied()
        serializer.save()
