"""Course-creation workflow tests (PDF: course wizard, curriculum,
YouTube validation, resources, video progress, assignments, admin review).

Live classes are intentionally not built here: there is no live-class
model, endpoint, or UI in this feature.
"""
from django.utils import timezone

from .models import Assignment, AssignmentSubmission, CourseResource, CourseReview, LessonProgress
from .test_acceptance import AcceptanceBase
from .video import extract_youtube_id


class YoutubeIdTests(AcceptanceBase):
    def test_extracts_watch_short_embed_and_bare_ids(self):
        self.assertEqual(extract_youtube_id('https://www.youtube.com/watch?v=dQw4w9WgXcQ'), 'dQw4w9WgXcQ')
        self.assertEqual(extract_youtube_id('https://youtu.be/dQw4w9WgXcQ'), 'dQw4w9WgXcQ')
        self.assertEqual(extract_youtube_id('https://www.youtube.com/embed/dQw4w9WgXcQ'), 'dQw4w9WgXcQ')
        self.assertEqual(extract_youtube_id('https://www.youtube.com/shorts/dQw4w9WgXcQ'), 'dQw4w9WgXcQ')
        self.assertEqual(extract_youtube_id('dQw4w9WgXcQ'), 'dQw4w9WgXcQ')
        self.assertEqual(extract_youtube_id('https://www.youtube.com/watch?v=short'), '')
        self.assertEqual(extract_youtube_id('https://video.test/a'), '')
        self.assertEqual(extract_youtube_id(''), '')


class CourseWizardTests(AcceptanceBase):
    def test_create_with_wizard_fields_and_youtube_promo(self):
        body = {
            'title': 'Intro to Python', 'subtitle': 'From zero to scripts',
            'description': 'A structured course.', 'category': 'Programming',
            'subcategory': 'Python', 'level': 'beginner', 'language': 'en',
            'outcomes': ['Write a Python program', 'Use lists and loops'],
            'target_audience': 'Complete beginners', 'prerequisites': 'A computer',
            'is_free': True, 'price': '0.00', 'enrollment_open': True,
            'completion_threshold': 90,
            'promo_video_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        }
        r = self.post('/api/courses/', body, user=self.instructor)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['subtitle'], 'From zero to scripts')
        self.assertEqual(r.data['promo_provider_video_id'], 'dQw4w9WgXcQ')
        self.assertEqual(r.data['outcomes'], ['Write a Python program', 'Use lists and loops'])
        self.assertEqual(r.data['status'], 'pending')

    def test_free_course_cannot_carry_a_price_and_bad_youtube_is_rejected(self):
        r = self.post('/api/courses/', {'title': 'X', 'description': 'x', 'is_free': True, 'price': '10.00'}, user=self.instructor)
        self.assertEqual(r.status_code, 400)
        r = self.post('/api/courses/', {'title': 'X', 'description': 'x', 'promo_video_url': 'https://www.youtube.com/watch?v=short'}, user=self.instructor)
        self.assertEqual(r.status_code, 400)
        r = self.post('/api/courses/', {'title': 'X', 'description': 'x', 'is_free': False, 'price': '0.00'}, user=self.instructor)
        self.assertEqual(r.status_code, 400)

    def test_lesson_video_url_extracts_provider_id_and_bad_youtube_is_rejected(self):
        r = self.post('/api/lessons/', {'unit': self.unit.id, 'title': 'Watch', 'lesson_type': 'video', 'video_url': 'https://youtu.be/dQw4w9WgXcQ', 'duration_seconds': 600, 'is_preview': True}, user=self.instructor)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['provider'], 'youtube')
        self.assertEqual(r.data['provider_video_id'], 'dQw4w9WgXcQ')
        self.assertTrue(r.data['is_preview'])
        r = self.post('/api/lessons/', {'unit': self.unit.id, 'title': 'Bad', 'lesson_type': 'video', 'video_url': 'https://www.youtube.com/watch?v=short'}, user=self.instructor)
        self.assertEqual(r.status_code, 400)

    def test_submit_review_requires_curriculum_and_records_audit(self):
        empty = self.course_for(self.instructor, 'Empty', 'pending')
        r = self.post(f'/api/courses/{empty.id}/submit-review/', {}, user=self.instructor)
        self.assertEqual(r.status_code, 400)
        r = self.post(f'/api/courses/{self.course.id}/submit-review/', {'notes': 'Ready'}, user=self.instructor)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['decision'], 'submitted')
        self.assertEqual(CourseReview.objects.filter(course=self.course, decision='submitted').count(), 1)

    def test_admin_approve_and_request_changes_are_audited(self):
        r = self.post(f'/api/courses/{self.pending.id}/approve/', {'notes': 'Looks good'}, user=self.admin)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['course']['status'], 'approved')
        self.assertEqual(CourseReview.objects.filter(course=self.pending, decision='approved').count(), 1)
        r = self.post(f'/api/courses/{self.pending.id}/request-changes/', {}, user=self.admin)
        self.assertEqual(r.status_code, 400)
        r = self.post(f'/api/courses/{self.pending.id}/request-changes/', {'notes': 'Fix the first lesson title.'}, user=self.admin)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['course']['status'], 'pending')
        self.assertEqual(CourseReview.objects.filter(course=self.pending, decision='changes_requested').count(), 1)
        r = self.post(f'/api/courses/{self.pending.id}/approve/', {}, user=self.instructor)
        self.assertIn(r.status_code, (401, 403, 404, 405))


