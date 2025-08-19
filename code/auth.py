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
    # Here you would typically handle user registration logic
    username = request.json.get('username')
    password = request.json.get('password')
    role_id = request.json.get('role') 

    print(f"Registering user: {username}, Role ID: {role_id}")
    user = User.query.filter_by(username=username).first()

    if user:
        print("User already exists")
        return "User already exists", 400
    
    new_user = User(
        username=username,
        password=generate_password_hash(password),
    )

    role = Role.query.filter_by(id=role_id).first()
    if not role:
        print(f"Role with ID '{role_id}' not found")
        return f"Role does not exist", 400

    # ⬅️ Rolle zuweisen über Many-to-Many
    new_user.roles.append(role)

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

    new_username = request.json.get('username')
    new_password = request.json.get('password')

    #user = User.query.filter_by(id=current_user.username).first()
    if current_user.is_authenticated:
        if new_username :
            current_user.username = new_username
        if new_password :
            current_user.password = generate_password_hash(new_password)
        db.session.commit()
        print("User updated successfully")
        return jsonify({'redirect': url_for('updated_user')})