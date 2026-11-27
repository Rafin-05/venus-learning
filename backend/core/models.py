import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone

class UserManager(BaseUserManager):
    def create_user(self,email,password=None,**extra):
        if not email: raise ValueError('email required')
        user=self.model(email=self.normalize_email(email).lower().strip(),**extra)
        if password: user.set_password(password)
        user.save(using=self._db); return user
    def create_superuser(self,email,password,**extra):
        extra.update(role='admin',is_staff=True,is_superuser=True,is_verified=True,instructor_approved=True)
        return self.create_user(email,password,**extra)

class User(AbstractBaseUser,PermissionsMixin):
    ROLE_CHOICES=(('learner','Learner'),('instructor','Instructor'),('admin','Admin'))
    email=models.EmailField(unique=True); full_name=models.CharField(max_length=150); role=models.CharField(max_length=20,choices=ROLE_CHOICES,default='learner')
    title=models.CharField(max_length=150,blank=True)
    bio=models.TextField(blank=True); expertise=models.CharField(max_length=255,blank=True); profile_pic=models.URLField(blank=True)
    is_verified=models.BooleanField(default=False); instructor_approved=models.BooleanField(default=False); is_active=models.BooleanField(default=True); is_staff=models.BooleanField(default=False); is_demo_account=models.BooleanField(default=False)
    current_streak=models.PositiveIntegerField(default=0); points=models.PositiveIntegerField(default=0); verification_token=models.UUIDField(default=uuid.uuid4,editable=False)
    created_at=models.DateTimeField(auto_now_add=True)
    objects=UserManager(); USERNAME_FIELD='email'; REQUIRED_FIELDS=[]
    def save(self,*a,**k): self.email=self.email.strip().lower(); super().save(*a,**k)

class LoginAttempt(models.Model):
    email=models.EmailField(); ip=models.GenericIPAddressField(); failures=models.PositiveIntegerField(default=0); locked_until=models.DateTimeField(null=True,blank=True); updated_at=models.DateTimeField(auto_now=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['email','ip'],name='unique_login_attempt')]
class EmailToken(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE); token=models.UUIDField(default=uuid.uuid4,unique=True); kind=models.CharField(max_length=20); expires_at=models.DateTimeField(); used_at=models.DateTimeField(null=True,blank=True)
class Course(models.Model):
    STATUS=(('pending','Pending'),('approved','Approved'),('rejected','Rejected'))
    LEVEL_CHOICES=(('beginner','Beginner'),('intermediate','Intermediate'),('advanced','Advanced'))
    title=models.CharField(max_length=200); subtitle=models.CharField(max_length=300,blank=True); description=models.TextField(); category=models.CharField(max_length=100,blank=True); subcategory=models.CharField(max_length=100,blank=True); level=models.CharField(max_length=50,blank=True,choices=LEVEL_CHOICES); language=models.CharField(max_length=20,default='en'); thumbnail=models.URLField(blank=True); promo_video_url=models.URLField(blank=True); promo_provider_video_id=models.CharField(max_length=20,blank=True)
    # Wizard step B (PDF §4): measurable outcomes, audience and prerequisites.
    outcomes=models.JSONField(default=list,blank=True); target_audience=models.TextField(blank=True); prerequisites=models.TextField(blank=True)
    # Wizard step G (PDF §4): pricing and enrollment. A free course has price 0.
    price=models.DecimalField(max_digits=10,decimal_places=2,default=Decimal('0.00')); is_free=models.BooleanField(default=True); enrollment_open=models.BooleanField(default=True); access_duration_days=models.PositiveIntegerField(null=True,blank=True)
    # PDF §7/§17: video completion threshold (percent watched) for required lessons.
    completion_threshold=models.PositiveSmallIntegerField(default=90)
    instructor=models.ForeignKey(User,on_delete=models.CASCADE,related_name='courses'); status=models.CharField(max_length=20,choices=STATUS,default='pending'); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
class Unit(models.Model):
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='units'); title=models.CharField(max_length=200); position=models.PositiveIntegerField(default=0)
    class Meta: ordering=['position','id']
