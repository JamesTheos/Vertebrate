from flask import Blueprint, render_template, redirect, url_for, request, jsonify, session
from datetime import timedelta, datetime
from werkzeug.security import generate_password_hash, check_password_hash
from models import User
from models import db
from flask_login import login_user, logout_user, current_user
from models import Role

auth = Blueprint('auth', __name__) 

@auth.route('/registerUser', methods=['POST'])
def register_user():
    data = request.get_json()

    username = data.get('username')
    password = data.get('password')
    role_ids = data.get('roles')  # ⬅️ Erwartet Liste von Rollen-IDs

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

    print("User registered successfully")
    return "User registered successfully", 201


@auth.route('/loginUser', methods=['POST']) 
def loginUser():
    username = request.json.get('username')
    password = request.json.get('password')

    user = User.query.filter_by(username=username).first()

    if user and check_password_hash(user.password, password) and not current_user.is_authenticated:
        print("Login successful")
        login_user(user)        
        # Return a JSON response with the redirect URL
        return jsonify({'redirect': url_for('index')})

    else:
        print("Login failed")
        return jsonify({'redirect': url_for('Login_error')})

@auth.route('/logoutUser', methods=['POST'])
def logoutUser():
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
    new_role_ids = data.get('roles')  # Erwartet Liste von Rollen-IDs

    print(f"Updating user: {current_user.username}")

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
    print("User updated successfully")
    return jsonify({'redirect': url_for('updated_user')})
