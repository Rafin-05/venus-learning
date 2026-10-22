from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from .models import *


def is_staff_user(user):
    return bool(user and user.is_authenticated and user.is_active and (user.is_staff or user.role == 'admin'))


def owns_course(user, course):
    return bool(user and user.is_authenticated and (is_staff_user(user) or (user.role == 'instructor' and user.instructor_approved and course.instructor_id == user.id)))


def safe_url(value):
    if value and not value.lower().startswith(('https://', 'http://')):
        raise serializers.ValidationError('Only HTTP(S) links are allowed.')
    return value


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'full_name', 'role', 'bio', 'expertise', 'profile_pic', 'current_streak', 'points', 'is_verified', 'instructor_approved', 'is_active')
        read_only_fields = ('id', 'email', 'role', 'current_streak', 'points', 'is_verified', 'instructor_approved', 'is_active')

    def validate_profile_pic(self, value):
        return safe_url(value)


class StaffUserSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        read_only_fields = ('id', 'email', 'role', 'current_streak', 'points', 'is_verified')


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, min_length=10, max_length=128, trim_whitespace=False)
    full_name = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(choices=('learner', 'instructor'), default='learner')

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Registration could not be completed for this address. Try signing in or resetting your password.')
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages)
        return value

    def create(self, data):
        return User.objects.create_user(**data, is_verified=False, instructor_approved=False)


class PublicInstructorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'full_name', 'bio', 'expertise', 'profile_pic')


class CourseSerializer(serializers.ModelSerializer):
    instructor = PublicInstructorSerializer(read_only=True)
    instructor_name = serializers.CharField(source='instructor.full_name', read_only=True)
    average_rating = serializers.SerializerMethodField()
    student_count = serializers.SerializerMethodField()
    lesson_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ('id', 'title', 'description', 'category', 'level', 'thumbnail', 'instructor', 'instructor_name', 'status', 'created_at', 'average_rating', 'student_count', 'lesson_count')
        read_only_fields = ('id', 'instructor', 'instructor_name', 'status', 'created_at')

    def get_average_rating(self, course):
        from django.db.models import Avg
        return round(course.ratings.aggregate(value=Avg('rating'))['value'] or 0, 2)

    def get_student_count(self, course):
        return course.enrollments.count()

    def get_lesson_count(self, course):
        return Lesson.objects.filter(unit__course=course).count()

    def validate_thumbnail(self, value):
        return safe_url(value)


class StaffCourseSerializer(CourseSerializer):
    class Meta(CourseSerializer.Meta):
        read_only_fields = ('id', 'instructor', 'instructor_name', 'created_at')


class CurriculumLessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ('id', 'title', 'lesson_type', 'position')


class LessonSerializer(serializers.ModelSerializer):
    progress = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = ('id', 'unit', 'title', 'content', 'video_url', 'document_url', 'lesson_type', 'coding_language', 'coding_boilerplate', 'coding_expected_output', 'position', 'progress')
        read_only_fields = ('id', 'progress')
        extra_kwargs = {'content': {'max_length': 100000}, 'coding_boilerplate': {'max_length': 100000}, 'coding_expected_output': {'max_length': 20000}}

    def get_progress(self, lesson):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
        return LessonProgress.objects.filter(enrollment__learner=request.user, lesson=lesson).values_list('progress', flat=True).first() or 0

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if not request or not owns_course(request.user, instance.unit.course):
            data.pop('coding_expected_output', None)
        return data

    def validate_video_url(self, value):
        return safe_url(value)

    def validate_document_url(self, value):
        return safe_url(value)

    def validate_lesson_type(self, value):
        if value not in ('video', 'document', 'coding'):
            raise serializers.ValidationError('Choose video, document, or coding.')
        return value

    def validate(self, data):
        kind = data.get('lesson_type', getattr(self.instance, 'lesson_type', 'document'))
        if kind == 'coding':
            language = data.get('coding_language', getattr(self.instance, 'coding_language', ''))
            if str(language).lower() not in ('50', '54', '60', '62', '63', '71', '73', '74', '78', 'python', 'javascript', 'java', 'cpp', 'c++', 'c', 'go', 'rust'):
                raise serializers.ValidationError({'coding_language': 'Choose a supported execution language.'})
        return data


class UnitSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Unit
        fields = ('id', 'course', 'title', 'position', 'lessons')
        read_only_fields = ('id',)


class CurriculumUnitSerializer(serializers.ModelSerializer):
    lessons = CurriculumLessonSerializer(many=True, read_only=True)

    class Meta:
        model = Unit
        fields = ('id', 'title', 'position', 'lessons')


