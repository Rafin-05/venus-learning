"""Admin-managed course categories (migration 0016).

Course.category stays a plain name field — these tests pin that: the
dropdown list is public, only staff/admin can add a category, and a
course created with a category name keeps working exactly as before.
"""
from .models import Category
from .test_acceptance import AcceptanceBase


class CategoryTests(AcceptanceBase):
    def test_list_is_public_and_seeded_with_the_existing_categories(self):
        r = self.client.get('/api/categories/')
        self.assertEqual(r.status_code, 200, r.data)
        names = [row['name'] for row in (r.data if isinstance(r.data, list) else r.data.get('results', []))]
        for expected in ('Programming', 'Data Science', 'Design', 'Business', 'Language', 'Mathematics'):
            self.assertIn(expected, names)

    def test_admin_can_create_a_category_and_instructors_cannot(self):
        r = self.post('/api/categories/', {'name': 'Photography'}, user=self.admin)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(Category.objects.filter(name='Photography').exists())
        self.assertEqual(self.post('/api/categories/', {'name': 'Cooking'}, user=self.instructor).status_code, 403)
        self.assertEqual(self.post('/api/categories/', {'name': 'Cooking'}, user=self.learner).status_code, 403)

    def test_duplicate_and_blank_category_names_are_rejected(self):
        self.assertEqual(self.post('/api/categories/', {'name': 'Programming'}, user=self.admin).status_code, 400)
        self.assertEqual(self.post('/api/categories/', {'name': '   '}, user=self.admin).status_code, 400)

    def test_admin_can_delete_a_category_without_touching_courses(self):
        course = self.course_for(self.instructor, 'Keeps its category', 'pending')
        course.category = 'Design'
        course.save(update_fields=['category'])
        category = Category.objects.get(name='Design')
        self.auth(self.admin)
        r = self.client.delete(f'/api/categories/{category.id}/')
        self.assertEqual(r.status_code, 204, r.data)
        course.refresh_from_db()
        self.assertEqual(course.category, 'Design')

    def test_course_creation_still_accepts_a_category_name(self):
        body = {
            'title': 'Intro to Photography', 'description': 'A structured course.',
            'category': 'Photography', 'level': 'beginner',
            'is_free': True, 'price': '0.00',
        }
        r = self.post('/api/courses/', body, user=self.instructor)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['category'], 'Photography')
        self.assertEqual(r.data['status'], 'pending')
