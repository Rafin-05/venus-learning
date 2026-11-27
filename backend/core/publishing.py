from django.db.models import Q


def published_courses(prefix=''):
    """Only courses whose publisher's account is current are public."""
    teacher = prefix + 'instructor__'
    account = Q(**{teacher+'is_active': True, teacher+'is_verified': True})
    role = Q(**{teacher+'role': 'instructor'}) | Q(**{teacher+'role': 'admin'}) | Q(**{teacher+'is_staff': True})
    return Q(**{prefix+'status': 'approved'}) & account & role


def course_is_published(course):
    teacher = course.instructor
    return bool(course.status == 'approved' and teacher.is_active and teacher.is_verified and (teacher.is_staff or teacher.role in ('admin', 'instructor')))


def account_is_verified(user):
    return bool(user and user.is_authenticated and user.is_active and user.is_verified)
