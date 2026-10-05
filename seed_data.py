"""Create public demo accounts and realistic data in the configured database."""
import argparse
import calendar
import hashlib
import json
import os
from datetime import date, datetime
from decimal import Decimal

from app import create_app
from tracker.extensions import db
from tracker.models import User, Expense, Income, Budget, DemoSeed

SEED_KEY = 'smart-expense-demo-v1'
ACCOUNTS = [
    {'full_name': 'Admin User', 'username': 'admin', 'email': 'admin@example.com', 'password': 'Admin123!', 'is_admin': True},
    {'full_name': 'John Doe', 'username': 'johndoe', 'email': 'john@example.com', 'password': 'User123!', 'is_admin': False},
    {'full_name': 'Sarah Khan', 'username': 'sarah', 'email': 'sarah@example.com', 'password': 'User123!', 'is_admin': False},
]
EXPENSES = [
    ('Grocery Shopping', 'Food', '165.00'),
    ('Coffee', 'Food', '14.00'),
    ('Restaurant Dinner', 'Food', '61.00'),
    ('Fuel', 'Transport', '95.00'),
    ('Taxi Ride', 'Transport', '55.00'),
    ('Clothing', 'Shopping', '175.00'),
    ('New Headphones', 'Shopping', '115.00'),
    ('Movie Ticket', 'Entertainment', '24.00'),
    ('Streaming Subscription', 'Entertainment', '12.00'),
    ('Concert Tickets', 'Entertainment', '132.00'),
    ('Gym Membership', 'Health', '49.00'),
    ('Pharmacy Purchase', 'Health', '31.00'),
    ('Online Course', 'Education', '140.00'),
    ('Books', 'Education', '60.00'),
    ('Internet Bill', 'Bills', '65.00'),
    ('Electricity Bill', 'Bills', '110.00'),
    ('Mobile Recharge', 'Bills', '25.00'),
    ('Weekend Trip', 'Travel', '235.00'),
    ('Hotel Booking', 'Travel', '190.00'),
    ('Home Supplies', 'Other', '35.00'),
]
LIMITS = {'Food': 500, 'Transport': 200, 'Shopping': 300, 'Entertainment': 150, 'Health': 200, 'Education': 250}
PAYMENTS = ['Cash', 'Debit Card', 'Credit Card', 'Bank Transfer', 'E-Wallet']
MODELS = {'users': User, 'expenses': Expense, 'incomes': Income, 'budgets': Budget}


def month_ago(today, offset):
    """Calendar-month arithmetic that also works across year boundaries."""
    index = today.year * 12 + today.month - 1 - offset
    year, month = divmod(index, 12)
    return date(year, month + 1, 1)


def transaction_day(month, requested_day, today):
    last_day = today.day if (month.year, month.month) == (today.year, today.month) else calendar.monthrange(month.year, month.month)[1]
    return month.replace(day=min(requested_day, last_day))


def fingerprint(record):
    """Detect changed/replaced rows before deleting any seed-owned data."""
    values = {column.name: str(getattr(record, column.name)) for column in record.__table__.columns}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode('utf-8')).hexdigest()


def find_collisions():
    usernames = [account['username'] for account in ACCOUNTS]
    emails = [account['email'] for account in ACCOUNTS]
    return User.query.filter(db.or_(db.func.lower(User.username).in_(usernames), db.func.lower(User.email).in_(emails))).all()


def checked_records(manifest):
    """Preflight the entire reset, so collisions or edits cannot cause partial deletion."""
    records = {kind: [] for kind in MODELS}
    for kind, entries in manifest.items():
        for entry in entries:
            record = db.session.get(MODELS[kind], entry['id'])
            if record is None:
                if kind == 'users':
                    raise ValueError('A demo account was removed. Reset refused to protect unrelated accounts.')
                continue
            if fingerprint(record) != entry['fingerprint']:
                raise ValueError('A seed-owned {} record was edited or replaced. Reset refused; no data was deleted.'.format(kind))
            records[kind].append(record)
    return records


