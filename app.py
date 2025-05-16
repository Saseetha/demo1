from flask import Flask, render_template, request, redirect, url_for, session, flash
import pandas as pd
import numpy as np
import logging
import joblib
import json
import sys
import os
import sqlite3
from g4f.client import Client

current_dir = os.path.dirname(__file__)

# Flask app
app = Flask(__name__, static_folder='static', template_folder='template')
app.secret_key = 'your_secret_key_here'

# Logging
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.ERROR)

def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    # Update users table
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL UNIQUE,
                        password TEXT NOT NULL,
                        mobile TEXT,
                        dob TEXT,
                        location TEXT
                    )''')

    # Create a predictions table
    cursor.execute('''CREATE TABLE IF NOT EXISTS predictions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        name TEXT,
                        gender TEXT,
                        education TEXT,
                        self_employed TEXT,
                        marital_status TEXT,
                        dependents TEXT,
                        applicant_income REAL,
                        coapplicant_income REAL,
                        loan_amount REAL,
                        loan_term REAL,
                        credit_history REAL,
                        property_area TEXT,
                        result TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(user_id) REFERENCES users(id)
                    )''')
    conn.commit()
    conn.close()

init_db()

# Function
def ValuePredictor(data=pd.DataFrame):
    # Model name
    model_name = r'C:\Users\Hp\Desktop\loan-approval-prediction-main\bin\xgboostModel.pkl'
    # Directory where the model is stored
    model_dir = os.path.join(current_dir, model_name)
    # Load the model
    loaded_model = joblib.load(open(model_dir, 'rb'))
    # Predict the data
    result = loaded_model.predict(data)
    return result[0]

# Home page
@app.route('/index')
def home():
    return render_template('index.html')

# Login page
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')

    return render_template('login.html')

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if the credentials match
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('Login successful! Welcome to the Admin Dashboard.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')

    return render_template('admin_login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        mobile = request.form['mobile']
        dob = request.form['dob']
        location = request.form['location']

        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password, mobile, dob, location) VALUES (?, ?, ?, ?, ?)",
                           (username, password, mobile, dob, location))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists. Please choose another.', 'danger')
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        flash('Please log in to view your dashboard.', 'warning')
        return redirect(url_for('login'))

    # Get the logged-in user's username
    username = session['username']
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    # Fetch all users' data
    cursor.execute("SELECT id, username, mobile, dob, location FROM users")
    all_users_data = cursor.fetchall()

    if not all_users_data:
        flash('No users found!', 'danger')
        return redirect(url_for('login'))

    # Prepare to collect predictions for all users
    users_with_predictions = []

    for user in all_users_data:
        user_id, username, mobile, dob, location = user

        # Fetch user's predictions
        cursor.execute("SELECT name, gender, education, self_employed, marital_status, dependents, "
                       "applicant_income, coapplicant_income, loan_amount, loan_term, credit_history, "
                       "property_area, result, timestamp FROM predictions WHERE user_id = ?", (user_id,))
        predictions_data = cursor.fetchall()

        # Add user data and their predictions to the list
        users_with_predictions.append({
            'user': user,
            'predictions': predictions_data
        })

    conn.close()

    return render_template('dashboard.html', users_with_predictions=users_with_predictions)

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/model')
def model():
    return render_template('model.html')

@app.route('/prediction', methods=['POST'])
def predict():
    if 'username' not in session:
        flash('Please log in to access the prediction feature.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = session['username']
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()

        # Fetch user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_id = cursor.fetchone()[0]

        # Get data from the form
        name = request.form['name']
        gender = request.form['gender']
        education = request.form['education']
        self_employed = request.form['self_employed']
        marital_status = request.form['marital_status']
        dependents = request.form['dependents']
        applicant_income = float(request.form['applicant_income'])
        coapplicant_income = float(request.form['coapplicant_income'])
        loan_amount = float(request.form['loan_amount'])
        loan_term = float(request.form['loan_term'])
        credit_history = float(request.form['credit_history'])
        property_area = request.form['property_area']

        # Prediction process
        schema_name = 'data/columns_set.json'
        schema_dir = os.path.join(current_dir, schema_name)
        with open(schema_dir, 'r') as f:
            cols = json.loads(f.read())
        schema_cols = cols['data_columns']

        # Update schema columns with input values
        schema_cols.update({
            'ApplicantIncome': applicant_income,
            'CoapplicantIncome': coapplicant_income,
            'LoanAmount': loan_amount,
            'Loan_Amount_Term': loan_term,
            'Gender_Male': gender,
            'Married_Yes': marital_status,
            'Education_Not Graduate': education,
            'Self_Employed_Yes': self_employed,
            'Credit_History_1.0': credit_history,
        })

        df = pd.DataFrame(data={k: [v] for k, v in schema_cols.items()}, dtype=float)
        result = ValuePredictor(data=df)

        prediction = 'Approved' if int(result) == 1 else 'Rejected'

        # Store prediction in the database
        cursor.execute('''INSERT INTO predictions
                          (user_id, name, gender, education, self_employed, marital_status, dependents,
                          applicant_income, coapplicant_income, loan_amount, loan_term, credit_history,
                          property_area, result)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (user_id, name, gender, education, self_employed, marital_status, dependents,
                        applicant_income, coapplicant_income, loan_amount, loan_term, credit_history,
                        property_area, prediction))
        conn.commit()
        conn.close()

        # AI Analysis
        client = Client()
        ai_input = f"""
        User Input:
        - Name: {name}
        - Gender: {gender}
        - Education: {education}
        - Self-Employed: {self_employed}
        - Marital Status: {marital_status}
        - Dependents: {dependents}
        - Applicant Income: {applicant_income}
        - Coapplicant Income: {coapplicant_income}
        - Loan Amount: {loan_amount}
        - Loan Term: {loan_term}
        - Credit History: {credit_history}
        - Property Area: {property_area}

        Prediction Result: {prediction}

        Provide an analysis of why the loan was {prediction.lower()} and suggest improvements if applicable.
        """
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": ai_input}],
            web_search=False
        )
        ai_analysis = response.choices[0].message.content

        # Return the prediction and AI analysis
        flash(f'Prediction: {prediction}', 'info')
        return render_template('prediction.html', prediction=prediction, ai_analysis=ai_analysis)

    return render_template('error.html', prediction='An error occurred.')

if __name__ == '__main__':
    app.run(debug=True)
