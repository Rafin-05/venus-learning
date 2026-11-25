from rest_framework.permissions import BasePermission

class Verified(BasePermission):
    # Email verification is disabled: an active account is enough.
    # Instructors still need administrator approval. The class name is
    # kept so every existing viewset keeps working unchanged.
    message = 'An active account is required; instructors also need approval.'
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and (user.role != 'instructor' or user.instructor_approved))

class EditorOnly(Verified):
    message = 'Only an approved instructor or administrator can edit learning content.'
    def has_permission(self, request, view):
        return super().has_permission(request, view) and bool(request.user.is_staff or request.user.role in ('admin', 'instructor'))

class StaffOnly(Verified):
    message = 'Administrator access is required.'
    def has_permission(self, request, view):
        return super().has_permission(request, view) and bool(request.user.is_staff or request.user.role == 'admin')

class IsAdmin(StaffOnly):
    pass

class IsInstructor(EditorOnly):
    pass

class IsLearner(Verified):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role == 'learner'
