from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .finance_models import TopUpRequest, WithdrawalRequest
from .mentor_models import WalletTransaction
from .mentor_views import locked_wallet


def _reviewer_fields(reviewer, note):
    return {'reviewed_by': reviewer, 'reviewed_at': timezone.now(), 'review_note': note or ''}


def approve_top_up(top_up_id, reviewer=None, note=''):
    with transaction.atomic():
        top_up = TopUpRequest.objects.select_for_update().get(pk=top_up_id)
        if top_up.status != 'pending':
            raise ValidationError('This top-up request has already been reviewed.')
        wallet = locked_wallet(top_up.user)
        wallet.balance += top_up.amount
        wallet.save(update_fields=['balance', 'updated_at'])
        WalletTransaction.objects.create(
            wallet=wallet, user=top_up.user, kind='top_up', status='completed', amount=top_up.amount,
            note=f'{top_up.get_method_display()} top-up {top_up.transaction_id} verified.',
        )
        top_up.status = 'approved'
        for field, value in _reviewer_fields(reviewer, note).items():
            setattr(top_up, field, value)
        top_up.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_note'])
    return top_up


def reject_top_up(top_up_id, reviewer=None, note=''):
    with transaction.atomic():
        top_up = TopUpRequest.objects.select_for_update().get(pk=top_up_id)
        if top_up.status != 'pending':
            raise ValidationError('This top-up request has already been reviewed.')
        top_up.status = 'rejected'
        for field, value in _reviewer_fields(reviewer, note).items():
            setattr(top_up, field, value)
        top_up.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_note'])
    return top_up


def approve_withdrawal(withdrawal_id, reviewer=None, note=''):
    with transaction.atomic():
        withdrawal = WithdrawalRequest.objects.select_for_update().get(pk=withdrawal_id)
        if withdrawal.status != 'pending':
            raise ValidationError('This withdrawal request has already been reviewed.')
        wallet = locked_wallet(withdrawal.user)
        if wallet.balance < withdrawal.amount:
            raise ValidationError('The available balance is lower than this withdrawal request.')
        wallet.balance -= withdrawal.amount
        wallet.save(update_fields=['balance', 'updated_at'])
        WalletTransaction.objects.create(
            wallet=wallet, user=withdrawal.user, kind='withdrawal', status='paid', amount=-withdrawal.amount,
            note=f'{withdrawal.get_method_display()} payout to {withdrawal.account_number}.',
        )
        withdrawal.status = 'paid'
        for field, value in _reviewer_fields(reviewer, note).items():
            setattr(withdrawal, field, value)
        withdrawal.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_note'])
    return withdrawal


def reject_withdrawal(withdrawal_id, reviewer=None, note=''):
    with transaction.atomic():
        withdrawal = WithdrawalRequest.objects.select_for_update().get(pk=withdrawal_id)
        if withdrawal.status != 'pending':
            raise ValidationError('This withdrawal request has already been reviewed.')
        withdrawal.status = 'rejected'
        for field, value in _reviewer_fields(reviewer, note).items():
            setattr(withdrawal, field, value)
        withdrawal.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_note'])
    return withdrawal