def seed_demo(reset=False, today=None):
    """Run within an app context. Return counts, or None when already seeded."""
    today = today or date.today()
    state = db.session.get(DemoSeed, SEED_KEY)
    if state and not reset:
        print('Demo data already exists. Skipping seed process.')
        return None
    if not state and find_collisions():
        raise ValueError('A demo username or email already exists without a seed ownership manifest. No accounts were modified. Use a separate demo database.')

    try:
        generated = {kind: [] for kind in MODELS}
        if state:
            records = checked_records(state.manifest)
            users = records['users']
            # Retain accounts and any manually added data; delete only manifest-owned rows.
            for kind in ('expenses', 'incomes', 'budgets'):
                for record in records[kind]:
                    db.session.delete(record)
            db.session.flush()
        else:
            users = []
            for account, offset in zip(ACCOUNTS, (5, 2, 0)):
                user = User(**{key: value for key, value in account.items() if key != 'password'})
                user.created_at = datetime.combine(month_ago(today, offset), datetime.min.time())
                user.set_password(account['password'])
                db.session.add(user)
                users.append(user)
            db.session.flush()
        generated['users'] = users

        for person, user in enumerate(users):
            for offset in range(6):
                month = month_ago(today, offset)
                factor = Decimal('1') + Decimal(person) * Decimal('0.02') + Decimal(offset) * Decimal('0.035')
                for index, (title, category, amount) in enumerate(EXPENSES):
                    day = transaction_day(month, 1 + (index * 3 + person) % 28, today)
                    expense = Expense(user_id=user.id, title=title, description='Demo: {} for {}.'.format(title.lower(), day.strftime('%B %Y')), amount=(Decimal(amount) * factor).quantize(Decimal('0.01')), category=category, payment_method=PAYMENTS[(index + offset + person) % len(PAYMENTS)], expense_date=day, created_at=datetime.combine(day, datetime.min.time()))
                    db.session.add(expense)
                    generated['expenses'].append(expense)

                payments = [('Monthly Salary', 'Salary', 3600 + person * 350, 1), ('Freelance Web Project' if offset % 2 == 0 else 'Consulting Payment', 'Freelancing', 650 + offset * 70, 14), ('Investment Return', 'Investment', 85 + person * 20 + offset * 5, 25)]
                if offset in (1, 4):
                    payments.append(('Performance Bonus', 'Bonus', 450, 20))
                if offset == 2:
                    payments.append(('Online Store Sales', 'Business', 380, 18))
                if offset == 0:
                    payments.append(('Birthday Gift', 'Gift', 100, 3))
                if offset == 5:
                    payments.append(('Cashback Reward', 'Other', 30, 27))
                for title, source, amount, scheduled_day in payments:
                    day = transaction_day(month, scheduled_day, today)
                    payment = Income(user_id=user.id, title=title, source=source, amount=Decimal(amount), income_date=day, description='Demo: {} received in {}.'.format(source.lower(), day.strftime('%B %Y')), created_at=datetime.combine(day, datetime.min.time()))
                    db.session.add(payment)
                    generated['incomes'].append(payment)

                if offset < 3:
                    for category, limit in LIMITS.items():
                        budget = Budget(user_id=user.id, category=category, monthly_limit=Decimal(limit), month=month.month, year=month.year)
                        db.session.add(budget)
                        generated['budgets'].append(budget)
        db.session.flush()
        # Read back normalized decimals/dates so later fingerprints match the persisted values.
        for records in generated.values():
            for record in records:
                db.session.refresh(record)
        manifest = {kind: [{'id': record.id, 'fingerprint': fingerprint(record)} for record in records] for kind, records in generated.items()}
        if state:
            state.manifest = manifest
        else:
            db.session.add(DemoSeed(key=SEED_KEY, manifest=manifest))
        db.session.commit()
        return {kind: len(records) for kind, records in generated.items()}
    except Exception:
        db.session.rollback()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reset', action='store_true', help='Replace unchanged seed-owned transactions and budgets; preserve other data.')
    args = parser.parse_args()
    if os.environ.get('APP_ENV', '').lower() == 'production':
        parser.exit(1, 'Demo seeding is disabled when APP_ENV=production. Use a local/demo database.\n')
    with create_app().app_context():
        try:
            counts = seed_demo(reset=args.reset)
        except Exception as error:
            parser.exit(1, 'Demo seeding failed: {}\nNo seed changes were committed.\n'.format(error))
    if counts is None:
        return
    print('\nSmart Expense Tracker Demo Data Created Successfully\n')
    print('Created: 1 Admin account, 2 Demo users, {expenses} expenses, {incomes} income records, {budgets} monthly budgets'.format(**counts))
    print('\nDemo Login (local/demo use only):')
    for account in ACCOUNTS:
        print('{}: {} / {}'.format(account['full_name'], account['email'], account['password']))
    print('\nThese credentials are public. Remove/change these accounts before production deployment.')


if __name__ == '__main__':
    main()
