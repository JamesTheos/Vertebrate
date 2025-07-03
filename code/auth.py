from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from models import User
from models import db
from flask_login import login_user, logout_user, current_user

auth = Blueprint('auth', __name__)
logged_in=False

@auth.route('/loginstatus', methods = ['POST'])
def loginstatus():
    print("Checking login status: ", logged_in)
    return jsonify({'logged_in': logged_in})

@auth.route('/registerUser', methods=['POST'])
def register_user():
    # Here you would typically handle user registration logic
    username = request.json.get('username')
    password = request.json.get('password')
    role = request.json.get('role') 

    print(f"Registering user: {username}, Role: {role}")

    user = User.query.filter_by(username=username).first()

    if user:
        print("User already exists")
        return "User already exists", 400
    
    new_user = User(
        username=username,
        password=generate_password_hash(password),
        role=role
    )

    db.session.add(new_user)
    db.session.commit()
    print("User registered successfully")
    return "User registered successfully", 201

@auth.route('/loginUser', methods=['POST']) 
def loginUser():
    username = request.json.get('username')
    password = request.json.get('password')

    user = User.query.filter_by(username=username).first()

    if user and check_password_hash(user.password, password):
        print("Login successful")
        logged_in = True
        print("logged_in_status: ",logged_in)
        login_user(user)
        # Return a JSON response with the redirect URL
        return jsonify({'redirect': url_for('index'),'logged_in': logged_in})#,
    else:
        print("Login failed")
        logged_in = False
        print("logged_in_status: ",logged_in)
        return jsonify({'redirect': url_for('Login_error'), 'logged_in': logged_in})

@auth.route('/logoutUser', methods=['POST'])
def logoutUser():
    logout_user()
    logged_in = False
    print("logged_in_status: ",logged_in)
    print("User logged out")
    if logged_in:
        return jsonify({'redirect': url_for('Logout_message'), 'logged_in': logged_in})
    else:
        return jsonify({'redirect': url_for('index'), 'logged_in': logged_in})
