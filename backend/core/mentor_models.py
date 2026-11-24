from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class MentorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mentor_profile')
    qualifications = models.TextField(blank=True)
    topics = models.CharField(max_length=500, blank=True)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('user__full_name', 'id')

    def __str__(self):
        return f'Mentor profile for {self.user}'


class Wallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Wallet for {self.user}: {self.balance}'


class SessionRequest(models.Model):
    STATUS_CHOICES = (('open', 'Open'), ('booked', 'Booked'), ('closed', 'Closed'))
    DURATION_CHOICES = ((1, '1 hour'), (2, '2 hours'))
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='session_requests')
    topic = models.CharField(max_length=200)
    problem = models.TextField()
    tried = models.TextField(blank=True)
    preferred_duration_hours = models.PositiveSmallIntegerField(choices=DURATION_CHOICES, default=1)
    preferred_times = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', '-id')

    def __str__(self):
        return f'Session request by {self.student}: {self.topic}'


class MentorOffer(models.Model):
    STATUS_CHOICES = (('pending', 'Pending'), ('accepted', 'Accepted'), ('declined', 'Declined'))
    session_request = models.ForeignKey(SessionRequest, on_delete=models.CASCADE, related_name='offers')
    mentor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mentor_offers')
    mentor_profile = models.ForeignKey(MentorProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name='offers')
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    proposed_time = models.DateTimeField()
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'id')
        constraints = [models.UniqueConstraint(fields=['session_request', 'mentor'], name='unique_offer_per_mentor_request')]

    def __str__(self):
        return f'Offer by {self.mentor} on request {self.session_request_id}'


class MentorSession(models.Model):
    SOURCE_CHOICES = (('browse', 'Browse Mentors'), ('request', 'Session Request'))
    STATUS_CHOICES = (('pending', 'Pending mentor confirmation'), ('confirmed', 'Confirmed'), ('cancelled', 'Cancelled'), ('completed', 'Completed'))
    PAYMENT_CHOICES = (('unpaid', 'Unpaid'), ('paid', 'Paid'), ('refunded', 'Refunded'))
    DURATION_CHOICES = ((1, '1 hour'), (2, '2 hours'))
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mentor_sessions_as_student')
    mentor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mentor_sessions_as_mentor')
    mentor_profile = models.ForeignKey(MentorProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name='sessions')
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='browse')
    session_request = models.ForeignKey(SessionRequest, null=True, blank=True, on_delete=models.SET_NULL, related_name='sessions')
    offer = models.ForeignKey(MentorOffer, null=True, blank=True, on_delete=models.SET_NULL, related_name='sessions')
    topic = models.CharField(max_length=200)
    duration_hours = models.PositiveSmallIntegerField(choices=DURATION_CHOICES, default=1)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    total_fee = models.DecimalField(max_digits=12, decimal_places=2)
    scheduled_at = models.DateTimeField()
    meet_link = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='unpaid')
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-scheduled_at', '-id')

    def __str__(self):
        return f'Mentor session: {self.topic} ({self.student} with {self.mentor})'


class WalletTransaction(models.Model):
    KIND_CHOICES = (('top_up', 'Top-up'), ('session_payment', 'Session payment'), ('mentor_credit', 'Mentor credit'), ('platform_deduction', 'Platform deduction'), ('refund', 'Refund'))
    STATUS_CHOICES = (('completed', 'Completed'), ('paid', 'Paid'), ('credited', 'Credited to mentor'), ('refunded', 'Refunded'), ('deduction', 'Deduction applied'))
    wallet = models.ForeignKey(Wallet, null=True, blank=True, on_delete=models.CASCADE, related_name='transactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name='wallet_transactions')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    fee_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    deduction_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    credited_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    session = models.ForeignKey(MentorSession, null=True, blank=True, on_delete=models.SET_NULL, related_name='wallet_transactions')
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-id')

    def __str__(self):
        return f'{self.kind} {self.amount} ({self.status})'


class SessionRating(models.Model):
    session = models.OneToOneField(MentorSession, on_delete=models.CASCADE, related_name='rating')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='session_ratings_given')
    mentor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='session_ratings_received')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-id')

    def __str__(self):
        return f'Rating {self.rating} for session {self.session_id}'
