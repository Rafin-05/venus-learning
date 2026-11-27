from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from . import finance_services
from .finance_models import PAYMENT_METHODS, TopUpRequest, WithdrawalRequest
from .finance_serializers import TopUpRequestSerializer, WithdrawalRequestSerializer
from .mentor_models import WalletTransaction
from .mentor_serializers import WalletTransactionSerializer
from .mentor_views import get_or_create_wallet, staff
from .permissions import Verified


def money(value):
    return str(value or 0)


class FinanceViewSet(viewsets.ViewSet):
    permission_classes = [Verified]

    def _staff_only(self, request):
        if not staff(request.user):
            raise PermissionDenied('Only administrators can review finance requests.')

    def list(self, request):
        wallet = get_or_create_wallet(request.user)
        is_instructor = request.user.role == 'instructor'
        top_ups = TopUpRequest.objects.filter(user=request.user)
        withdrawals = WithdrawalRequest.objects.filter(user=request.user)
        return Response({
            'balance': money(wallet.balance),
            'role': request.user.role,
            'can_withdraw': is_instructor,
            'payment_methods': [{'value': value, 'label': label} for value, label in PAYMENT_METHODS],
            'pending_top_ups': top_ups.filter(status='pending').count(),
            'approved_top_ups': top_ups.filter(status='approved').aggregate(total=Sum('amount'))['total'] or '0.00',
            'pending_withdrawals': withdrawals.filter(status='pending').count(),
            'paid_withdrawals': withdrawals.filter(status='paid').aggregate(total=Sum('amount'))['total'] or '0.00',
        })

    @action(detail=False, methods=['get', 'post'], url_path='top-ups')
    def top_ups(self, request):
        if request.method == 'POST':
            serializer = TopUpRequestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            top_up = serializer.save(user=request.user)
            return Response(TopUpRequestSerializer(top_up).data, status=201)
        queryset = TopUpRequest.objects.all() if staff(request.user) else TopUpRequest.objects.filter(user=request.user)
        return Response(TopUpRequestSerializer(queryset[:50], many=True).data)

    @action(detail=False, methods=['get', 'post'], url_path='withdrawals')
    def withdrawals(self, request):
        if request.method == 'POST':
            if request.user.role != 'instructor':
                raise PermissionDenied('Only instructors can request a withdrawal.')
            serializer = WithdrawalRequestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            wallet = get_or_create_wallet(request.user)
            if serializer.validated_data['amount'] > wallet.balance:
                raise ValidationError('The withdrawal amount is higher than your available balance.')
            withdrawal = serializer.save(user=request.user)
            return Response(WithdrawalRequestSerializer(withdrawal).data, status=201)
        if request.user.role != 'instructor':
            return Response([])
        return Response(WithdrawalRequestSerializer(WithdrawalRequest.objects.filter(user=request.user)[:50], many=True).data)

    @action(detail=False, methods=['get'], url_path='transactions')
    def transactions(self, request):
        wallet = get_or_create_wallet(request.user)
        return Response(WalletTransactionSerializer(WalletTransaction.objects.filter(wallet=wallet)[:50], many=True).data)

    @action(detail=False, methods=['post'], url_path=r'top-ups/(?P<top_up_id>\d+)/approve')
    def approve_top_up(self, request, top_up_id=None):
        self._staff_only(request)
        top_up = get_object_or_404(TopUpRequest, pk=top_up_id)
        top_up = finance_services.approve_top_up(top_up.pk, request.user, request.data.get('note', ''))
        return Response(TopUpRequestSerializer(top_up).data)

    @action(detail=False, methods=['post'], url_path=r'top-ups/(?P<top_up_id>\d+)/reject')
    def reject_top_up(self, request, top_up_id=None):
        self._staff_only(request)
        top_up = get_object_or_404(TopUpRequest, pk=top_up_id)
        top_up = finance_services.reject_top_up(top_up.pk, request.user, request.data.get('note', ''))
        return Response(TopUpRequestSerializer(top_up).data)

    @action(detail=False, methods=['post'], url_path=r'withdrawals/(?P<withdrawal_id>\d+)/approve')
    def approve_withdrawal(self, request, withdrawal_id=None):
        self._staff_only(request)
        withdrawal = get_object_or_404(WithdrawalRequest, pk=withdrawal_id)
        withdrawal = finance_services.approve_withdrawal(withdrawal.pk, request.user, request.data.get('note', ''))
        return Response(WithdrawalRequestSerializer(withdrawal).data)

    @action(detail=False, methods=['post'], url_path=r'withdrawals/(?P<withdrawal_id>\d+)/reject')
    def reject_withdrawal(self, request, withdrawal_id=None):
        self._staff_only(request)
        withdrawal = get_object_or_404(WithdrawalRequest, pk=withdrawal_id)
        withdrawal = finance_services.reject_withdrawal(withdrawal.pk, request.user, request.data.get('note', ''))
        return Response(WithdrawalRequestSerializer(withdrawal).data)
