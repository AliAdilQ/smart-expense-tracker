from datetime import date, timedelta
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from tracker.extensions import db
from tracker.models import User, Expense, Income, Budget, CATEGORIES, PAYMENTS, SOURCES
from tracker.forms import RegisterForm, LoginForm, IdentityForm, PasswordForm, TransactionForm, BudgetForm
from tracker.services import metrics, transactions, paginate_transactions, date_arg

auth = Blueprint('auth', __name__)
main = Blueprint('main', __name__)
expenses = Blueprint('expenses', __name__, url_prefix='/expenses')
income = Blueprint('income', __name__, url_prefix='/income')
budgets = Blueprint('budgets', __name__, url_prefix='/budgets')
admin = Blueprint('admin', __name__, url_prefix='/admin')


def save():
    try:
        db.session.commit()
        return True
    except IntegrityError:
        db.session.rollback()
        flash('That username, email, or monthly category budget already exists.', 'danger')
        return False


def identity(user, form):
    user.full_name = form.full_name.data.strip()
    user.username = form.username.data.strip().lower()
    user.email = form.email.data.strip().lower()


@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User()
        identity(user, form)
        user.set_password(form.password.data)
        db.session.add(user)
        if save():
            flash('Registration successful. Sign in to get started.', 'success')
            return redirect(url_for('auth.login'))
    return render_template('register.html', form=form)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.check_password(form.password.data) and user.active:
            login_user(user)
            flash('Welcome back. You’re signed in.', 'success')
            return redirect(url_for('main.dashboard'))
        flash('Invalid email or password, or account is inactive.', 'danger')
    return render_template('login.html', form=form)


@auth.post('/logout')
@login_required
def logout():
    logout_user()
    flash('You have signed out.', 'success')
    return redirect(url_for('main.landing'))


@main.get('/')
def landing():
    return render_template('landing.html')


@main.get('/dashboard')
@login_required
def dashboard():
    today = date.today()
    stats = metrics(current_user.id)
    monthly = metrics(current_user.id, today.replace(day=1), today)
    recent = db.session.execute(transactions(current_user.id).limit(5)).mappings().all()
    return render_template('dashboard.html', stats=stats, monthly=monthly, rows=recent, title='Dashboard', subtitle='A little clarity. A lot more control.')


@main.get('/transactions')
@login_required
def transaction_list():
    return listing('Transactions')


def listing(title, kind=None, platform=False):
    rows, pagination = paginate_transactions(None if platform else current_user.id, kind)
    return render_template('admin/transactions.html' if platform else 'transactions.html', rows=rows, pagination=pagination, title=title, subtitle='Every movement, in one place.', kind=kind, categories=list(dict.fromkeys(CATEGORIES + SOURCES)), payments=PAYMENTS, users=User.query.order_by(User.full_name).all() if platform else [], platform=platform)


def owned(model, record_id):
    item = db.get_or_404(model, record_id)
    if item.user_id != current_user.id:
        abort(403)
    return item


def transaction_form(kind, record_id=None):
    model = Expense if kind == 'expense' else Income
    item = owned(model, record_id) if record_id else None
    form = TransactionForm(obj=item)
    if request.method == 'GET' and item:
        form.date.data = item.expense_date if kind == 'expense' else item.income_date
    if form.validate_on_submit():
        item = item or model(user_id=current_user.id)
        for key in ('title', 'amount', 'description'):
            setattr(item, key, getattr(form, key).data)
        if kind == 'expense':
            item.category, item.payment_method, item.expense_date = form.category.data, form.payment_method.data, form.date.data
        else:
            item.source, item.income_date = form.source.data, form.date.data
        db.session.add(item)
        if save():
            flash('{} {} successfully.'.format(kind.title(), 'updated' if record_id else 'added'), 'success')
            return redirect(url_for(('expenses' if kind == 'expense' else 'income') + '.list_records'))
    return render_template('transaction_form.html', form=form, kind=kind, title=('Edit ' if item else 'Add ') + kind, subtitle='Keep your financial story up to date.')


def transaction_view(kind, record_id):
    item = owned(Expense if kind == 'expense' else Income, record_id)
    return render_template('transaction_detail.html', item=item, kind=kind, title=item.title, subtitle='Transaction details')


def transaction_delete(kind, record_id):
    db.session.delete(owned(Expense if kind == 'expense' else Income, record_id))
    db.session.commit()
    flash(kind.title() + ' deleted.', 'success')
    return redirect(url_for('main.transaction_list'))


for blueprint, kind in [(expenses, 'expense'), (income, 'income')]:
    blueprint.add_url_rule('/', 'list_records', login_required(lambda kind=kind: listing('Expenses' if kind == 'expense' else 'Income', kind)))
    blueprint.add_url_rule('/add', 'add', login_required(lambda kind=kind: transaction_form(kind)), methods=['GET', 'POST'])
    blueprint.add_url_rule('/<int:record_id>/edit', 'edit', login_required(lambda record_id, kind=kind: transaction_form(kind, record_id)), methods=['GET', 'POST'])
    blueprint.add_url_rule('/<int:record_id>', 'view', login_required(lambda record_id, kind=kind: transaction_view(kind, record_id)))
    blueprint.add_url_rule('/<int:record_id>/delete', 'delete', login_required(lambda record_id, kind=kind: transaction_delete(kind, record_id)), methods=['POST'])