class Lesson(models.Model):
    LESSON_TYPES=(('video','Video'),('document','Document'),('coding','Coding'),('resource','Resource'),('quiz','Quiz'),('assignment','Assignment'))
    unit=models.ForeignKey(Unit,on_delete=models.CASCADE,related_name='lessons'); title=models.CharField(max_length=200); description=models.TextField(blank=True); content=models.TextField(blank=True); video_url=models.URLField(blank=True)
    # Provider-neutral video record (PDF §6): provider + provider_video_id, not a raw URL.
    # 'youtube' is the initial provider; other HTTPS hosts are stored as 'external'.
    provider=models.CharField(max_length=20,default='youtube'); provider_video_id=models.CharField(max_length=20,blank=True)
    document_url=models.URLField(blank=True); lesson_type=models.CharField(max_length=20,default='document',choices=LESSON_TYPES); coding_language=models.CharField(max_length=50,blank=True); coding_boilerplate=models.TextField(blank=True); coding_expected_output=models.TextField(blank=True); position=models.PositiveIntegerField(default=0)
    duration_seconds=models.PositiveIntegerField(null=True,blank=True); is_preview=models.BooleanField(default=False); is_required=models.BooleanField(default=True)
    class Meta: ordering=['position','id']
class Enrollment(models.Model):
    learner=models.ForeignKey(User,on_delete=models.CASCADE,related_name='enrollments'); course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='enrollments'); enrolled_at=models.DateTimeField(auto_now_add=True); completed_at=models.DateTimeField(null=True,blank=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['learner','course'],name='unique_enrollment')]
class LessonProgress(models.Model):
    enrollment=models.ForeignKey(Enrollment,on_delete=models.CASCADE,related_name='progress'); lesson=models.ForeignKey(Lesson,on_delete=models.CASCADE); progress=models.PositiveSmallIntegerField(default=0); completed_at=models.DateTimeField(null=True,blank=True)
    # PDF §7: actual playback progress, not just "opened the lesson".
    watched_seconds=models.PositiveIntegerField(default=0); duration_seconds=models.PositiveIntegerField(null=True,blank=True); watch_percentage=models.PositiveSmallIntegerField(default=0); resume_position_seconds=models.PositiveIntegerField(default=0); updated_at=models.DateTimeField(auto_now=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['enrollment','lesson'],name='unique_lesson_progress')]
class Certificate(models.Model):
    learner=models.ForeignKey(User,on_delete=models.CASCADE,related_name='certificates'); course=models.ForeignKey(Course,on_delete=models.CASCADE); issued_at=models.DateTimeField(auto_now_add=True); certificate_no=models.UUIDField(default=uuid.uuid4,unique=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['learner','course'],name='unique_certificate')]
class Quiz(models.Model):
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='quizzes'); lesson=models.ForeignKey(Lesson,on_delete=models.SET_NULL,null=True,blank=True,related_name='quizzes'); title=models.CharField(max_length=200); owner=models.ForeignKey(User,on_delete=models.CASCADE); pass_percentage=models.PositiveSmallIntegerField(default=70)
    time_limit_minutes=models.PositiveIntegerField(null=True,blank=True); attempts_allowed=models.PositiveIntegerField(null=True,blank=True); shuffle_questions=models.BooleanField(default=False); shuffle_options=models.BooleanField(default=False); show_answers=models.CharField(max_length=20,default='after_review',choices=(('immediate','Immediately'),('after_review','After review'),('never','Never')))
class CourseReview(models.Model):
    """Audit trail for the admin review workflow (PDF §13)."""
    DECISIONS=(('submitted','Submitted for review'),('approved','Approved'),('rejected','Rejected'),('changes_requested','Changes requested'))
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='course_reviews'); reviewer=models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name='course_reviews'); decision=models.CharField(max_length=20,choices=DECISIONS); notes=models.TextField(blank=True); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['-created_at','-id']
class CourseResource(models.Model):
    """Downloadable learning resource (PDF §8), at course level or attached to a lesson."""
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='resources'); lesson=models.ForeignKey(Lesson,on_delete=models.CASCADE,null=True,blank=True,related_name='resources'); title=models.CharField(max_length=200); description=models.TextField(blank=True); asset=models.ForeignKey('core.UploadedAsset',on_delete=models.SET_NULL,null=True,blank=True,related_name='course_resources'); external_url=models.URLField(blank=True); downloadable=models.BooleanField(default=True); original_name=models.CharField(max_length=255,blank=True); mime_type=models.CharField(max_length=100,blank=True); size_bytes=models.PositiveIntegerField(null=True,blank=True); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['created_at','id']
class Assignment(models.Model):
    """Homework assignment (PDF §10), attached to a course and optionally to a lesson item."""
    ACCEPTED=(('file','File upload'),('text','Text response'),('both','File or text'))
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='assignments'); lesson=models.ForeignKey(Lesson,on_delete=models.SET_NULL,null=True,blank=True,related_name='assignments'); title=models.CharField(max_length=200); instructions=models.TextField(); due_at=models.DateTimeField(null=True,blank=True); max_points=models.PositiveIntegerField(default=100); rubric=models.TextField(blank=True); accepted_types=models.CharField(max_length=10,default='both',choices=ACCEPTED); is_required=models.BooleanField(default=False); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['created_at','id']
class AssignmentSubmission(models.Model):
    STATUSES=(('submitted','Submitted'),('late','Late'),('under_review','Under review'),('graded','Graded'),('needs_resubmission','Needs resubmission'))
    assignment=models.ForeignKey(Assignment,on_delete=models.CASCADE,related_name='submissions'); learner=models.ForeignKey(User,on_delete=models.CASCADE,related_name='assignment_submissions'); text_response=models.TextField(blank=True); asset=models.ForeignKey('core.UploadedAsset',on_delete=models.SET_NULL,null=True,blank=True,related_name='assignment_submissions'); attempt_no=models.PositiveIntegerField(default=1); status=models.CharField(max_length=20,choices=STATUSES,default='submitted'); score=models.PositiveIntegerField(null=True,blank=True); feedback=models.TextField(blank=True); graded_by=models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name='graded_submissions'); graded_at=models.DateTimeField(null=True,blank=True); submitted_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['-submitted_at','-id']
