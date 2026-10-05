import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from sqlalchemy import text

from app import create_app
from seed_data import seed_demo, month_ago, ACCOUNTS
from tracker.extensions import db
from tracker.models import User, Expense, Income, Budget, DemoSeed, CATEGORIES, SOURCES
from tracker.services import metrics


class DemoSeedTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'SECRET_KEY': 'seed-test-key', 'WTF_CSRF_ENABLED': False})
        self.context = self.app.app_context()
        self.context.push()
        self.today = date.today()

    def tearDown(self):
        db.session.remove()
        self.context.pop()

    def seed(self, **kwargs):
        with patch('builtins.print'):
            return seed_demo(**kwargs)

    def counts(self):
        return tuple(model.query.count() for model in (User, Expense, Income, Budget, DemoSeed))

    def test_complete_data_relationships_charts_and_dashboards(self):
        counts = self.seed()
        self.assertEqual(counts, {'users': 3, 'expenses': 360, 'incomes': 69, 'budgets': 54})
        self.assertEqual({x.category for x in Expense.query.all()}, set(CATEGORIES))
        self.assertEqual({x.source for x in Income.query.all()}, set(SOURCES))
        self.assertEqual(len({(x.expense_date.year, x.expense_date.month) for x in Expense.query.all()}), 6)
        self.assertTrue(all(x.expense_date <= self.today for x in Expense.query.all()))
        self.assertTrue(all(x.income_date <= self.today for x in Income.query.all()))
        self.assertEqual(db.session.execute(text('PRAGMA foreign_key_check')).all(), [])
        for account in ACCOUNTS:
            user = User.query.filter_by(email=account['email']).one()
            self.assertTrue(user.check_password(account['password']))
            self.assertNotEqual(user.password_hash, account['password'])
            self.assertEqual(user.is_admin, account['is_admin'])
            self.assertEqual(len(user.expenses), 120)
            self.assertEqual(len(user.incomes), 23)
            self.assertEqual(len(user.budgets), 18)
            totals = metrics(user.id)
            self.assertGreater(totals['earned'], 0)
            self.assertGreater(totals['spent'], 0)
            self.assertNotEqual(totals['balance'], 0)
            self.assertTrue(all(value > 0 for value in totals['chart']['income']))
            self.assertTrue(all(value > 0 for value in totals['chart']['expenses']))
            self.assertGreater(len(totals['chart']['categories']), 1)
            client = self.app.test_client()
            self.assertEqual(client.post('/login', data={'email': account['email'], 'password': account['password']}).status_code, 302)
            for path in ('/dashboard', '/transactions', '/budgets/', '/reports'):
                response = client.get(path)
                self.assertEqual(response.status_code, 200, path)
            self.assertIn(b'Grocery Shopping', client.get('/transactions?q=Grocery').data)
            if user.is_admin:
                for path in ('/admin/', '/admin/analytics', '/admin/transactions'):
                    self.assertEqual(client.get(path).status_code, 200, path)
                self.assertIn(b'REGISTERED USERS', client.get('/admin/').data)
        john = User.query.filter_by(username='johndoe').one()
        ratios = {}
        for budget in john.budgets:
            if (budget.year, budget.month) == (self.today.year, self.today.month):
                spent = sum(x.amount for x in john.expenses if x.category == budget.category and (x.expense_date.year, x.expense_date.month) == (budget.year, budget.month))
                ratios[budget.category] = spent / budget.monthly_limit
        self.assertLess(ratios['Food'], Decimal('0.5'))
        self.assertTrue(Decimal('0.75') <= ratios['Transport'] < Decimal('0.8'))
        self.assertTrue(Decimal('0.95') <= ratios['Shopping'] < 1)
        self.assertGreater(ratios['Entertainment'], 1)

    def test_idempotent_and_reset_preserves_unseeded_data(self):
        self.seed()
        original_counts = self.counts()
        self.assertIsNone(self.seed())
        self.assertEqual(self.counts(), original_counts)
        john = User.query.filter_by(username='johndoe').one()
        real_user = User(full_name='Real User', username='realuser', email='real@example.com')
        real_user.set_password('private-password')
        db.session.add(real_user)
        db.session.flush()
        for user, title in ((real_user, 'Real expense'), (john, 'Manually added expense')):
            db.session.add(Expense(user_id=user.id, title=title, amount=Decimal('12.34'), category='Food', payment_method='Cash', expense_date=self.today))
        db.session.add(Budget(user_id=john.id, category='Travel', monthly_limit=Decimal('999'), month=self.today.month, year=self.today.year))
        db.session.commit()
        real_id = real_user.id
        self.seed(reset=True)
        self.assertEqual(self.counts(), (4, 362, 69, 55, 1))
        self.assertIsNotNone(db.session.get(User, real_id))
        self.assertEqual(Expense.query.filter(Expense.title.in_(['Real expense', 'Manually added expense'])).count(), 2)
        self.assertIsNone(self.seed())

    def test_unowned_identity_collision_is_never_promoted_or_deleted(self):
        user = User(full_name='Real Admin Name', username='admin', email='real@example.com')
        user.set_password('private-password')
        db.session.add(user)
        db.session.commit()
        for reset in (False, True):
            with self.assertRaises(ValueError):
                self.seed(reset=reset)
            self.assertEqual(self.counts(), (1, 0, 0, 0, 0))
            self.assertFalse(user.is_admin)
            self.assertTrue(user.check_password('private-password'))

    def test_edited_seed_record_refuses_reset_atomically(self):
        self.seed()
        expense = Expense.query.first()
        expense.description = 'Edited by user'
        db.session.commit()
        counts = self.counts()
        with self.assertRaises(ValueError):
            self.seed(reset=True)
        self.assertEqual(self.counts(), counts)
        self.assertEqual(db.session.get(Expense, expense.id).description, 'Edited by user')

    def test_year_boundary_and_first_of_month(self):
        today = date(2027, 1, 1)
        self.assertEqual(month_ago(today, 5), date(2026, 8, 1))
        self.seed(today=today)
        self.assertTrue(all(x.expense_date <= today for x in Expense.query.all()))
        self.assertTrue(all(x.income_date <= today for x in Income.query.all()))
        self.assertEqual(len({(x.expense_date.year, x.expense_date.month) for x in Expense.query.all()}), 6)


if __name__ == '__main__':
    unittest.main()
