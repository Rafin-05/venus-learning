import uuid
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
    title=models.CharField(max_length=200); description=models.TextField(); category=models.CharField(max_length=100,blank=True); level=models.CharField(max_length=50,blank=True); thumbnail=models.URLField(blank=True); instructor=models.ForeignKey(User,on_delete=models.CASCADE,related_name='courses'); status=models.CharField(max_length=20,choices=STATUS,default='pending'); created_at=models.DateTimeField(auto_now_add=True)
class Unit(models.Model):
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='units'); title=models.CharField(max_length=200); position=models.PositiveIntegerField(default=0)
    class Meta: ordering=['position','id']
class Lesson(models.Model):
    unit=models.ForeignKey(Unit,on_delete=models.CASCADE,related_name='lessons'); title=models.CharField(max_length=200); content=models.TextField(blank=True); video_url=models.URLField(blank=True); document_url=models.URLField(blank=True); lesson_type=models.CharField(max_length=20,default='document'); coding_language=models.CharField(max_length=50,blank=True); coding_boilerplate=models.TextField(blank=True); coding_expected_output=models.TextField(blank=True); position=models.PositiveIntegerField(default=0)
    class Meta: ordering=['position','id']
class Enrollment(models.Model):
    learner=models.ForeignKey(User,on_delete=models.CASCADE,related_name='enrollments'); course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='enrollments'); enrolled_at=models.DateTimeField(auto_now_add=True); completed_at=models.DateTimeField(null=True,blank=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['learner','course'],name='unique_enrollment')]
class LessonProgress(models.Model):
    enrollment=models.ForeignKey(Enrollment,on_delete=models.CASCADE,related_name='progress'); lesson=models.ForeignKey(Lesson,on_delete=models.CASCADE); progress=models.PositiveSmallIntegerField(default=0); completed_at=models.DateTimeField(null=True,blank=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['enrollment','lesson'],name='unique_lesson_progress')]
class Certificate(models.Model):
    learner=models.ForeignKey(User,on_delete=models.CASCADE,related_name='certificates'); course=models.ForeignKey(Course,on_delete=models.CASCADE); issued_at=models.DateTimeField(auto_now_add=True); certificate_no=models.UUIDField(default=uuid.uuid4,unique=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['learner','course'],name='unique_certificate')]
class Quiz(models.Model):
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='quizzes'); title=models.CharField(max_length=200); owner=models.ForeignKey(User,on_delete=models.CASCADE); pass_percentage=models.PositiveSmallIntegerField(default=70)
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
