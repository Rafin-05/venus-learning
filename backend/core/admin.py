from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from .models import *


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


for model in (Course, Unit, Lesson, Enrollment, LessonProgress, Certificate, Quiz, Question, QuizAttempt, Contest, ContestAttempt, Problem, ProblemCompletion, Submission, Rating, SupportTicket, LoginAttempt, EmailToken, DailyActivity):
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


for model in (MentorProfile, Wallet, SessionRequest, MentorOffer):
    admin.site.register(model)
admin.site.site_header = 'Venus Learning administration'
admin.site.site_title = 'Venus Learning'
admin.site.index_title = 'Platform management'