class VideoProgressTests(AcceptanceBase):
    def test_watched_seconds_drive_completion_at_threshold(self):
        # 90% of a 100-second video, with the course threshold at 90.
        r = self.patch(f'/api/lessons/{self.video.id}/progress/', {'watched_seconds': 90, 'duration_seconds': 100, 'resume_position_seconds': 90}, user=self.learner)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['watch_percentage'], 90)
        self.assertEqual(r.data['progress'], 100)
        row = LessonProgress.objects.get(enrollment=self.enrollment, lesson=self.video)
        self.assertEqual(row.resume_position_seconds, 90)
        self.assertIsNotNone(row.completed_at)

    def test_partial_watch_is_not_completion_and_replay_is_not_double_counted(self):
        r = self.patch(f'/api/lessons/{self.video.id}/progress/', {'watched_seconds': 40, 'duration_seconds': 100, 'resume_position_seconds': 40}, user=self.learner)
        self.assertEqual(r.data['progress'], 40)
        r = self.patch(f'/api/lessons/{self.video.id}/progress/', {'watched_seconds': 30, 'duration_seconds': 100, 'resume_position_seconds': 70}, user=self.learner)
        self.assertEqual(r.data['watched_seconds'], 40)
        self.assertEqual(r.data['progress'], 40)

    def test_playback_needs_enrollment_but_preview_is_open_on_a_published_course(self):
        preview = self.video
        preview.is_preview = True
        preview.save(update_fields=['is_preview'])
        outsider = self.user('outsider@example.test', is_verified=True)
        self.auth(outsider)
        r = self.client.get(f'/api/lessons/{preview.id}/playback/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['provider_video_id'], '')
        # A non-preview lesson stays closed to outsiders.
        preview.is_preview = False
        preview.save(update_fields=['is_preview'])
        r = self.client.get(f'/api/lessons/{self.video.id}/playback/')
        self.assertIn(r.status_code, (401, 403, 404))


class ResourceAndAssignmentTests(AcceptanceBase):
    def test_resource_requires_enrollment_for_learners(self):
        resource = CourseResource.objects.create(course=self.course, title='Guide', external_url='https://example.test/guide.pdf')
        outsider = self.user('outsider@example.test', is_verified=True)
        self.auth(outsider)
        r = self.client.get(f'/api/resources/?course={self.course.id}')
        self.assertEqual(r.status_code, 200)
        rows = r.data if isinstance(r.data, list) else r.data.get('results', [])
        self.assertTrue(all(row['id'] != resource.id for row in rows))
        self.auth(self.learner)
        r = self.client.get(f'/api/resources/?course={self.course.id}')
        rows = r.data if isinstance(r.data, list) else r.data.get('results', [])
        self.assertTrue(any(row['id'] == resource.id for row in rows))
        r = self.client.get(f'/api/resources/{resource.id}/download/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('guide.pdf', r.data['download_url'])

    def test_assignment_submit_and_grade_keeps_history(self):
        assignment = Assignment.objects.create(course=self.course, title='Homework 1', instructions='Write a program.', max_points=10, accepted_types='text', is_required=True)
        r = self.post('/api/assignment-submissions/', {'assignment': assignment.id, 'text_response': 'My answer.'}, user=self.learner)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['attempt_no'], 1)
        r = self.post('/api/assignment-submissions/', {'assignment': assignment.id, 'text_response': 'Improved answer.'}, user=self.learner)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['attempt_no'], 2)
        self.assertEqual(AssignmentSubmission.objects.filter(assignment=assignment, learner=self.learner).count(), 2)
        submission_id = r.data['id']
        r = self.post(f'/api/assignment-submissions/{submission_id}/grade/', {'score': 9, 'feedback': 'Well done.'}, user=self.instructor)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['status'], 'graded')
        self.assertEqual(r.data['score'], 9)
        r = self.post(f'/api/assignment-submissions/{submission_id}/grade/', {'score': 99, 'feedback': 'Too much.'}, user=self.instructor)
        self.assertEqual(r.status_code, 400)

    def test_quiz_attempt_limit_is_enforced_only_when_set(self):
        self.quiz.attempts_allowed = 1
        self.quiz.save(update_fields=['attempts_allowed'])
        r = self.post(f'/api/quizzes/{self.quiz.id}/submit/', {'answers': {str(self.question.id): 'a'}}, user=self.learner)
        self.assertEqual(r.status_code, 200, r.data)
        r = self.post(f'/api/quizzes/{self.quiz.id}/submit/', {'answers': {str(self.question.id): 'a'}}, user=self.learner)
        self.assertEqual(r.status_code, 409)