class CourseDetailSerializer(CourseSerializer):
    units = serializers.SerializerMethodField()

    class Meta(CourseSerializer.Meta):
        fields = CourseSerializer.Meta.fields + ('units',)

    def get_units(self, course):
        request = self.context.get('request')
        serializer = UnitSerializer if request and owns_course(request.user, course) else CurriculumUnitSerializer
        return serializer(course.units.all(), many=True, context=self.context).data


class EnrollmentSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    progress_percent = serializers.SerializerMethodField()

    def get_progress_percent(self, enrollment):
        total = Lesson.objects.filter(unit__course=enrollment.course).count()
        done = enrollment.progress.filter(progress=100, lesson__unit__course=enrollment.course).count()
        return round(done * 100 / total) if total else 0

    class Meta:
        model = Enrollment
        fields = ('id', 'course', 'enrolled_at', 'completed_at', 'progress_percent')


class CertificateSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    learner = UserSerializer(read_only=True)
    learner_name = serializers.CharField(source='learner.full_name', read_only=True)

    class Meta:
        model = Certificate
        fields = ('id', 'course', 'learner', 'learner_name', 'issued_at', 'certificate_no')


class RatingSerializer(serializers.ModelSerializer):
    learner_name = serializers.CharField(source='learner.full_name', read_only=True)

    class Meta:
        model = Rating
        fields = ('id', 'course', 'rating', 'review', 'learner_name', 'created_at')
        read_only_fields = ('id', 'learner_name', 'created_at')
        extra_kwargs = {'review': {'max_length': 5000}}

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError('Rating must be between 1 and 5.')
        return value


class TicketSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = SupportTicket
        fields = ('id', 'user', 'subject', 'message', 'response', 'status', 'created_at')
        read_only_fields = ('id', 'user', 'response', 'status', 'created_at')
        extra_kwargs = {'message': {'max_length': 10000}}


class StaffTicketSerializer(TicketSerializer):
    status = serializers.ChoiceField(choices=('open', 'in_progress', 'resolved', 'closed'), required=False)

    class Meta(TicketSerializer.Meta):
        read_only_fields = ('id', 'user', 'subject', 'message', 'created_at')
        extra_kwargs = {'response': {'max_length': 10000}}


class QuestionSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    correct_answer = serializers.ChoiceField(choices=tuple('abcd'), required=False)

    class Meta:
        model = Question
        fields = ('id', 'question', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer')


class QuizSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True)

    class Meta:
        model = Quiz
        fields = ('id', 'course', 'title', 'pass_percentage', 'questions', 'owner')
        read_only_fields = ('id', 'owner')

    def validate_pass_percentage(self, value):
        if not 1 <= value <= 100:
            raise serializers.ValidationError('Pass mark must be between 1 and 100.')
        return value

    def validate_questions(self, questions):
        if not questions or len(questions) > 100:
            raise serializers.ValidationError('Provide between 1 and 100 questions.')
        existing = {question.id: question for question in self.instance.questions.all()} if self.instance else {}
        seen = set()
        for question in questions:
            old = existing.get(question.get('id'))
            if question.get('id') is not None and (old is None or question['id'] in seen):
                raise serializers.ValidationError('Question ID does not belong to this quiz or is duplicated.')
            seen.add(question.get('id'))
            if 'correct_answer' not in question:
                if old:
                    question['correct_answer'] = old.correct_answer
                else:
                    raise serializers.ValidationError('Every question needs a correct answer.')
            if not question.get('option_' + question['correct_answer'], getattr(old, 'option_' + question['correct_answer'], '')):
                raise serializers.ValidationError('The correct answer must refer to a nonempty option.')
        return questions

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if not request or not owns_course(request.user, instance.course):
            for question in data['questions']:
                question.pop('correct_answer', None)
        return data

    @transaction.atomic
    def create(self, data):
        questions = data.pop('questions')
        quiz = Quiz.objects.create(**data)
        for question in questions:
            question.pop('id', None)
            Question.objects.create(quiz=quiz, **question)
        return quiz

    @transaction.atomic
    def update(self, instance, data):
        questions = data.pop('questions', None)
        instance = super().update(instance, data)
        if questions is not None:
            instance.questions.all().delete()
            for question in questions:
                question.pop('id', None)
                Question.objects.create(quiz=instance, **question)
            QuizAttempt.objects.filter(quiz=instance).delete()
        return instance


# Alias retained for integrations that imported the previous write serializer.
QuizWriteSerializer = QuizSerializer