class Question(models.Model):
    quiz=models.ForeignKey(Quiz,on_delete=models.CASCADE,related_name='questions'); question=models.TextField(); option_a=models.CharField(max_length=500); option_b=models.CharField(max_length=500); option_c=models.CharField(max_length=500,blank=True); option_d=models.CharField(max_length=500,blank=True); correct_answer=models.CharField(max_length=1,choices=[(x,x) for x in 'abcd'])
class QuizAttempt(models.Model):
    learner=models.ForeignKey(User,on_delete=models.CASCADE); quiz=models.ForeignKey(Quiz,on_delete=models.CASCADE); score=models.PositiveIntegerField(); total=models.PositiveIntegerField(default=0); percentage=models.DecimalField(max_digits=5,decimal_places=2,default=0); passed=models.BooleanField(default=False); answers=models.JSONField(default=dict); created_at=models.DateTimeField(auto_now_add=True)
class Contest(models.Model):
    title=models.CharField(max_length=200); description=models.TextField(blank=True); starts_at=models.DateTimeField(); ends_at=models.DateTimeField(); prize=models.CharField(max_length=200,blank=True); prizes=models.JSONField(default=list,blank=True); owner=models.ForeignKey(User,on_delete=models.CASCADE); questions=models.JSONField(default=list)
class ContestAttempt(models.Model):
    contest=models.ForeignKey(Contest,on_delete=models.CASCADE); learner=models.ForeignKey(User,on_delete=models.CASCADE); score=models.PositiveIntegerField(); total=models.PositiveIntegerField(default=0); percentage=models.DecimalField(max_digits=5,decimal_places=2,default=0); answers=models.JSONField(default=dict); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['contest','learner'],name='unique_contest_attempt')]
class Problem(models.Model):
    title=models.CharField(max_length=200); statement=models.TextField(); input_format=models.TextField(blank=True); output_format=models.TextField(blank=True); owner=models.ForeignKey(User,on_delete=models.CASCADE); test_cases=models.JSONField(default=list)
class Submission(models.Model):
    problem=models.ForeignKey(Problem,on_delete=models.CASCADE); learner=models.ForeignKey(User,on_delete=models.CASCADE); code=models.TextField(); language=models.CharField(max_length=30); status=models.CharField(max_length=30,default='pending'); result=models.TextField(blank=True); created_at=models.DateTimeField(auto_now_add=True)
class Rating(models.Model):
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='ratings'); learner=models.ForeignKey(User,on_delete=models.CASCADE); rating=models.PositiveSmallIntegerField(); review=models.TextField(blank=True); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['course','learner'],name='unique_rating')]
class SupportTicket(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='tickets'); subject=models.CharField(max_length=200); message=models.TextField(); response=models.TextField(blank=True); status=models.CharField(max_length=20,default='open'); created_at=models.DateTimeField(auto_now_add=True)
class DailyActivity(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='daily_activity'); day=models.DateField(default=timezone.now)
    class Meta: constraints=[models.UniqueConstraint(fields=['user','day'],name='unique_daily_activity')]

class ProblemCompletion(models.Model):
    learner=models.ForeignKey(User,on_delete=models.CASCADE,related_name='problem_completions')
    problem=models.ForeignKey(Problem,on_delete=models.CASCADE)
    completed_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['learner','problem'],name='unique_problem_completion')]
from .asset_models import UploadedAsset
from .mentor_models import MentorProfile, Wallet, WalletTransaction, MentorSession, SessionRequest, MentorOffer, SessionRating
from .proctor_models import ProctoredExamSession, ProctorEvent
