from datetime import timedelta
from random import Random
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import (User, Course, Unit, Lesson, Enrollment,
                         LessonProgress, Certificate, FocusSession,
                         Quiz, Question, Rating)

# One shared password for all 63 test accounts. It is printed in the
# test-accounts.md list so Rafin can log in as any of them.
PASSWORD = 'TestPass-2026!'
# Fixed seed so every run makes the same choices: re-running the command
# finds the same rows and creates no duplicates.
SEED = 20261128
# Open-licensed Big Buck Bunny test video, used as the YouTube video for
# every seeded video lesson.
VIDEO_ID = 'aqz-KE-bpKQ'

# 63 distinct Bangladeshi first names: 50 learners, 10 instructors, 3 admins.
FIRST_NAMES = [
    # learners (male)
    'Rahim', 'Karim', 'Tanvir', 'Arif', 'Mehedi', 'Rakib', 'Sakib', 'Fahim',
    'Naim', 'Shihab', 'Rashed', 'Imran', 'Hasan', 'Mahmud', 'Abdullah',
    'Farhan', 'Sourav', 'Anik', 'Rifat', 'Tanmoy', 'Sajib', 'Parvez',
    'Mamun', 'Junaid', 'Rayhan',
    # learners (female)
    'Fatema', 'Nusrat', 'Sadia', 'Jannat', 'Ayesha', 'Tasnim', 'Farhana',
    'Priya', 'Riya', 'Sumaiya', 'Lamia', 'Mahfuza', 'Shamima', 'Nadia',
    'Rubina', 'Shimu', 'Keya', 'Anika', 'Maliha', 'Ishrat', 'Sabrina',
    'Tanisha', 'Mim', 'Orpa', 'Ritu',
    # instructors
    'Ashik', 'Biplob', 'Emon', 'Hridoy', 'Shakil', 'Shanta', 'Brishti',
    'Puspa', 'Nabila', 'Roksana',
    # admins
    'Kamrul', 'Rokeya', 'Shamsul',
]
LAST_NAMES = [
    'Uddin', 'Ahmed', 'Rahman', 'Khan', 'Islam', 'Hossain', 'Chowdhury',
    'Hasan', 'Ali', 'Begum', 'Khatun', 'Sultana', 'Akter', 'Das', 'Roy',
    'Mia', 'Sarkar', 'Talukder', 'Bhuiyan', 'Molla', 'Sheikh', 'Mahmud',
    'Ferdous', 'Karim', 'Alam', 'Haque', 'Siddique', 'Parvin', 'Rani',
    'Chakraborty',
]

LEARNER_BIOS = [
    '{name} is a second-year CSE student in Dhaka, learning {interest} to build a career in software.',
    'University student from Chattogram. Interested in {interest} and practising a little every day.',
    'Final-year student preparing for job interviews. Currently focused on {interest}.',
    'Self-taught learner from Khulna who enjoys {interest} and building small projects.',
    'College student in Sylhet. Learning {interest} to support freelance work.',
    'Recent graduate from Rajshahi, brushing up on {interest} before applying for jobs.',
]
LEARNER_INTERESTS = [
    'Python programming', 'data analysis', 'web design', 'digital marketing',
    'spoken English', 'mathematics', 'machine learning', 'graphic design',
]
INSTRUCTOR_TITLES = [
    'Senior Lecturer, Computer Science',
    'Assistant Professor, Data Science',
    'Lecturer, Business Administration',
    'Senior Instructor, Design',
    'Associate Professor, Mathematics',
    'Lecturer, English Language',
    'Senior Lecturer, Software Engineering',
    'Assistant Professor, Statistics',
    'Instructor, Digital Marketing',
    'Lecturer, Programming',
]
INSTRUCTOR_EXPERTISE = [
    'Python, Web Development, Databases',
    'Machine Learning, Statistics, Python',
    'Marketing, Management, Communication',
    'UI Design, Figma, Typography',
    'Algebra, Calculus, Statistics',
    'English Grammar, Academic Writing',
    'Java, Software Architecture',
    'Probability, Data Analysis, R',
    'SEO, Social Media, E-commerce',
    'C Programming, Data Structures',
]
INSTRUCTOR_BIOS = [
    '{name} has taught {subject} for {years} years and enjoys helping beginners take their first steps.',
    'Former software engineer turned teacher. {name} focuses on practical, project-based learning in {subject}.',
    '{name} teaches {subject} at a private university in Dhaka and writes short, clear lessons for busy learners.',
]
ADMIN_TITLES = [
    'Platform Administrator',
    'System Administrator',
    'Support Administrator',
]
ADMIN_EXPERTISE = [
    'Platform administration, User support',
    'System administration, Security, Backups',
    'User support, Content moderation',
]
ADMIN_BIOS = [
    '{name} keeps the Venus Learning platform running smoothly and helps learners and instructors with account issues.',
    '{name} looks after the platform, reviews reported content and makes sure courses stay available for everyone.',
    '{name} supports learners and instructors day to day and helps new users get started on the platform.',
]

