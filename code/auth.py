from flask import Blueprint, render_template, redirect, url_for, request, jsonify, session
from datetime import timedelta, datetime
from werkzeug.security import generate_password_hash, check_password_hash
from models import User
from models import db
from flask_login import login_user, logout_user, current_user
from models import Role
from audit_trail import log_audit, log_field_change

auth = Blueprint('auth', __name__) 

@auth.route('/registerUser', methods=['POST'])
def register_user():
    data = request.get_json()

    username = data.get('username')
    password = data.get('password')
    role_ids = data.get('roles')

    print(f"Registering user: {username}, Roles: {role_ids}")

    # Existiert der Benutzer schon?
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        print("User already exists")
        return "User already exists", 400

    # Benutzer anlegen
    new_user = User(
        username=username,
        password=generate_password_hash(password)
    )

    # Rollen anhand der IDs laden
    if not role_ids or not isinstance(role_ids, list):
        return "Invalid role selection", 400

    roles = Role.query.filter(Role.id.in_(role_ids)).all()

    if len(roles) != len(role_ids):
        return "One or more roles not found", 400

    # Rollen zuweisen
    new_user.roles.extend(roles)

    # In DB speichern
    db.session.add(new_user)
    db.session.commit()

    # Audit: log new user creation after successful commit
    log_audit(
        action_type='CREATE',
        record_type='USER',
        record_id=str(new_user.id),
        change_reason='New user registration'
    )

    print("User registered successfully")
    return "User registered successfully", 201


@auth.route('/loginUser', methods=['POST']) 
def loginUser():
    # Accept both application/json (fetch from JS) and
    # application/x-www-form-urlencoded (native <form> submit).
    json_data = request.get_json(force=True, silent=True)
    if json_data:
        username = json_data.get('username')
        password = json_data.get('password')
    else:
        username = request.form.get('username')
        password = request.form.get('password')

    user = User.query.filter_by(username=username).first()

    if user and check_password_hash(user.password, password) and not current_user.is_authenticated:
        print("Login successful")
        login_user(user)
        # Audit: log successful login after login_user() so current_user is set
        log_audit(
            action_type='LOGIN',
            record_type='USER',
            record_id=str(user.id),
            change_reason='Successful login'
        )
        # JSON fetch gets a redirect URL; native form submit gets a direct redirect
        if json_data:
            return jsonify({'redirect': url_for('index')})
        return redirect(url_for('index'))

    else:
        print("Login failed")
        # Audit: log failed attempt; record_id is user.id if account exists, else None
        log_audit(
            action_type='LOGIN_FAILED',
            record_type='USER',
            record_id=str(user.id) if user else None,
            change_reason='Invalid credentials'
        )
        if json_data:
            return jsonify({'redirect': url_for('Login_error')})
        return redirect(url_for('Login_error'))


@auth.route('/logoutUser', methods=['POST'])
def logoutUser():
    # Audit: capture user id BEFORE logout_user() clears current_user
    user_id = str(current_user.id) if current_user.is_authenticated else None
    log_audit(
        action_type='LOGOUT',
        record_type='USER',
        record_id=user_id,
        change_reason='User logout'
    )
    logout_user()
    session.permanent = False
    print("User logged out")
    if current_user.is_authenticated:
        return jsonify({'redirect': url_for('Logout_message')})
    else:
        return jsonify({'redirect': url_for('index')})


@auth.route('/UpdateUser', methods=['POST'])
def update_user():
    if not current_user.is_authenticated:
        return jsonify({'redirect': url_for('Login_error')})

    data = request.get_json()

    new_username = data.get('username')
    new_password = data.get('password')
    new_role_ids = data.get('roles')

    print(f"Updating user: {current_user.username}")

    # Capture old values BEFORE any mutations so audit records are accurate
    user_id = str(current_user.id)
    old_username = current_user.username
    old_role_names = [r.name for r in current_user.roles] if new_role_ids is not None else None

    # Username aktualisieren
    if new_username:
        current_user.username = new_username

    # Passwort aktualisieren
    if new_password:
        current_user.password = generate_password_hash(new_password)

    # Rollen aktualisieren (falls angegeben)
    if new_role_ids is not None:
        if not isinstance(new_role_ids, list):
            return "Invalid role format", 400

        roles = Role.query.filter(Role.id.in_(new_role_ids)).all()
        if len(roles) != len(new_role_ids):
            return "One or more roles not found", 400

        # Vorherige Rollen entfernen und durch neue ersetzen
        current_user.roles = roles

    db.session.commit()

    # Audit: log username change
    if new_username:
        log_field_change(
            action_type='UPDATE',
            record_type='USER',
            record_id=user_id,
            field_name='username',
            old_value=old_username,
            new_value=new_username,
            change_reason='Username updated'
        )

    # Audit: log password change — _sanitize_value() auto-redacts to [REDACTED]
    if new_password:
        log_field_change(
            action_type='UPDATE',
            record_type='USER',
            record_id=user_id,
            field_name='password',
            old_value='[REDACTED]',
            new_value='[REDACTED]',
            change_reason='User password change'
        )

    # Audit: log role changes
    if new_role_ids is not None:
        new_role_names = [r.name for r in roles]
        log_field_change(
            action_type='UPDATE',
            record_type='USER',
            record_id=user_id,
            field_name='role',
            old_value=str(old_role_names),
            new_value=str(new_role_names),
            change_reason='Role updated by admin'
        )

    print("User updated successfully")
    return jsonify({'redirect': url_for('updated_user')})
