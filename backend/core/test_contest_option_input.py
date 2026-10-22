from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Contest, User


class ContestOptionInputTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            'contest-admin@example.test', 'SafePass123!', full_name='Admin',
            role='admin', is_staff=True, is_superuser=True, is_verified=True,
            instructor_approved=True,
        )
        self.learner = User.objects.create_user(
            'contest-learner@example.test', 'SafePass123!', full_name='Learner',
            role='learner', is_verified=True,
        )
        self.client.force_authenticate(user=self.admin)

    def payload(self, **question_changes):
        question = {
            'id': 'q1', 'question': 'Which answer?', 'option_a': 'A',
            'option_b': 'B', 'correct_answer': 'a',
        }
        question.update(question_changes)
        now = timezone.now()
        return {
            'title': 'Options',
            'starts_at': (now - timedelta(hours=1)).isoformat(),
            'ends_at': (now + timedelta(hours=1)).isoformat(),
            'questions': [question],
        }

    def test_create_rejects_non_string_and_oversized_values_for_every_option(self):
        for option in ('option_a', 'option_b', 'option_c', 'option_d'):
            for value_name, value in (
                ('null', None), ('object', {}), ('list', []),
                ('number', 1), ('boolean', True),
            ):
                with self.subTest(option=option, value=value_name):
                    response = self.client.post('/api/contests/', self.payload(**{option: value}), format='json')
                    self.assertEqual(response.status_code, 400)
            with self.subTest(option=option, value='oversized'):
                response = self.client.post('/api/contests/', self.payload(**{option: 'x' * 1001}), format='json')
                self.assertEqual(response.status_code, 400)

    def test_update_rejects_non_string_and_oversized_values_for_every_option(self):
        contest = Contest.objects.create(
            owner=self.admin, title='Existing', starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(hours=1), questions=self.payload()['questions'],
        )
        for option in ('option_a', 'option_b', 'option_c', 'option_d'):
            for value_name, value in (
                ('null', None), ('object', {}), ('list', []),
                ('number', 1), ('boolean', True), ('oversized', 'x' * 1001),
            ):
                with self.subTest(option=option, value=value_name):
                    question = dict(self.payload()['questions'][0], **{option: value})
                    response = self.client.patch(
                        f'/api/contests/{contest.id}/', {'questions': [question]}, format='json'
                    )
                    self.assertEqual(response.status_code, 400)

    def test_bound_values_are_accepted_and_learner_read_keeps_strings_and_hides_answers(self):
        response = self.client.post(
            '/api/contests/', self.payload(
                option_a='a' * 1000, option_b='b' * 1000,
                option_c='', option_d='d' * 1000,
            ), format='json',
        )
        self.assertEqual(response.status_code, 201)
        contest = Contest.objects.get(pk=response.data['id'])
        self.client.force_authenticate(user=self.learner)
        response = self.client.get(f'/api/contests/{contest.id}/')
        self.assertEqual(response.status_code, 200)
        question = response.data['questions'][0]
        self.assertNotIn('correct_answer', question)
        self.assertTrue(all(isinstance(question[option], str) for option in ('option_a', 'option_b', 'option_c', 'option_d')))

    def test_required_options_and_selected_option_must_be_nonblank(self):
        for option in ('option_a', 'option_b'):
            with self.subTest(option=option):
                response = self.client.post('/api/contests/', self.payload(**{option: ' \t '}), format='json')
                self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/contests/', self.payload(option_c=' \t ', correct_answer='c'), format='json')
        self.assertEqual(response.status_code, 400)
