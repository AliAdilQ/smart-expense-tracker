from getpass import getpass
from app import create_app
from tracker.extensions import db
from tracker.models import User
from tracker.forms import RegisterForm


def main():
    app = create_app()
    with app.test_request_context():
        from werkzeug.datastructures import MultiDict
        name = input('Full name: ').strip()
        username = input('Username: ').strip().lower()
        email = input('Email: ').strip().lower()
        password = getpass('Password (at least 10 characters): ')
        confirm = getpass('Confirm password: ')
        form = RegisterForm(MultiDict({'full_name': name, 'username': username, 'email': email, 'password': password, 'confirm': confirm}), meta={'csrf': False})
        if not form.validate():
            print('Invalid input:', form.errors)
            return
        if User.query.filter((User.username == username) | (User.email == email)).first():
            print('That username or email already exists. No account changed.')
            return
        user = User(full_name=name, username=username, email=email, is_admin=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print('Administrator created. Sign in at http://127.0.0.1:5000/login')


if __name__ == '__main__':
    main()
