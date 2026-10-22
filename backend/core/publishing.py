from django.db.models import Q


def published_courses(prefix=''):
    """An approval flag alone must not bypass the publisher's current account state."""
    teacher = prefix + 'instructor__'
    account = Q(**{teacher+'is_active': True, teacher+'is_verified': True})
    role = Q(**{teacher+'role': 'instructor', teacher+'instructor_approved': True}) | Q(**{teacher+'role': 'admin'}) | Q(**{teacher+'is_staff': True})
    return Q(**{prefix+'status': 'approved'}) & account & role


def course_is_published(course):
    teacher = course.instructor
    return bool(course.status == 'approved' and teacher.is_active and teacher.is_verified and (teacher.is_staff or teacher.role == 'admin' or (teacher.role == 'instructor' and teacher.instructor_approved)))


def account_is_verified(user):
    return bool(user and user.is_authenticated and user.is_active and user.is_verified and (user.role != 'instructor' or user.instructor_approved))