# (title, category, short topic, description)
COURSE_POOL = [
    ('Python Foundations', 'Programming', 'Python', 'Start with the building blocks of clear, practical Python programs.'),
    ('JavaScript for the Web', 'Programming', 'JavaScript', 'Learn the language of the browser and build interactive web pages.'),
    ('Java Programming Basics', 'Programming', 'Java', 'A gentle start to Java, from variables and loops to small programs.'),
    ('C Programming Essentials', 'Programming', 'C', 'Learn the fundamentals of C and how programs talk to the computer.'),
    ('Web Development with HTML and CSS', 'Programming', 'HTML and CSS', 'Build real web pages from scratch with HTML structure and CSS styling.'),
    ('Data Structures in Python', 'Programming', 'data structures', 'Understand lists, stacks, queues and trees, and when to use each one.'),
    ('Introduction to Data Analysis', 'Data Science', 'data analysis', 'Turn raw tables into answers with spreadsheets and Python.'),
    ('Machine Learning Basics', 'Data Science', 'machine learning', 'A friendly first look at how machines learn from data.'),
    ('Statistics for Data Science', 'Data Science', 'statistics', 'The statistics you actually need to read data and test ideas.'),
    ('Data Visualisation with Python', 'Data Science', 'data visualisation', 'Make charts that explain your data clearly to anyone.'),
    ('SQL for Data Analysis', 'Data Science', 'SQL', 'Ask questions of real databases and get answers with SQL.'),
    ('Deep Learning Foundations', 'Data Science', 'deep learning', 'An approachable introduction to neural networks and how they learn.'),
    ('UI Design Fundamentals', 'Design', 'UI design', 'Learn the decisions behind interfaces that feel easy to use.'),
    ('Graphic Design Basics', 'Design', 'graphic design', 'Colour, type and layout: the foundations of clear visual design.'),
    ('User Experience Research', 'Design', 'UX research', 'Learn how to watch real users and find what confuses them.'),
    ('Figma for Beginners', 'Design', 'Figma', 'Design screens and prototypes in Figma, step by step.'),
    ('Colour and Typography', 'Design', 'colour and typography', 'Choose colours and type that make reading easy and designs memorable.'),
    ('Design Systems in Practice', 'Design', 'design systems', 'Build reusable components so a whole product stays consistent.'),
    ('Entrepreneurship 101', 'Business', 'entrepreneurship', 'Turn an idea into a small business, one testable step at a time.'),
    ('Digital Marketing Basics', 'Business', 'digital marketing', 'Reach customers online with search, social media and email.'),
    ('Business Communication', 'Business', 'business communication', 'Write and speak clearly at work: emails, meetings and presentations.'),
    ('Accounting Fundamentals', 'Business', 'accounting', 'Understand money in a business: income, expenses and simple reports.'),
    ('Project Management Essentials', 'Business', 'project management', 'Plan work, keep a team on track and deliver on time.'),
    ('E-commerce for Beginners', 'Business', 'e-commerce', 'Set up a small online shop and make your first sales.'),
    ('English Grammar in Use', 'Language', 'English grammar', 'The grammar rules that matter most, practised with real sentences.'),
    ('Spoken English for Beginners', 'Language', 'spoken English', 'Speak English with confidence in everyday situations.'),
    ('Academic Writing Skills', 'Language', 'academic writing', 'Write clear essays and reports with proper structure and references.'),
    ('Bangla Literature Essentials', 'Language', 'Bangla literature', 'Explore classic Bangla stories and poems and what makes them last.'),
    ('English for Job Interviews', 'Language', 'job interviews', 'Prepare answers, practise common questions and walk in confident.'),
    ('Creative Writing Workshop', 'Language', 'creative writing', 'Write stories that people want to finish, with feedback each week.'),
    ('Algebra Foundations', 'Mathematics', 'algebra', 'Master equations and expressions, the language of mathematics.'),
    ('Calculus for Beginners', 'Mathematics', 'calculus', 'Derivatives and integrals explained with pictures and real examples.'),
    ('Probability and Statistics', 'Mathematics', 'probability', 'Understand chance, risk and data with worked examples.'),
    ('Discrete Mathematics', 'Mathematics', 'discrete mathematics', 'Logic, sets and graphs: the maths behind computer science.'),
    ('Linear Algebra Essentials', 'Mathematics', 'linear algebra', 'Vectors and matrices, and how they power graphics and data science.'),
    ('Geometry in Practice', 'Mathematics', 'geometry', 'Shapes, angles and measurement, with problems from everyday life.'),
]

