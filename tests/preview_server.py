"""Run an ephemeral, in-memory UI preview; never writes to the real database."""
import secrets
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from tracker.extensions import db
from tracker.models import User, Expense, Income, Budget
from waitress import serve

app = create_app({'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'SECRET_KEY': secrets.token_hex(32)})
with app.app_context():
    password = secrets.token_urlsafe(18)
    user = User(full_name='Alex Morgan', username='preview', email='preview@example.com', is_admin=True)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    today = date.today()
    for offset in range(6):
        year = today.year - (1 if today.month - offset <= 0 else 0)
        month = (today.month - offset - 1) % 12 + 1
        day = date(year, month, 1)
        db.session.add(Income(user_id=user.id, title='Monthly salary', source='Salary', amount=4200 + offset * 100, income_date=day, description='Preview data'))
        for title, category, amount in [('Weekly groceries', 'Food', 240), ('Morning commute', 'Transport', 85), ('Apartment rent', 'Bills', 1250), ('Weekend coffee', 'Food', 18), ('New headphones', 'Shopping', 149)]:
            db.session.add(Expense(user_id=user.id, title=title, category=category, amount=amount + offset * 7, expense_date=day, payment_method='Debit Card', description='Preview data'))
    db.session.add(Budget(user_id=user.id, category='Food', monthly_limit=350, month=today.month, year=today.year))
    db.session.commit()
    print('Preview login: preview@example.com / ' + password, flush=True)
serve(app, host='127.0.0.1', port=5001)
