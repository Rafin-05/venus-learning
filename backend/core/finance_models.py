from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

PAYMENT_METHODS = (('bkash', 'bKash'), ('nagad', 'Nagad'), ('rocket', 'Rocket'))


class TopUpRequest(models.Model):
    STATUS_CHOICES = (('pending', 'Pending verification'), ('approved', 'Approved'), ('rejected', 'Rejected'))
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='top_up_requests')
    method = models.CharField(max_length=10, choices=PAYMENT_METHODS)
    account_number = models.CharField(max_length=20)
    transaction_id = models.CharField(max_length=64)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('1.00'))])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    review_note = models.CharField(max_length=255, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_top_ups')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-id')
        constraints = [models.UniqueConstraint(fields=['method', 'transaction_id'], name='unique_top_up_transaction')]

    def __str__(self):
        return f'{self.get_method_display()} top-up {self.transaction_id} for {self.user}'


class WithdrawalRequest(models.Model):
    STATUS_CHOICES = (('pending', 'Pending payout'), ('paid', 'Paid'), ('rejected', 'Rejected'))
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='withdrawal_requests')
    method = models.CharField(max_length=10, choices=PAYMENT_METHODS)
    account_number = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('1.00'))])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    review_note = models.CharField(max_length=255, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_withdrawals')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-id')

    def __str__(self):
        return f'{self.get_method_display()} payout {self.amount} for {self.user}'