CATEGORY_CONTENT = {
    'Programming': {
        'outcomes': ['Write clear, working programs from scratch', 'Break a problem into small, testable pieces', 'Find and fix errors with a systematic approach'],
        'doc': 'This lesson introduces {topic}. Read the explanation slowly, then try the small exercise at the end before moving on. If something is unclear, re-read the example and change one thing at a time until the result makes sense.',
    },
    'Data Science': {
        'outcomes': ['Ask a clear question of a dataset', 'Clean and summarise data with simple tools', 'Explain what a result means in plain words'],
        'doc': 'This lesson works with {topic}. Start by looking at a small sample of the data and describing what you see. Then apply the method step by step, checking your result against the example before continuing.',
    },
    'Design': {
        'outcomes': ['Judge a design by how easy it is to use', 'Apply colour, type and spacing with intent', 'Give and use design feedback constructively'],
        'doc': 'This lesson explores {topic}. Look at the two examples and note what feels different about them. Good design is mostly about removing confusion, so practise explaining your choices in one short sentence.',
    },
    'Business': {
        'outcomes': ['Explain a business idea in one clear paragraph', 'Plan a small test before spending money', 'Read a simple budget and spot problems early'],
        'doc': 'This lesson covers {topic}. Think of a small business you know and follow the worked example with it in mind. At the end, write down one thing you would test first and why.',
    },
    'Language': {
        'outcomes': ['Use the new language in real sentences', 'Notice and correct your most common mistakes', 'Read and listen a little every day'],
        'doc': 'This lesson practises {topic}. Read each example aloud, then write two sentences of your own using the same pattern. Short daily practice beats one long session, so come back tomorrow and repeat it.',
    },
    'Mathematics': {
        'outcomes': ['Solve problems step by step without skipping', 'Check an answer before trusting it', 'Explain a method to someone else in plain words'],
        'doc': 'This lesson works through {topic}. Follow the worked example with a pen in hand and copy each step. Then try the practice problem on your own; if you get stuck, find the first step where your work differs from the example.',
    },
}

