from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        email = self.normalize_email(email).lower()
        if not email:
            raise ValueError('Email is required')
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES=(('learner','Learner'),('instructor','Instructor'),('admin','Admin'))
    email=models.EmailField(max_length=254,unique=True)
    full_name=models.CharField(max_length=150)
    role=models.CharField(max_length=20,choices=ROLE_CHOICES,default='learner')
    title=models.CharField(max_length=150,blank=True)
    bio=models.TextField(blank=True)
    expertise=models.CharField(max_length=255,blank=True)
    profile_pic=models.URLField(max_length=500,blank=True)
    points=models.PositiveIntegerField(default=0)
    current_streak=models.PositiveIntegerField(default=0)
    last_active_date=models.DateField(null=True,blank=True)
    is_verified=models.BooleanField(default=False)
    instructor_approved=models.BooleanField(default=False)
    is_active=models.BooleanField(default=True)
    is_staff=models.BooleanField(default=False)
    objects=CustomUserManager()
    USERNAME_FIELD='email'
    REQUIRED_FIELDS=['full_name']

    def __str__(self):
        return f'{self.full_name} ({self.email})'


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Course(models.Model):
    STATUS=(
        ('draft','Draft'),
        ('pending','Pending'),
        ('approved','Approved'),
        ('rejected','Rejected'),
    )
    title=models.CharField(max_length=255)
    subtitle=models.CharField(max_length=255,blank=True)
    description=models.TextField()
    category=models.CharField(max_length=100,blank=True,default='General')
    subcategory=models.CharField(max_length=100,blank=True)
    level=models.CharField(max_length=20,default='beginner')
    language=models.CharField(max_length=50,default='English')
    thumbnail=models.URLField(max_length=500,blank=True)
    promo_video_url=models.URLField(max_length=500,blank=True)
    promo_provider_video_id=models.CharField(max_length=100,blank=True)
    outcomes=models.JSONField(default=list,blank=True)
    target_audience=models.TextField(blank=True)
    prerequisites=models.TextField(blank=True)
    price=models.DecimalField(max_digits=10,decimal_places=2,default=0)
    is_free=models.BooleanField(default=True)
    enrollment_open=models.BooleanField(default=True)
    access_duration_days=models.PositiveIntegerField(null=True,blank=True)
    completion_threshold=models.PositiveIntegerField(default=90)
    instructor=models.ForeignKey(User,on_delete=models.CASCADE,related_name='courses')
    status=models.CharField(max_length=20,choices=STATUS,default='draft')
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Unit(models.Model):
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='units')
    title=models.CharField(max_length=255)
    position=models.PositiveIntegerField(default=1)

    class Meta:
        ordering=['position','id']

    def __str__(self):
        return f'{self.course.title} - {self.title}'


class Lesson(models.Model):
    LESSON_TYPES=(
        ('video','Video'),
        ('document','Document'),
        ('coding','Coding'),
    )
    unit=models.ForeignKey(Unit,on_delete=models.CASCADE,related_name='lessons')
    title=models.CharField(max_length=255)
    content=models.TextField(blank=True)
    video_url=models.URLField(max_length=500,blank=True)
    video_provider_id=models.CharField(max_length=100,blank=True)
    video_duration=models.PositiveIntegerField(null=True,blank=True)
    document_url=models.URLField(max_length=500,blank=True)
    lesson_type=models.CharField(max_length=20,default='document',choices=LESSON_TYPES)
    is_required=models.BooleanField(default=True)
    position=models.PositiveIntegerField(default=1)
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering=['position','id']

    def __str__(self):
        return f'{self.unit.title} - {self.title}'


class CourseReview(models.Model):
    DECISIONS=(('submitted','Submitted'),('approved','Approved'),('rejected','Rejected'),('changes_requested','Changes requested'))
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='course_reviews')
    reviewer=models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name='course_reviews')
    decision=models.CharField(max_length=20,choices=DECISIONS)
    notes=models.TextField(blank=True)
    created_at=models.DateTimeField(auto_now_add=True)


