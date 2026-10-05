import re
import unittest
from unittest.mock import patch
from datetime import date
from app import create_app
from tracker.extensions import db
from tracker.models import User, Expense, Income, Budget


class TrackerTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'SECRET_KEY': 'test-only-key', 'WTF_CSRF_ENABLED': False})
        self.client = self.app.test_client()
        with self.app.app_context():
            for username, admin in [('member', False), ('other', False), ('admin', True)]:
                user = User(full_name=username.title(), username=username, email=username + '@example.com', is_admin=admin)
                user.set_password('correct-password')
                db.session.add(user)
            db.session.commit()

    def login(self, username='member'):
        return self.client.post('/login', data={'email': username + '@example.com', 'password': 'correct-password'})

    def transaction(self, **changes):
        values = {'title': 'Lunch', 'amount': '25.10', 'category': 'Food', 'source': 'Salary', 'payment_method': 'Cash', 'date': date.today().isoformat(), 'description': 'With friends'}
        values.update(changes)
        return values

    def test_authentication_and_identity(self):
        self.assertEqual(self.client.get('/dashboard').status_code, 302)
        result = self.client.post('/register', data={'full_name': 'New Member', 'username': 'newuser', 'email': 'new@example.com', 'password': 'secure-password', 'confirm': 'secure-password'})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(self.client.post('/login', data={'email': 'member@example.com', 'password': 'wrong'}, follow_redirects=True).status_code, 200)
        self.login()
        self.assertEqual(self.client.get('/admin/').status_code, 403)
        self.assertEqual(self.client.post('/profile', data={'action': 'profile', 'full_name': 'Updated Name', 'username': 'member', 'email': 'member@example.com'}).status_code, 302)
        self.assertEqual(self.client.post('/profile', data={'action': 'password', 'current_password': 'correct-password', 'password': 'new-password123', 'confirm': 'new-password123'}).status_code, 302)
        self.assertEqual(self.client.post('/logout').status_code, 302)
        self.assertEqual(self.client.get('/dashboard').status_code, 302)
        self.assertEqual(self.client.post('/login', data={'email': 'member@example.com', 'password': 'new-password123'}).status_code, 302)

    def test_transaction_crud_filters_pagination_and_ownership(self):
        self.login()
        self.assertEqual(self.client.post('/expenses/add', data=self.transaction()).status_code, 302)
        self.assertEqual(self.client.post('/income/add', data=self.transaction(title='Salary', amount='1000')).status_code, 302)
        combined = self.client.get('/transactions').data
        self.assertIn(b'<strong>Lunch</strong>', combined)
        self.assertIn(b'<strong>Salary</strong>', combined)
        self.assertEqual(self.client.post('/expenses/1/edit', data=self.transaction(title='Dinner', amount='35')).status_code, 302)
        self.assertEqual(self.client.post('/income/1/edit', data=self.transaction(title='Updated salary', amount='1200')).status_code, 302)
        for path in ['/expenses/', '/income/', '/expenses/1', '/income/1', '/transactions', '/dashboard', '/reports', '/profile']:
            self.assertEqual(self.client.get(path).status_code, 200, path)
        result = self.client.get('/transactions?q=Dinner&type=expense&category=Food&payment_method=Cash&min=30&max=40')
        self.assertIn(b'Dinner', result.data)
        self.assertNotIn(b'<strong>Salary</strong>', result.data)
        for i in range(11):
            self.client.post('/expenses/add', data=self.transaction(title='Purchase ' + str(i)))
        self.assertIn(b'Page 2 of 2', self.client.get('/expenses/?page=2').data)
        self.client.post('/logout')
        self.login('other')
        for path in ['/expenses/1', '/expenses/1/edit', '/income/1']:
            self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.post('/expenses/1/delete').status_code, 403)
        self.assertNotIn(b'Dinner', self.client.get('/transactions').data)
        self.client.post('/logout')
        self.login()
        self.assertEqual(self.client.post('/expenses/1/delete').status_code, 302)
        self.assertEqual(self.client.get('/expenses/1').status_code, 404)
        self.assertEqual(self.client.post('/income/1/delete').status_code, 302)

    def test_validation_and_budgets(self):
        self.login()
        for amount in ['-10', '0', 'invalid', 'NaN', 'Infinity']:
            self.assertEqual(self.client.post('/expenses/add', data=self.transaction(amount=amount)).status_code, 200)
        self.assertEqual(self.client.post('/expenses/add', data=self.transaction(title='')).status_code, 200)
        data = {'category': 'Food', 'monthly_limit': '100', 'month': date.today().month, 'year': date.today().year}
        self.assertEqual(self.client.post('/budgets/', data=data).status_code, 302)
        self.client.post('/expenses/add', data=self.transaction(amount='80'))
        self.assertIn(b'Near limit', self.client.get('/budgets/').data)
        self.client.post('/expenses/add', data=self.transaction(amount='30'))
        self.assertIn(b'Exceeded', self.client.get('/budgets/').data)
        self.assertEqual(self.client.post('/budgets/', data=data).status_code, 200)
        data['monthly_limit'] = '200'
        self.assertEqual(self.client.post('/budgets/1/edit', data=data).status_code, 302)
        self.assertEqual(self.client.post('/budgets/1/delete').status_code, 302)
        self.assertEqual(self.client.get('/transactions?start=invalid').status_code, 400)
        self.assertEqual(self.client.get('/transactions?min=NaN').status_code, 400)
        self.assertEqual(self.client.get('/reports?period=custom&start=2026-02-01&end=2026-01-01').status_code, 400)
        self.assertEqual(self.client.get('/reports?period=last').status_code, 200)
        self.assertEqual(self.client.get('/reports?period=year').status_code, 200)

    def test_duplicate_identity_validation(self):
        data = {'full_name': 'Duplicate', 'username': 'member', 'email': 'fresh@example.com', 'password': 'secure-password', 'confirm': 'secure-password'}
        self.assertEqual(self.client.post('/register', data=data).status_code, 200)
        data.update(username='freshuser', email='member@example.com')
        self.assertEqual(self.client.post('/register', data=data).status_code, 200)
        data.update(email='invalid-email')
        self.assertEqual(self.client.post('/register', data=data).status_code, 200)
        with self.app.app_context():
            self.assertEqual(User.query.count(), 3)

    def test_admin_creation_script(self):
        import create_admin
        with patch.object(create_admin, 'create_app', return_value=self.app), patch('builtins.input', side_effect=['New Admin', 'newadmin', 'newadmin@example.com']), patch.object(create_admin, 'getpass', side_effect=['secure-password', 'secure-password']), patch('builtins.print'):
            create_admin.main()
        with self.app.app_context():
            user = User.query.filter_by(username='newadmin').one()
            self.assertTrue(user.is_admin)
            self.assertTrue(user.check_password('secure-password'))
            self.assertNotEqual(user.password_hash, 'secure-password')

    def test_admin_actions_and_deactivation(self):
        self.login('admin')
        for path in ['/admin/', '/admin/users', '/admin/users/1', '/admin/transactions', '/admin/analytics', '/admin/settings']:
            self.assertEqual(self.client.get(path).status_code, 200, path)
        self.client.post('/admin/users/3/delete')
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(User, 3))
        self.client.post('/admin/users/2/toggle-admin')
        self.client.post('/admin/users/1/toggle-active')
        with self.app.app_context():
            self.assertTrue(db.session.get(User, 2).is_admin)
            self.assertFalse(db.session.get(User, 1).active)
        self.client.post('/logout')
        self.login()
        self.assertEqual(self.client.get('/dashboard').status_code, 302)
        self.login('admin')
        self.client.post('/admin/users/2/delete')
        with self.app.app_context():
            self.assertIsNone(db.session.get(User, 2))

    def test_csrf_is_required(self):
        self.app.config['WTF_CSRF_ENABLED'] = True
        self.assertEqual(self.client.post('/login', data={'email': 'member@example.com', 'password': 'correct-password'}).status_code, 400)
        token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', self.client.get('/login').text).group(1)
        self.assertEqual(self.client.post('/login', data={'csrf_token': token, 'email': 'member@example.com', 'password': 'correct-password'}).status_code, 302)
        self.assertEqual(self.client.post('/logout').status_code, 400)


if __name__ == '__main__':
    unittest.main()
