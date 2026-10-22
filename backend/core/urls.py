from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .assets import AssetUploadView, AssetContentView
from .views import *
router=DefaultRouter()
router.register('courses',CourseViewSet,basename='course')
router.register('units',UnitViewSet,basename='unit')
router.register('enrollments',EnrollmentViewSet,basename='enrollment')
router.register('lessons',LessonViewSet,basename='lesson')
router.register('ratings',RatingViewSet,basename='rating')
router.register('certificates',CertificateViewSet,basename='certificate')
router.register('quizzes',QuizViewSet,basename='quiz')
router.register('quiz-attempts',QuizAttemptViewSet,basename='quiz-attempt')
router.register('problems',ProblemViewSet,basename='problem')
router.register('submissions',SubmissionViewSet,basename='submission')
router.register('contests',ContestViewSet,basename='contest')
router.register('contest-attempts',ContestAttemptViewSet,basename='contest-attempt')
router.register('issues',IssueViewSet,basename='issue')
router.register('staff/users',StaffUserViewSet,basename='staff-user')
router.register('staff/courses',StaffCourseViewSet,basename='staff-course')
router.register('staff/issues',StaffIssueViewSet,basename='staff-issue')
urlpatterns=[path('uploads/', AssetUploadView.as_view()), path('uploads/<uuid:asset_id>/content/', AssetContentView.as_view()),
path('health/',HealthView.as_view()),path('auth/csrf/',CsrfView.as_view()),path('auth/register/',AuthView.as_view(),{'action':'register'}),path('auth/login/',AuthView.as_view(),{'action':'login'}),path('auth/logout/',LogoutView.as_view()),path('auth/me/',MeView.as_view()),path('profile/',MeView.as_view()),path('auth/change-password/',ChangePasswordView.as_view()),path('auth/verify/<uuid:token>/',VerifyView.as_view()),path('auth/resend-verification/',ResendVerificationView.as_view()),path('auth/password-reset/',PasswordResetView.as_view()),path('auth/password-reset/confirm/<uuid:token>/',PasswordResetView.as_view()),path('dashboard/',DashboardView.as_view()),path('leaderboard/',LeaderboardView.as_view()),path('staff/dashboard/',StaffDashboardView.as_view()),path('',include(router.urls))]