class Enrollment(models.Model):
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='enrollments')
    learner=models.ForeignKey(User,on_delete=models.CASCADE,related_name='enrollments')
    enrolled_at=models.DateTimeField(auto_now_add=True)
    completed_at=models.DateTimeField(null=True,blank=True)

    class Meta:
        unique_together=(('course','learner'),)


class LessonProgress(models.Model):
    enrollment=models.ForeignKey(Enrollment,on_delete=models.CASCADE,related_name='progress')
    lesson=models.ForeignKey(Lesson,on_delete=models.CASCADE,related_name='progress')
    progress=models.PositiveIntegerField(default=0)
    updated_at=models.DateTimeField(auto_now=True)

    class Meta:
        unique_together=(('enrollment','lesson'),)


class Certificate(models.Model):
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='certificates')
    learner=models.ForeignKey(User,on_delete=models.CASCADE,related_name='certificates')
    certificate_no=models.CharField(max_length=32,unique=True,blank=True)
    issued_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together=(('course','learner'),)

    def save(self, *args, **kwargs):
        if not self.certificate_no:
            self.certificate_no='VL-'+slugify(f'{self.course_id}-{self.learner_id}-{timezone.now().timestamp()}')[:24].upper()
        super().save(*args, **kwargs)


class Question(models.Model):
    quiz=models.ForeignKey('Quiz',on_delete=models.CASCADE,related_name='questions')
    question_text=models.TextField()
    option_a=models.CharField(max_length=1000)
    option_b=models.CharField(max_length=1000)
    option_c=models.CharField(max_length=1000,blank=True)
    option_d=models.CharField(max_length=1000,blank=True)
    correct_answer=models.CharField(max_length=1,choices=(('a','A'),('b','B'),('c','C'),('d','D')))


class Quiz(models.Model):
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='quizzes')
    lesson=models.ForeignKey(Lesson,on_delete=models.SET_NULL,null=True,blank=True,related_name='quizzes')
    title=models.CharField(max_length=255)
    pass_percentage=models.PositiveIntegerField(default=70)
    is_final=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering=['id']


class QuizAttempt(models.Model):
    quiz=models.ForeignKey(Quiz,on_delete=models.CASCADE,related_name='attempts')
    learner=models.ForeignKey(User,on_delete=models.CASCADE,related_name='quiz_attempts')
    score=models.PositiveIntegerField()
    total=models.PositiveIntegerField()
    percentage=models.FloatField()
    passed=models.BooleanField(default=False)
    answers=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)


class Assignment(models.Model):
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='assignments')
    lesson=models.ForeignKey(Lesson,on_delete=models.SET_NULL,null=True,blank=True,related_name='assignments')
    title=models.CharField(max_length=255)
    instructions=models.TextField(blank=True)
    due_at=models.DateTimeField(null=True,blank=True)
    max_points=models.PositiveIntegerField(default=100)
    rubric=models.TextField(blank=True)
    accepted_types=models.CharField(max_length=255,blank=True,default='pdf,docx,txt,zip')
    is_required=models.BooleanField(default=True)
    created_at=models.DateTimeField(auto_now_add=True)


class AssignmentSubmission(models.Model):
    STATUS=(('submitted','Submitted'),('graded','Graded'))
    assignment=models.ForeignKey(Assignment,on_delete=models.CASCADE,related_name='submissions')
    learner=models.ForeignKey(User,on_delete=models.CASCADE,related_name='assignment_submissions')
    text_response=models.TextField(blank=True)
    asset=models.ForeignKey('asset_models.UploadedAsset',on_delete=models.SET_NULL,null=True,blank=True,related_name='assignment_submissions')
    attempt_no=models.PositiveIntegerField(default=1)
    status=models.CharField(max_length=20,choices=STATUS,default='submitted')
    score=models.FloatField(null=True,blank=True)
    feedback=models.TextField(blank=True)
    graded_by=models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name='graded_assignments')
    graded_at=models.DateTimeField(null=True,blank=True)
    submitted_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together=(('assignment','learner','attempt_no'),)
        ordering=['-submitted_at','-id']