class ProblemSerializer(serializers.ModelSerializer):
    test_cases = serializers.JSONField(required=True)

    class Meta:
        model = Problem
        fields = ('id', 'title', 'statement', 'input_format', 'output_format', 'owner', 'test_cases')
        read_only_fields = ('id', 'owner')
        extra_kwargs = {'statement': {'max_length': 30000}}

    def validate_test_cases(self, value):
        if not isinstance(value, list) or not 1 <= len(value) <= 20:
            raise serializers.ValidationError('Provide 1–20 test cases as a JSON array.')
        for case in value:
            if not isinstance(case, dict) or 'output' not in case or not isinstance(case.get('input', ''), str) or not isinstance(case['output'], str):
                raise serializers.ValidationError('Each case requires string input and output fields.')
            if len(case.get('input', '')) > 20000 or len(case['output']) > 20000:
                raise serializers.ValidationError('Test case content is too long.')
        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if not request or not (is_staff_user(request.user) or instance.owner_id == request.user.id):
            data.pop('test_cases', None)
        return data


class ContestSerializer(serializers.ModelSerializer):
    questions = serializers.JSONField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Contest
        fields = ('id', 'title', 'description', 'starts_at', 'ends_at', 'prize', 'prizes', 'owner', 'questions', 'status')
        read_only_fields = ('id', 'owner', 'status')

    def get_status(self, contest):
        now = timezone.now()
        return 'upcoming' if now < contest.starts_at else 'ended' if now >= contest.ends_at else 'active'

    def validate_prizes(self, value):
        if not isinstance(value, list) or len(value) > 100:
            raise serializers.ValidationError('Prizes must be an array with at most 100 entries.')
        seen = set()
        for prize in value:
            if not isinstance(prize, dict) or type(prize.get('position')) is not int or not 1 <= prize['position'] <= 100:
                raise serializers.ValidationError('Every prize requires a numeric position from 1 to 100.')
            if prize['position'] in seen or not isinstance(prize.get('prize_label'), str) or not 1 <= len(prize['prize_label'].strip()) <= 255:
                raise serializers.ValidationError('Prize positions must be unique and labels must be 1–255 characters.')
            seen.add(prize['position'])
        return sorted(value, key=lambda prize: prize['position'])

    def validate_questions(self, questions):
        if not isinstance(questions, list) or not 1 <= len(questions) <= 100:
            raise serializers.ValidationError('Provide 1–100 contest questions.')
        seen = set()
        for question in questions:
            if not isinstance(question, dict):
                raise serializers.ValidationError('Question must be an object.')
            key = str(question.get('id', ''))
            if not key or len(key) > 50 or key in seen:
                raise serializers.ValidationError('Each question needs a unique short ID.')
            seen.add(key)
            if not isinstance(question.get('question'), str) or not question['question'].strip():
                raise serializers.ValidationError('Each question needs question text.')
            for option in ('option_a', 'option_b', 'option_c', 'option_d'):
                if option not in question:
                    if option in ('option_a', 'option_b'):
                        raise serializers.ValidationError('Each question requires option_a and option_b.')
                    continue
                value = question[option]
                if not isinstance(value, str) or len(value) > 1000:
                    raise serializers.ValidationError('Each option must be a string of at most 1000 characters.')
                if option in ('option_a', 'option_b') and not value.strip():
                    raise serializers.ValidationError('Each question requires option_a and option_b.')
            answer = question.get('correct_answer')
            selected = question.get('option_' + answer) if answer in tuple('abcd') else None
            if answer not in tuple('abcd') or not isinstance(selected, str) or not selected.strip():
                raise serializers.ValidationError('Correct answer must refer to a nonempty a–d option.')
        return questions

    def validate(self, data):
        start = data.get('starts_at', getattr(self.instance, 'starts_at', None))
        end = data.get('ends_at', getattr(self.instance, 'ends_at', None))
        if start and end and end <= start:
            raise serializers.ValidationError({'ends_at': 'End must be later than start.'})
        return data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if not request or not is_staff_user(request.user):
            data['questions'] = [] if timezone.now() < instance.starts_at else [{key: value for key, value in question.items() if key != 'correct_answer'} for question in instance.questions]
        return data


ContestWriteSerializer = ContestSerializer


class AttemptSerializer(serializers.ModelSerializer):
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)

    class Meta:
        model = QuizAttempt
        fields = ('id', 'quiz', 'quiz_title', 'score', 'total', 'percentage', 'passed', 'created_at')


class ContestAttemptSerializer(serializers.ModelSerializer):
    contest_title = serializers.CharField(source='contest.title', read_only=True)

    class Meta:
        model = ContestAttempt
        fields = ('id', 'contest', 'contest_title', 'score', 'total', 'percentage', 'created_at')


class SubmissionSerializer(serializers.ModelSerializer):
    problem_title = serializers.CharField(source='problem.title', read_only=True)

    class Meta:
        model = Submission
        fields = ('id', 'problem', 'problem_title', 'language', 'status', 'result', 'created_at')
        read_only_fields = fields
