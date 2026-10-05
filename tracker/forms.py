from datetime import date
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, DecimalField, SelectField, DateField, TextAreaField, IntegerField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange, Regexp
from tracker.models import CATEGORIES, PAYMENTS, SOURCES


class IdentityForm(FlaskForm):
    full_name = StringField('Full name', validators=[DataRequired(), Length(max=100)])
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=40), Regexp(r'^[a-zA-Z0-9_]+$', message='Use letters, numbers, and underscores.')])
    email = StringField('Email address', validators=[DataRequired(), Email(), Length(max=120)])


class RegisterForm(IdentityForm):
    password = PasswordField('Password', validators=[DataRequired(), Length(min=10, max=128)])
    confirm = PasswordField('Confirm password', validators=[DataRequired(), EqualTo('password')])


class LoginForm(FlaskForm):
    email = StringField('Email address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(max=128)])


class PasswordForm(FlaskForm):
    current_password = PasswordField('Current password', validators=[DataRequired()])
    password = PasswordField('New password', validators=[DataRequired(), Length(min=10, max=128)])
    confirm = PasswordField('Confirm new password', validators=[DataRequired(), EqualTo('password')])


class TransactionForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=120)])
    amount = DecimalField('Amount ($)', places=2, validators=[DataRequired(), NumberRange(min=0.01, max=999999999999.99)])
    date = DateField('Date', default=date.today, validators=[DataRequired()])
    category = SelectField('Category', choices=CATEGORIES)
    source = SelectField('Source', choices=SOURCES)
    payment_method = SelectField('Payment method', choices=PAYMENTS)
    description = TextAreaField('Description', validators=[Length(max=2000)])


class BudgetForm(FlaskForm):
    category = SelectField('Category', choices=CATEGORIES)
    monthly_limit = DecimalField('Monthly limit ($)', places=2, validators=[DataRequired(), NumberRange(min=0.01, max=999999999999.99)])
    month = SelectField('Month', coerce=int, choices=[(i, date(2000, i, 1).strftime('%B')) for i in range(1, 13)], default=lambda: date.today().month)
    year = IntegerField('Year', default=lambda: date.today().year, validators=[DataRequired(), NumberRange(min=2000, max=2100)])