@budgets.route('/', methods=['GET', 'POST'])
@login_required
def index():
    form = BudgetForm()
    if form.validate_on_submit():
        item = Budget(user_id=current_user.id, category=form.category.data, monthly_limit=form.monthly_limit.data, month=form.month.data, year=form.year.data)
        db.session.add(item)
        if save():
            flash('Budget created.', 'success')
            return redirect(url_for('budgets.index'))
    items = []
    for budget in Budget.query.filter_by(user_id=current_user.id).order_by(Budget.year.desc(), Budget.month.desc()).all():
        spending = db.session.query(db.func.coalesce(db.func.sum(Expense.amount), 0)).filter(Expense.user_id == current_user.id, Expense.category == budget.category, db.extract('month', Expense.expense_date) == budget.month, db.extract('year', Expense.expense_date) == budget.year).scalar()
        items.append({'budget': budget, 'spent': spending, 'percent': float(spending / budget.monthly_limit * 100)})
    return render_template('budgets.html', form=form, items=items, title='Budgets', subtitle='Give every dollar a little direction.')


@budgets.route('/<int:record_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(record_id):
    item = owned(Budget, record_id)
    form = BudgetForm(obj=item)
    if form.validate_on_submit():
        form.populate_obj(item)
        if save():
            flash('Budget updated.', 'success')
            return redirect(url_for('budgets.index'))
    return render_template('form_page.html', form=form, title='Edit budget', subtitle='Adjust your monthly plan.')


@budgets.post('/<int:record_id>/delete')
@login_required
def delete(record_id):
    db.session.delete(owned(Budget, record_id))
    db.session.commit()
    flash('Budget deleted.', 'success')
    return redirect(url_for('budgets.index'))


@main.get('/reports')
@login_required
def reports():
    today = date.today()
    period = request.args.get('period', 'month')
    if period == 'year':
        start, end = date(today.year, 1, 1), today
    elif period == 'last':
        end = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)
    elif period == 'custom':
        start, end = date_arg('start'), date_arg('end')
        if not start or not end or start > end:
            abort(400)
    else:
        start, end = today.replace(day=1), today
    stats = metrics(current_user.id, start, end)
    days = (end - start).days + 1
    months = (end.year - start.year) * 12 + end.month - start.month + 1
    return render_template('reports.html', stats=stats, start=start, end=end, daily=stats['spent'] / days, average=stats['spent'] / months, title='Financial summary', subtitle='Understand your habits. Build your next chapter.')


@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = IdentityForm(obj=current_user)
    password_form = PasswordForm()
    if request.form.get('action') == 'password':
        if password_form.validate_on_submit():
            if current_user.check_password(password_form.current_password.data):
                current_user.set_password(password_form.password.data)
                db.session.commit()
                flash('Password changed.', 'success')
                return redirect(url_for('main.profile'))
            password_form.current_password.errors.append('Current password is incorrect.')
    elif form.validate_on_submit():
        identity(current_user, form)
        if save():
            flash('Profile updated.', 'success')
            return redirect(url_for('main.profile'))
    return render_template('profile.html', form=form, password_form=password_form, title='Your profile', subtitle='Your account, your preferences.')


@admin.before_request
@login_required
def protect_admin():
    if not current_user.is_admin:
        abort(403)


@admin.get('/')
def dashboard_admin():
    stats = metrics()
    return render_template('admin/dashboard.html', stats=stats, user_count=User.query.count(), new_users=User.query.filter(User.created_at >= date.today().replace(day=1)).count(), latest=User.query.order_by(User.created_at.desc()).limit(5).all(), title='Platform overview', subtitle='The big picture, at a glance.', platform=True)


@admin.get('/users')
def users():
    query = User.query
    term = request.args.get('q', '')
    if term:
        query = query.filter(or_(User.full_name.ilike('%' + term + '%'), User.email.ilike('%' + term + '%'), User.username.ilike('%' + term + '%')))
    pagination = query.order_by(User.created_at.desc()).paginate(page=request.args.get('page', 1, type=int), per_page=10, error_out=False)
    return render_template('admin/users.html', users=pagination.items, pagination={'page': pagination.page, 'pages': pagination.pages, 'total': pagination.total}, title='Users', subtitle='Manage access with care.', platform=True)


@admin.get('/users/<int:user_id>')
def user_detail(user_id):
    user = db.get_or_404(User, user_id)
    return render_template('admin/user_detail.html', user=user, stats=metrics(user.id), title=user.full_name, subtitle='Account details', platform=True)


@admin.post('/users/<int:user_id>/<action>')
def user_action(user_id, action):
    user = db.get_or_404(User, user_id)
    if action not in ('toggle-active', 'toggle-admin', 'delete'):
        abort(404)
    if user.id == current_user.id:
        flash('You cannot deactivate, demote, or delete your own admin account.', 'warning')
    else:
        if action == 'delete':
            db.session.delete(user)
        elif action == 'toggle-active':
            user.active = not user.active
        else:
            user.is_admin = not user.is_admin
        db.session.commit()
        flash('User account updated.', 'success')
    return redirect(url_for('admin.users'))


@admin.get('/transactions')
def platform_transactions():
    return listing('Platform transactions', platform=True)


@admin.get('/analytics')
def analytics():
    stats = metrics()
    from datetime import datetime
    registrations = []
    for label in stats['chart']['labels']:
        month = datetime.strptime(label, '%b %Y')
        registrations.append(User.query.filter(db.extract('year', User.created_at) == month.year, db.extract('month', User.created_at) == month.month).count())
    stats['chart']['registrations'] = registrations
    return render_template('admin/analytics.html', stats=stats, title='Platform analytics', subtitle='Patterns behind the numbers.', platform=True)


@admin.get('/settings')
def settings():
    return render_template('admin/settings.html', title='Admin settings', subtitle='Platform configuration and account security.', platform=True)
