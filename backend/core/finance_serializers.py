import re
from decimal import Decimal

from rest_framework import serializers

from .finance_models import PAYMENT_METHODS, TopUpRequest, WithdrawalRequest

MOBILE_WALLET_NUMBER = re.compile(r'^01[3-9]\d{8}$')


def clean_account_number(value):
    digits = re.sub(r'[\s-]', '', value or '')
    if not MOBILE_WALLET_NUMBER.match(digits):
        raise serializers.ValidationError('Enter the 11-digit mobile wallet number, for example 01712345678.')
    return digits


class TopUpRequestSerializer(serializers.ModelSerializer):
    method_label = serializers.CharField(source='get_method_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    method = serializers.ChoiceField(choices=PAYMENT_METHODS)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('1.00'))

    class Meta:
        model = TopUpRequest
        fields = ('id', 'method', 'method_label', 'account_number', 'transaction_id', 'amount', 'status', 'status_label', 'review_note', 'created_at')
        read_only_fields = ('id', 'status', 'status_label', 'review_note', 'created_at')

    def validate_account_number(self, value):
        return clean_account_number(value)

    def validate_transaction_id(self, value):
        cleaned = (value or '').strip()
        if len(cleaned) < 4:
            raise serializers.ValidationError('Enter the transaction ID from your mobile wallet receipt.')
        return cleaned

    def validate(self, attrs):
        if TopUpRequest.objects.filter(method=attrs['method'], transaction_id=attrs['transaction_id']).exists():
            raise serializers.ValidationError({'transaction_id': 'This transaction ID has already been submitted for this payment service.'})
        return attrs


class WithdrawalRequestSerializer(serializers.ModelSerializer):
    method_label = serializers.CharField(source='get_method_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    method = serializers.ChoiceField(choices=PAYMENT_METHODS)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('1.00'))

    class Meta:
        model = WithdrawalRequest
        fields = ('id', 'method', 'method_label', 'account_number', 'amount', 'status', 'status_label', 'review_note', 'created_at')
        read_only_fields = ('id', 'status', 'status_label', 'review_note', 'created_at')

    def validate_account_number(self, value):
        return clean_account_number(value)
