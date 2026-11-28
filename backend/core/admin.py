from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from rest_framework.exceptions import ValidationError
from . import finance_services
from .finance_models import TopUpRequest, WithdrawalRequest
from .models import *
from .proctor_models import ProctoredExamSession, ProctorEvent


class AccountCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('email', 'full_name', 'role')


class AccountChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = '__all__'


@admin.register(User)
class AccountAdmin(UserAdmin):
    add_form = AccountCreationForm
    form = AccountChangeForm
    ordering = ('email',)
    list_display = ('email', 'full_name', 'role', 'is_active', 'is_verified', 'instructor_approved')
    list_filter = ('role', 'is_active', 'is_verified', 'instructor_approved')
    search_fields = ('email', 'full_name')
    readonly_fields = ('last_login', 'created_at', 'verification_token', 'points', 'current_streak')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Profile', {'fields': ('full_name', 'bio', 'expertise', 'profile_pic')}),
        ('Account access', {'fields': ('role', 'is_active', 'is_verified', 'instructor_approved')}),
        ('Django administration', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Activity', {'fields': ('last_login', 'created_at', 'points', 'current_streak', 'verification_token')}),
    )
    add_fieldsets = ((None, {'classes': ('wide',), 'fields': ('email', 'full_name', 'role', 'password1', 'password2')}),)


for model in (Category, Course, Unit, Lesson, Enrollment, LessonProgress, Certificate, Quiz, Question, QuizAttempt, Contest, ContestAttempt, Problem, ProblemCompletion, Submission, Rating, SupportTicket, LoginAttempt, EmailToken, DailyActivity):
    admin.site.register(model)


@admin.register(SessionRating)
class SessionRatingAdmin(admin.ModelAdmin):
    list_display = ('session', 'student', 'mentor', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('comment', 'student__email', 'mentor__email', 'session__topic')
    readonly_fields = ('created_at',)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('kind', 'status', 'amount', 'fee_amount', 'deduction_amount', 'credited_amount', 'user', 'session', 'created_at')
    list_filter = ('kind', 'status', 'created_at')
    search_fields = ('note', 'user__email')
    readonly_fields = ('created_at',)


@admin.register(MentorSession)
class MentorSessionAdmin(admin.ModelAdmin):
    list_display = ('topic', 'student', 'mentor', 'scheduled_at', 'duration_hours', 'total_fee', 'status', 'payment_status')
    list_filter = ('status', 'payment_status', 'source')
    search_fields = ('topic', 'student__email', 'mentor__email')


def _approve_top_ups(modeladmin, request, queryset):
    for top_up in queryset.filter(status='pending'):
        finance_services.approve_top_up(top_up.pk, request.user)


def _reject_top_ups(modeladmin, request, queryset):
    for top_up in queryset.filter(status='pending'):
        finance_services.reject_top_up(top_up.pk, request.user, 'Rejected from the admin panel.')


def _approve_withdrawals(modeladmin, request, queryset):
    errors = []
    for withdrawal in queryset.filter(status='pending'):
        try:
            finance_services.approve_withdrawal(withdrawal.pk, request.user)
        except ValidationError:
            errors.append(str(withdrawal.pk))
    if errors:
        modeladmin.message_user(request, f'Could not pay withdrawal(s) {", ".join(errors)}: balance too low.', messages.ERROR)


def _reject_withdrawals(modeladmin, request, queryset):
    for withdrawal in queryset.filter(status='pending'):
        finance_services.reject_withdrawal(withdrawal.pk, request.user, 'Rejected from the admin panel.')


@admin.register(TopUpRequest)
class TopUpRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'method', 'amount', 'transaction_id', 'account_number', 'status', 'created_at')
    list_filter = ('status', 'method', 'created_at')
    search_fields = ('user__email', 'transaction_id', 'account_number')
    readonly_fields = ('created_at', 'reviewed_by', 'reviewed_at')
    actions = (_approve_top_ups, _reject_top_ups)
    actions_on_top = True


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'method', 'amount', 'account_number', 'status', 'created_at')
    list_filter = ('status', 'method', 'created_at')
    search_fields = ('user__email', 'account_number')
    readonly_fields = ('created_at', 'reviewed_by', 'reviewed_at')
    actions = (_approve_withdrawals, _reject_withdrawals)
    actions_on_top = True


@admin.register(ProctoredExamSession)
class ProctoredExamSessionAdmin(admin.ModelAdmin):
    list_display = ('learner', 'quiz', 'course', 'status', 'risk_score', 'started_at', 'ended_at')
    list_filter = ('status', 'started_at')
    search_fields = ('learner__email', 'quiz__title', 'course__title')
    readonly_fields = ('started_at', 'ended_at', 'risk_score', 'consent_at')


@admin.register(ProctorEvent)
class ProctorEventAdmin(admin.ModelAdmin):
    list_display = ('session', 'event_type', 'severity', 'created_at')
    list_filter = ('event_type', 'severity', 'created_at')
    search_fields = ('session__learner__email',)


for model in (MentorProfile, Wallet, SessionRequest, MentorOffer):
    admin.site.register(model)
admin.site.site_header = 'Venus Learning administration'
admin.site.site_title = 'Venus Learning'
admin.site.index_title = 'Platform management'
