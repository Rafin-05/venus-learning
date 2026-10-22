from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .models import User,Course,Quiz,Question,Problem,Enrollment
class ApiTests(TestCase):
    def setUp(self):
        self.client=APIClient(); self.u=User.objects.create_user('learner@test.local','SafePass123!',full_name='Learner',is_verified=True)
        self.i=User.objects.create_user('inst@test.local','SafePass123!',full_name='Instructor',role='instructor',is_verified=True,instructor_approved=True)
        self.c=Course.objects.create(title='Course',description='Plain text',instructor=self.i,status='approved')
        Enrollment.objects.create(learner=self.u,course=self.c)
        self.q=Quiz.objects.create(course=self.c,title='Quiz',owner=self.i)
        Question.objects.create(quiz=self.q,question='Q',option_a='yes',option_b='no',correct_answer='a')
    def login(self):
        self.assertEqual(self.client.post('/api/auth/login/',{'email':'learner@test.local','password':'SafePass123!'},format='json').status_code,200)
    def test_login_and_me(self):
        self.login(); self.assertEqual(self.client.get('/api/auth/me/').status_code,200)
    def test_bruteforce_lockout(self):
        for _ in range(5): self.client.post('/api/auth/login/',{'email':'learner@test.local','password':'wrong'},format='json')
        self.assertEqual(self.client.post('/api/auth/login/',{'email':'learner@test.local','password':'SafePass123!'},format='json').status_code,429)
    def test_quiz_is_graded_server_side(self):
        self.login(); r=self.client.post(f'/api/quizzes/{self.q.id}/submit/',{'answers':{str(self.q.questions.first().id):'a'}},format='json'); self.assertEqual(r.data['score'],1); self.assertTrue(r.data['passed'])
    @override_settings(CODING_RUNNER_URL='')
    def test_code_never_runs_without_runner(self):
        self.login(); p=Problem.objects.create(title='P',statement='S',owner=self.i); self.assertEqual(self.client.post(f'/api/problems/{p.id}/submit/',{'code':'print(1)','language':'python'},format='json').status_code,503)