CATEGORY_QUESTIONS = {
    'Programming': [
        ('Which of the following is the best first step when a program does not behave as expected?',
         'Read the error message and reproduce the problem in the smallest possible case',
         'Delete the whole file and start again',
         'Change random lines until it works',
         'Ask someone else to fix it', 'a'),
        ('What does a variable do in a program?',
         'It stores a value under a name so the program can use it later',
         'It makes the program run faster',
         'It connects the program to the internet',
         'It prints text on the screen', 'a'),
        ('Why do programmers break a big task into small functions?',
         'Small pieces are easier to test, reuse and understand',
         'It makes the program use more memory',
         'Functions are required in every language',
         'It hides the code from other people', 'a'),
    ],
    'Data Science': [
        ('What is the first step before analysing a dataset?',
         'Understand what the data contains and clean obvious errors',
         'Build the most complex model available',
         'Delete every row with a missing value',
         'Publish the results', 'a'),
        ('Why is a training set kept separate from a test set?',
         'To check honestly how a model performs on data it has not seen',
         'To make training slower',
         'Because the test set is always larger',
         'To avoid saving the model', 'a'),
        ('What makes a chart misleading?',
         'Axes or scales that hide how big a difference really is',
         'Using more than one colour',
         'Labelling the axes clearly',
         'Showing the source of the data', 'a'),
    ],
    'Design': [
        ('What makes an interface easier to use?',
         'Clear labels, consistent placement and one obvious next step',
         'As many colours as possible',
         'Hiding all buttons behind menus',
         'Small text everywhere', 'a'),
        ('Why do designers test with real users?',
         'Real users reveal confusion that the designer cannot see themselves',
         'Testing is only for decoration',
         'Users always agree with the designer',
         'Testing replaces the need for a design', 'a'),
        ('What is the purpose of a design system?',
         'Reusable pieces that keep a whole product consistent',
         'Making every screen look different',
         'Removing the need for designers',
         'Hiding the brand', 'a'),
    ],
    'Business': [
        ('What is a simple way to check whether a business idea is worth pursuing?',
         'Talk to potential customers and test a small version first',
         'Spend all the budget on advertising at once',
         'Keep the idea secret forever',
         'Copy a competitor exactly', 'a'),
        ('Why does a budget matter for a small business?',
         'It shows what money is coming in and going out, so problems appear early',
         'Budgets are only for large companies',
         'A budget removes the need for customers',
         'Budgets guarantee profit', 'a'),
        ('What should a business do first when sales fall?',
         'Find out why: ask customers and check the numbers',
         'Cut all prices in half immediately',
         'Stop talking to customers',
         'Blame the season', 'a'),
    ],
    'Language': [
        ('What is the most effective way to remember new words?',
         'Use them in real sentences, repeatedly, over several days',
         'Read the dictionary once',
         'Memorise the alphabet',
         'Avoid speaking until perfect', 'a'),
        ('Why is listening practice important when learning a language?',
         'It trains your ear for real pronunciation and natural speed',
         'Listening is only for advanced learners',
         'Reading alone is enough',
         'Listening replaces grammar', 'a'),
        ('What helps most when you forget a word while speaking?',
         'Describe it with other words you know and keep going',
         'Stop talking completely',
         'Switch to your first language for the whole conversation',
         'Pretend you never needed the word', 'a'),
    ],
    'Mathematics': [
        ('What does it mean to solve for x in an equation?',
         'Find the value of x that makes both sides equal',
         'Delete x from the equation',
         'Guess any number',
         'Multiply both sides by zero', 'a'),
        ('Why do mathematicians check their answer after solving?',
         'A quick check catches small mistakes before they spread',
         'Checking is never needed',
         'Answers are always wrong',
         'Checking changes the answer', 'a'),
        ('What is the first step with a word problem?',
         'Work out what is being asked and what information you have',
         'Write down a random formula',
         'Skip to the answer',
         'Ignore the words and use the numbers only', 'a'),
    ],
}
GENERAL_QUESTION = (
    'What is the best way to keep learning after finishing a lesson?',
    'Practise the idea with a small exercise the same day',
    'Move on and never look back',
    'Only watch more videos',
    'Wait a month before practising', 'a',
)

REVIEW_SENTENCES = [
    'Very clear lessons, I finally understood the basics.',
    'Well organised course, the examples really helped.',
    'Great teacher, explains everything step by step.',
    'I enjoyed this course and learned a lot from it.',
    'Good pace and practical exercises throughout.',
]

UNIT_TITLES = ['Getting started', 'Going deeper']
UNIT_LESSON_TITLES = [
    ['Welcome and course overview', 'The core ideas', 'Your first practice task'],
    ['Going deeper', 'Common mistakes and how to avoid them', 'Mini project and review'],
]


def avatar_url(full_name, style):
    # Deterministic DiceBear avatar: same name always gets the same picture.
    return f'https://api.dicebear.com/9.x/{style}/svg?seed={quote(full_name)}'


def person_spec(index, role):
    first = FIRST_NAMES[index]
    last = LAST_NAMES[index % len(LAST_NAMES)]
    return {
        'full_name': f'{first} {last}',
        'email': f'{first}.{last}@example.com'.lower(),
        'role': role,
    }


