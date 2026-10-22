from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import User, Course, Unit, Lesson, Quiz, Question, Problem, Contest

DEMO_ACCOUNTS = {
    'learner': {'email': 'demo.learner@example.com', 'password': 'VenusDemo-Learner-2026!', 'full_name': 'Demo Learner'},
    'instructor': {'email': 'demo.instructor@example.com', 'password': 'VenusDemo-Instructor-2026!', 'full_name': 'Demo Instructor'},
    'admin': {'email': 'demo.admin@example.com', 'password': 'VenusDemo-Admin-2026!', 'full_name': 'Demo Administrator'},
}


class Command(BaseCommand):
    help = 'Create opt-in local evaluation accounts and sample data.'

    def add_arguments(self, parser):
        parser.add_argument('--reset-passwords', action='store_true', help='Restore fixed passwords only for existing flagged demo accounts.')

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG or not settings.ENABLE_DEMO_ACCOUNTS:
            raise CommandError('Demo seeding is disabled unless both DEBUG=true and ENABLE_DEMO_ACCOUNTS=true. It never runs automatically.')

        # Preflight every address before changing anything: real accounts are never claimed.
        existing = {}
        for role, spec in DEMO_ACCOUNTS.items():
            user = User.objects.select_for_update().filter(email=spec['email']).first()
            if user:
                if not user.is_demo_account:
                    raise CommandError(f"Refusing to claim existing unflagged account {spec['email']}.")
                if user.role != role:
                    raise CommandError(f"Refusing demo account {spec['email']}: expected role {role}, found {user.role}.")
                existing[role] = user

        for spec in DEMO_ACCOUNTS.values():
            try:
                validate_password(spec['password'])
            except Exception as error:
                raise CommandError(str(error))

        accounts = {}
        for role, spec in DEMO_ACCOUNTS.items():
            user = existing.get(role)
            if user is None:
                user = User(email=spec['email'], full_name=spec['full_name'], role=role,
                            is_demo_account=True, is_verified=True, is_active=True,
                            instructor_approved=(role == 'instructor'), is_staff=(role == 'admin'),
                            is_superuser=(role == 'admin'))
                user.set_password(spec['password'])
                user.save()
            else:
                changed = []
                required = {'is_demo_account': True, 'is_verified': True, 'is_active': True,
                            'instructor_approved': role == 'instructor', 'is_staff': role == 'admin',
                            'is_superuser': role == 'admin'}
                for field, value in required.items():
                    if getattr(user, field) != value:
                        setattr(user, field, value)
                        changed.append(field)
                if options['reset_passwords']:
                    user.set_password(spec['password'])
                    changed.append('password')
                if changed:
                    user.save(update_fields=changed)
            accounts[role] = user

        # Preserve the existing sample content and make each object idempotent.
        for title, category, description, content, image in (
            ('Python Foundations', 'Programming', 'Start with the building blocks of clear, practical Python programs.', 'Python uses variables to name values. Try reading a short program, predicting its output, and explaining it in your own words. A variable such as total = 3 stores the number 3. Use print(total) to display it. This lesson introduces names, values, and simple output.', 'course-1.png'),
            ('Design with Purpose', 'Design', 'Understand the decisions behind clear, accessible digital experiences.', 'Good design makes the next step clear. Begin with a user goal, remove unnecessary choices, use readable contrast, and label actions with specific verbs. Test your design with someone who has not seen it before and ask them to describe what they would do next.', 'course-2.png'),
        ):
            course, _ = Course.objects.get_or_create(title=title, instructor=accounts['instructor'], defaults={'description': description, 'category': category, 'level': 'Beginner', 'status': 'approved', 'thumbnail': f'{settings.FRONTEND_URL}/{image}'})
            unit, _ = Unit.objects.get_or_create(course=course, title='Getting started', defaults={'position': 0})
            Lesson.objects.get_or_create(unit=unit, title='Your first steps', defaults={'content': content, 'lesson_type': 'document', 'position': 0})
            quiz, _ = Quiz.objects.get_or_create(course=course, title='Check your understanding', owner=accounts['instructor'], defaults={'pass_percentage': 70})
            Question.objects.get_or_create(quiz=quiz, question='Which approach supports learning?', defaults={'option_a': 'Practice and explain what you learned', 'option_b': 'Skip every exercise', 'option_c': 'Never ask questions', 'option_d': 'Avoid feedback', 'correct_answer': 'a'})
        Problem.objects.get_or_create(title='Hello, Venus', owner=accounts['instructor'], defaults={'statement': 'Print Hello, Venus on one line.', 'input_format': 'No input.', 'output_format': 'Hello, Venus', 'test_cases': [{'input': '', 'output': 'Hello, Venus\n'}]})
        Contest.objects.get_or_create(title='Learning essentials challenge', owner=accounts['admin'], defaults={'description': 'A short sample challenge for evaluating contest participation.', 'starts_at': timezone.now()-timedelta(hours=1), 'ends_at': timezone.now()+timedelta(days=7), 'prizes': [{'position': 1, 'prize_label': 'Community recognition'}], 'questions': [{'id': 'q1', 'question': 'What is a helpful next step when you get stuck?', 'option_a': 'Break the problem into smaller parts', 'option_b': 'Ignore the problem forever', 'correct_answer': 'a'}]})
        self.stdout.write(self.style.SUCCESS('Demo data ready. Accounts are enabled only while DEBUG=true and ENABLE_DEMO_ACCOUNTS=true.'))
