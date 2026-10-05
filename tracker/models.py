from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from tracker.extensions import db

CATEGORIES = ['Food', 'Transport', 'Shopping', 'Bills', 'Entertainment', 'Health', 'Education', 'Travel', 'Other']
PAYMENTS = ['Cash', 'Debit Card', 'Credit Card', 'Bank Transfer', 'E-Wallet', 'Other']
SOURCES = ['Salary', 'Freelancing', 'Business', 'Investment', 'Gift', 'Bonus', 'Other']


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(40), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    expenses = db.relationship('Expense', backref='user', cascade='all, delete-orphan')
    incomes = db.relationship('Income', backref='user', cascade='all, delete-orphan')
    budgets = db.relationship('Budget', backref='user', cascade='all, delete-orphan')

    @property
    def is_active(self):
        return self.active

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default='')
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    category = db.Column(db.String(40), nullable=False)
    payment_method = db.Column(db.String(40), nullable=False)
    expense_date = db.Column(db.Date, default=date.today, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    source = db.Column(db.String(40), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    income_date = db.Column(db.Date, default=date.today, nullable=False, index=True)
    description = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(40), nullable=False)
    monthly_limit = db.Column(db.Numeric(14, 2), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'category', 'month', 'year'),)


class DemoSeed(db.Model):
    """Ownership manifest used to safely reset explicitly seeded records."""
    key = db.Column(db.String(40), primary_key=True)
    manifest = db.Column(db.JSON, nullable=False)