class CourseResource(models.Model):
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='resources')
    lesson=models.ForeignKey(Lesson,on_delete=models.SET_NULL,null=True,blank=True,related_name='resources')
    title=models.CharField(max_length=255)
    description=models.TextField(blank=True)
    asset=models.ForeignKey('asset_models.UploadedAsset',on_delete=models.SET_NULL,null=True,blank=True,related_name='resources')
    external_url=models.URLField(max_length=500,blank=True)
    downloadable=models.BooleanField(default=True)
    original_name=models.CharField(max_length=255,blank=True)
    mime_type=models.CharField(max_length=100,blank=True)
    size_bytes=models.PositiveIntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)


class Rating(models.Model):
    course=models.ForeignKey(Course,on_delete=models.CASCADE,related_name='ratings')
    learner=models.ForeignKey(User,on_delete=models.CASCADE,related_name='ratings')
    rating=models.PositiveSmallIntegerField()
    review=models.TextField(blank=True)
    created_at=models.DateTimeField(auto_now_add=True)


class Problem(models.Model):
    title=models.CharField(max_length=255)
    statement=models.TextField()
    input_format=models.TextField(blank=True)
    output_format=models.TextField(blank=True)
    test_cases=models.JSONField(default=list)
    owner=models.ForeignKey(User,on_delete=models.CASCADE,related_name='problems')
    created_at=models.DateTimeField(auto_now_add=True)


class Submission(models.Model):
    STATUS=(('accepted','Accepted'),('failed','Failed'),('runner_error','Runner error'))
    problem=models.ForeignKey(Problem,on_delete=models.CASCADE,related_name='submissions')
    learner=models.ForeignKey(User,on_delete=models.CASCADE,related_name='submissions')
    code=models.TextField()
    language=models.CharField(max_length=20,default='71')
    status=models.CharField(max_length=20,choices=STATUS,default='failed')
    result=models.TextField(blank=True)
    created_at=models.DateTimeField(auto_now_add=True)


class ProblemCompletion(models.Model):
    learner=models.ForeignKey(User,on_delete=models.CASCADE,related_name='problem_completions')
    problem=models.ForeignKey(Problem,on_delete=models.CASCADE,related_name='completions')
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together=(('learner','problem'),)


class Contest(models.Model):
    title=models.CharField(max_length=255)
    description=models.TextField(blank=True)
    starts_at=models.DateTimeField()
    ends_at=models.DateTimeField()
    prize=models.CharField(max_length=255,blank=True)
    prizes=models.JSONField(default=list,blank=True)
    questions=models.JSONField(default=list)
    owner=models.ForeignKey(User,on_delete=models.CASCADE,related_name='contests')
    created_at=models.DateTimeField(auto_now_add=True)


class ContestAttempt(models.Model):
    contest=models.ForeignKey(Contest,on_delete=models.CASCADE,related_name='attempts')
    learner=models.ForeignKey(User,on_delete=models.CASCADE,related_name='contest_attempts')
    score=models.PositiveIntegerField()
    total=models.PositiveIntegerField()
    percentage=models.FloatField()
    answers=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together=(('contest','learner'),)


class FocusSession(models.Model):
    TARGET_MINUTES=(30,60)
    learner=models.ForeignKey(User,on_delete=models.CASCADE,related_name='focus_sessions')
    target_minutes=models.PositiveIntegerField()
    started_at=models.DateTimeField(auto_now_add=True)
    ended_at=models.DateTimeField(null=True,blank=True)
    focused_seconds=models.PositiveIntegerField(default=0)
    status=models.CharField(max_length=20,default='active')


class SupportTicket(models.Model):
    STATUS=(('open','Open'),('in_progress','In progress'),('resolved','Resolved'),('closed','Closed'))
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='tickets')
    subject=models.CharField(max_length=255)
    message=models.TextField()
    response=models.TextField(blank=True)
    status=models.CharField(max_length=20,choices=STATUS,default='open')
    created_at=models.DateTimeField(auto_now_add=True)