class Command(BaseCommand):
    help = 'Create realistic local test data: 50 learners, 10 instructors, 3 admins, courses, enrollments, certificates and Deep Focus badges.'

    def add_arguments(self, parser):
        parser.add_argument('--reset-passwords', action='store_true', help='Restore the shared password only for existing flagged test accounts.')

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG or not settings.ENABLE_DEMO_ACCOUNTS:
            raise CommandError('Test data seeding is disabled unless both DEBUG=true and ENABLE_DEMO_ACCOUNTS=true. It never runs automatically.')

        rng = Random(SEED)
        try:
            validate_password(PASSWORD)
        except Exception as error:
            raise CommandError(str(error))

        specs = []
        for index in range(50):
            specs.append(person_spec(index, 'learner'))
        for index in range(50, 60):
            specs.append(person_spec(index, 'instructor'))
        for index in range(60, 63):
            specs.append(person_spec(index, 'admin'))

        # Preflight every address before changing anything: real accounts are never claimed.
        existing = {}
        for spec in specs:
            user = User.objects.select_for_update().filter(email=spec['email']).first()
            if user:
                if not user.is_demo_account:
                    raise CommandError(f"Refusing to claim existing unflagged account {spec['email']}.")
                if user.role != spec['role']:
                    raise CommandError(f"Refusing test account {spec['email']}: expected role {spec['role']}, found {user.role}.")
                existing[spec['email']] = user

        users = {}
        for position, spec in enumerate(specs):
            user = existing.get(spec['email'])
            name = spec['full_name']
            if spec['role'] == 'learner':
                bio = rng.choice(LEARNER_BIOS).format(name=name, interest=rng.choice(LEARNER_INTERESTS))
                profile = {
                    'title': '', 'expertise': '',
                    'profile_pic': avatar_url(name, 'avataaars'),
                    'points': rng.randint(0, 3000), 'current_streak': rng.randint(0, 20),
                }
            elif spec['role'] == 'instructor':
                slot = position - 50
                subject = COURSE_POOL[slot * 3][2]
                bio = rng.choice(INSTRUCTOR_BIOS).format(name=name, subject=subject, years=rng.randint(3, 12))
                profile = {
                    'title': INSTRUCTOR_TITLES[slot], 'expertise': INSTRUCTOR_EXPERTISE[slot],
                    'profile_pic': avatar_url(name, 'personas'),
                    'points': rng.randint(500, 5000), 'current_streak': rng.randint(0, 30),
                }
            else:
                slot = position - 60
                bio = rng.choice(ADMIN_BIOS).format(name=name)
                profile = {
                    'title': ADMIN_TITLES[slot], 'expertise': ADMIN_EXPERTISE[slot],
                    'profile_pic': avatar_url(name, 'personas'),
                    'points': rng.randint(1000, 5000), 'current_streak': rng.randint(0, 30),
                }
            if user is None:
                user = User(
                    email=spec['email'], full_name=name, role=spec['role'],
                    is_demo_account=True, is_verified=True, is_active=True,
                    instructor_approved=(spec['role'] == 'instructor'),
                    is_staff=(spec['role'] == 'admin'),
                    is_superuser=(spec['role'] == 'admin'),
                    bio=bio, **profile)
                user.set_password(PASSWORD)
                user.save()
            else:
                changed = []
                required = {
                    'is_demo_account': True, 'is_verified': True, 'is_active': True,
                    'instructor_approved': spec['role'] == 'instructor',
                    'is_staff': spec['role'] == 'admin',
                    'is_superuser': spec['role'] == 'admin',
                    'bio': bio, **profile,
                }
                for field, value in required.items():
                    if getattr(user, field) != value:
                        setattr(user, field, value)
                        changed.append(field)
                if options['reset_passwords']:
                    user.set_password(PASSWORD)
                    changed.append('password')
                if changed:
                    user.save(update_fields=changed)
            users[spec['email']] = user

        learners = [users[spec['email']] for spec in specs if spec['role'] == 'learner']
        instructors = [users[spec['email']] for spec in specs if spec['role'] == 'instructor']

        # Courses: each instructor gets 1-3, chosen at random.
        courses = []
        for instructor in instructors:
            count = rng.randint(1, 3)
            for title, category, topic, description in rng.sample(COURSE_POOL, count):
                content = CATEGORY_CONTENT[category]
                course, _ = Course.objects.get_or_create(
                    title=title, instructor=instructor,
                    defaults={
                        'description': description, 'category': category,
                        'level': rng.choice(['beginner', 'intermediate', 'advanced']),
                        'status': 'approved', 'is_free': True,
                        'outcomes': content['outcomes'],
                        'target_audience': f'Beginners and intermediate learners interested in {topic}.',
                    })
                courses.append(course)
        courses.sort(key=lambda course: course.id)

        # 2 units x 3 lessons per course, mixing video and document lessons.
        all_lessons = {}
        for course in courses:
            topic = next(spec[2] for spec in COURSE_POOL if spec[0] == course.title)
            category = course.category
            lessons = []
            for unit_position, unit_title in enumerate(UNIT_TITLES):
                unit, _ = Unit.objects.get_or_create(course=course, title=unit_title, defaults={'position': unit_position})
                for lesson_position, lesson_title in enumerate(UNIT_LESSON_TITLES[unit_position]):
                    is_video = rng.random() < 0.65
                    duration = rng.randint(300, 900) if is_video else rng.randint(180, 420)
                    lesson, _ = Lesson.objects.get_or_create(
                        unit=unit, title=lesson_title,
                        defaults={
                            'description': f'{lesson_title} — {course.title}.',
                            'content': '' if is_video else CATEGORY_CONTENT[category]['doc'].format(topic=topic),
                            'lesson_type': 'video' if is_video else 'document',
                            'provider': 'youtube' if is_video else 'youtube',
                            'provider_video_id': VIDEO_ID if is_video else '',
                            'duration_seconds': duration,
                            'position': lesson_position,
                            'is_preview': unit_position == 0 and lesson_position == 0,
                        })
                    lessons.append(lesson)
            all_lessons[course.id] = lessons

            # One quiz per course: 2 questions from its category + 1 general.
            quiz, _ = Quiz.objects.get_or_create(
                course=course, title=f'{course.title} — Knowledge check',
                defaults={'owner': course.instructor, 'pass_percentage': 70})
            questions = list(CATEGORY_QUESTIONS[category][:2]) + [GENERAL_QUESTION]
            for question_text, a, b, c, d, correct in questions:
                Question.objects.get_or_create(
                    quiz=quiz, question=question_text,
                    defaults={'option_a': a, 'option_b': b, 'option_c': c, 'option_d': d, 'correct_answer': correct})

        # Enrollments: each learner in 1-4 randomly chosen courses.
        now = timezone.now()
        enrollments_by_learner = {}
        for learner in learners:
            chosen = rng.sample(courses, rng.randint(1, 4))
            learner_enrollments = []
            for course in chosen:
                enrollment, _ = Enrollment.objects.get_or_create(learner=learner, course=course)
                complete = rng.random() < 0.35
                for lesson in all_lessons[course.id]:
                    progress, _ = LessonProgress.objects.get_or_create(enrollment=enrollment, lesson=lesson)
                    if complete:
                        progress.progress = 100
                        progress.watch_percentage = 100
                        progress.watched_seconds = lesson.duration_seconds or 0
                        progress.resume_position_seconds = lesson.duration_seconds or 0
                        if progress.completed_at is None:
                            progress.completed_at = now
                    else:
                        pct = rng.randint(20, 90)
                        progress.progress = pct
                        progress.watch_percentage = pct
                        progress.watched_seconds = int((lesson.duration_seconds or 0) * pct / 100)
                        progress.resume_position_seconds = progress.watched_seconds
                        progress.completed_at = None
                    progress.duration_seconds = lesson.duration_seconds
                    progress.save()
                if complete and enrollment.completed_at is None:
                    enrollment.completed_at = now
                    enrollment.save(update_fields=['completed_at'])
                learner_enrollments.append(enrollment)
            enrollments_by_learner[learner.id] = learner_enrollments

        # Certificates: exactly 15 learners, one each for a course they completed.
        # If the random draw left fewer than 15 learners with a completed
        # course, finish one of their enrollments first.
        completed_learners = [
            learner for learner in learners
            if any(e.completed_at is not None for e in enrollments_by_learner[learner.id])
        ]
        for learner in learners:
            if len(completed_learners) >= 15:
                break
            if learner in completed_learners:
                continue
            enrollment = enrollments_by_learner[learner.id][0]
            for lesson in all_lessons[enrollment.course_id]:
                LessonProgress.objects.filter(enrollment=enrollment, lesson=lesson).update(
                    progress=100, watch_percentage=100,
                    watched_seconds=lesson.duration_seconds or 0,
                    resume_position_seconds=lesson.duration_seconds or 0,
                    duration_seconds=lesson.duration_seconds, completed_at=now)
            enrollment.completed_at = now
            enrollment.save(update_fields=['completed_at'])
            completed_learners.append(learner)
        completed_learners.sort(key=lambda user: user.email)
        certificate_learners = completed_learners[:15]
        for learner in certificate_learners:
            done = next(e for e in enrollments_by_learner[learner.id] if e.completed_at is not None)
            Certificate.objects.get_or_create(learner=learner, course=done.course)

        # Deep Focus badges: completed FocusSession rows. 12 learners earn the
        # 30-minute badge (8 x 1, 3 x 2, 1 x 3 sessions) and 8 learners earn
        # the 60-minute badge (6 x 1, 2 x 2), plus 4 interrupted sessions.
        focus_learners = rng.sample(learners, 24)
        thirty_group, sixty_group = focus_learners[:12], focus_learners[12:20]
        interrupted_learners = focus_learners[20:24]
        thirty_counts = [1] * 8 + [2] * 3 + [3]
        sixty_counts = [1] * 6 + [2] * 2

        def add_focus_sessions(learner, target, wanted, status):
            existing = FocusSession.objects.filter(
                learner=learner, target_minutes=target, status=status).count()
            for _ in range(max(0, wanted - existing)):
                started = now - timedelta(days=rng.randint(1, 30), hours=rng.randint(0, 23))
                focused = target * 60 if status == 'completed' else rng.randint(300, target * 60 - 60)
                session = FocusSession.objects.create(
                    learner=learner, target_minutes=target,
                    focused_seconds=focused, status=status,
                    ended_at=started + timedelta(seconds=focused))
                # started_at is auto_now_add, so backdate it after creation.
                FocusSession.objects.filter(pk=session.pk).update(started_at=started)

        for learner, count in zip(thirty_group, thirty_counts):
            add_focus_sessions(learner, 30, count, 'completed')
        for learner, count in zip(sixty_group, sixty_counts):
            add_focus_sessions(learner, 60, count, 'completed')
        for index, learner in enumerate(interrupted_learners):
            add_focus_sessions(learner, 30 if index % 2 == 0 else 60, 1, 'interrupted')

        # Ratings: 2-4 per course, from enrolled learners, 4 or 5 stars.
        for course in courses:
            raters = [e.learner for e in Enrollment.objects.filter(course=course).order_by('learner__email')]
            if len(raters) < 2:
                raters = rng.sample(learners, 2)
            wanted = rng.randint(2, 4)
            existing = Rating.objects.filter(course=course).count()
            for learner in raters[:max(0, wanted - existing)]:
                if Rating.objects.filter(course=course, learner=learner).exists():
                    continue
                Rating.objects.create(
                    course=course, learner=learner,
                    rating=rng.choice([4, 5]), review=rng.choice(REVIEW_SENTENCES))

        learner_list = [u for u in learners]
        instructor_list = [u for u in instructors]
        admin_list = [users[spec['email']] for spec in specs if spec['role'] == 'admin']
        course_list = Course.objects.filter(instructor__in=instructor_list)
        enrollment_list = Enrollment.objects.filter(learner__in=learner_list)
        certificate_list = Certificate.objects.filter(learner__in=learner_list)
        focus_list = FocusSession.objects.filter(learner__in=learner_list)
        rating_list = Rating.objects.filter(course__in=course_list)
        self.stdout.write(self.style.SUCCESS(
            'Test data ready: '
            f"{User.objects.filter(is_demo_account=True).count()} demo users "
            f'({len(learner_list)} learners, {len(instructor_list)} instructors, {len(admin_list)} admins), '
            f'{course_list.count()} courses, {enrollment_list.count()} enrollments, '
            f'{certificate_list.count()} certificates, {focus_list.count()} focus sessions '
            f"({focus_list.filter(target_minutes=30, status='completed').count()}x 30-min completed, "
            f"{focus_list.filter(target_minutes=60, status='completed').count()}x 60-min completed, "
            f"{focus_list.filter(status='interrupted').count()} interrupted), "
            f'{rating_list.count()} ratings. '
            f'All accounts share the password {PASSWORD}. '
            'Test data is enabled only while DEBUG=true and ENABLE_DEMO_ACCOUNTS=true.'))
