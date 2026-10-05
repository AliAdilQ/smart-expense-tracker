import os
from flask import Flask, render_template
from config import Config
from tracker.extensions import db, login_manager, csrf


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if os.environ.get('APP_ENV') == 'production' and not os.environ.get('SECRET_KEY'):
        raise RuntimeError('Set SECRET_KEY before running in production.')
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    from tracker.models import User
    from tracker.routes import auth, main, expenses, income, budgets, admin
    for blueprint in (auth, main, expenses, income, budgets, admin):
        app.register_blueprint(blueprint)

    @login_manager.user_loader
    def load_user(user_id):
        user = db.session.get(User, int(user_id))
        return user if user and user.is_active else None

    @app.template_filter('money')
    def money(value):
        return '${:,.2f}'.format(value or 0)

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if response.mimetype == 'text/html':
            response.headers['Cache-Control'] = 'no-store'
        return response

    for code in (400, 403, 404, 500):
        def error_handler(error, status=code):
            if status == 500:
                db.session.rollback()
            return render_template(str(status) + '.html', code=status), status
        app.register_error_handler(code, error_handler)
    with app.app_context():
        db.create_all()
    return app


if __name__ == '__main__':
    from waitress import serve
    serve(create_app(), host='127.0.0.1', port=int(os.environ.get('PORT', 5000)))
