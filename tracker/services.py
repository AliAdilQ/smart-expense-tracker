from datetime import date
from decimal import Decimal, InvalidOperation
from flask import request, abort
from sqlalchemy import or_, select, union_all, literal
from tracker.extensions import db
from tracker.models import Expense, Income, User


def date_arg(name):
    value = request.args.get(name)
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        abort(400)


def transactions(user_id=None, kind=None):
    statements = []
    for model, row_kind, day, category, payment in (
        (Expense, 'expense', Expense.expense_date, Expense.category, Expense.payment_method),
        (Income, 'income', Income.income_date, Income.source, literal('—')),
    ):
        query = select(model.id, model.user_id, model.title, model.description, model.amount, day.label('date'), category.label('category'), payment.label('payment_method'), literal(row_kind).label('type'), User.full_name.label('owner')).join(User)
        if user_id is not None:
            query = query.where(model.user_id == user_id)
        statements.append(query)
    combined = union_all(*statements).subquery()
    query = select(combined)
    args = request.args
    if kind:
        query = query.where(combined.c.type == kind)
    if args.get('q'):
        term = '%' + args['q'] + '%'
        query = query.where(or_(combined.c.title.ilike(term), combined.c.description.ilike(term), combined.c.category.ilike(term)))
    for key in ('type', 'category', 'payment_method', 'user_id'):
        if args.get(key):
            query = query.where(combined.c[key] == args[key])
    start, end = date_arg('start'), date_arg('end')
    if start and end and start > end:
        abort(400)
    if start:
        query = query.where(combined.c.date >= start)
    if end:
        query = query.where(combined.c.date <= end)
    for key, operation in [('min', 'min'), ('max', 'max')]:
        if args.get(key):
            try:
                value = Decimal(args[key])
                if not value.is_finite() or value < 0:
                    raise ValueError()
            except (InvalidOperation, ValueError):
                abort(400)
            query = query.where(combined.c.amount >= value if operation == 'min' else combined.c.amount <= value)
    return query.order_by(combined.c.date.desc(), combined.c.id.desc())


def paginate_transactions(user_id=None, kind=None):
    query = transactions(user_id, kind)
    page = max(request.args.get('page', 1, type=int), 1)
    total = db.session.scalar(select(db.func.count()).select_from(query.subquery()))
    rows = db.session.execute(query.limit(10).offset((page - 1) * 10)).mappings().all()
    return rows, {'page': page, 'pages': max(1, (total + 9) // 10), 'total': total}


def metrics(user_id=None, start=None, end=None):
    ex = Expense.query
    inc = Income.query
    if user_id is not None:
        ex, inc = ex.filter_by(user_id=user_id), inc.filter_by(user_id=user_id)
    if start:
        ex, inc = ex.filter(Expense.expense_date >= start), inc.filter(Income.income_date >= start)
    if end:
        ex, inc = ex.filter(Expense.expense_date <= end), inc.filter(Income.income_date <= end)
    expenses, incomes = ex.all(), inc.all()
    spent = sum((x.amount for x in expenses), Decimal(0))
    earned = sum((x.amount for x in incomes), Decimal(0))
    categories = {}
    category_counts = {}
    for item in expenses:
        categories[item.category] = categories.get(item.category, 0) + float(item.amount)
        category_counts[item.category] = category_counts.get(item.category, 0) + 1
    today = date.today()
    months = [date(today.year - (1 if today.month - offset <= 0 else 0), (today.month - offset - 1) % 12 + 1, 1) for offset in reversed(range(6))]
    chart = {'labels': [d.strftime('%b %Y') for d in months], 'expenses': [], 'income': [], 'categories': list(categories), 'values': list(categories.values()), 'category_counts': list(category_counts.values())}
    for month in months:
        chart['expenses'].append(float(sum((x.amount for x in expenses if (x.expense_date.year, x.expense_date.month) == (month.year, month.month)), Decimal(0))))
        chart['income'].append(float(sum((x.amount for x in incomes if (x.income_date.year, x.income_date.month) == (month.year, month.month)), Decimal(0))))
    return {'spent': spent, 'earned': earned, 'balance': earned - spent, 'count': len(expenses) + len(incomes), 'top': max(categories, key=categories.get) if categories else 'No spending yet', 'chart': chart}
