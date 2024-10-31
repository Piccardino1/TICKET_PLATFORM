from flask import Flask, jsonify, render_template_string, request, session, redirect, url_for
import ssl
import json
from functools import wraps
from datetime import timedelta

app = Flask(__name__)
app.secret_key = 'una_chiave_segreta_molto_lunga_e_complessa'
app.permanent_session_lifetime = timedelta(minutes=1)

context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
context.load_cert_chain(certfile='./cert/cert.pem', keyfile='./cert/key.pem')

# Carica le credenziali dal file JSON
def load_credentials():
    with open('login_fronthand/login.json', 'r') as file:
        return json.load(file)
    
# Carica le credenziali dal file JSON
def load_credentials_back():
    with open('login_backdesk/login_back.json', 'r') as file:
        return json.load(file)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login_fronthand'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/verify_credentials', methods=['POST'])
def verify_credentials():
    credentials = load_credentials()
    data = request.get_json()
    
    username = data.get('username')
    password = data.get('password')
    
    for user in credentials:
        if user['username'] == username and user['password'] == password:
            session.permanent = True  # Abilita la sessione permanente
            session['logged_in'] = True
            return jsonify({'success': True})
    
    return jsonify({'success': False}), 401

@app.route('/verify_credentials_back', methods=['POST'])
def verify_credentials_back():
    credentials = load_credentials_back()
    data = request.get_json()
    
    username = data.get('username')
    password = data.get('password')
    
    for user in credentials:
        if user['username'] == username and user['password'] == password:
            session.permanent = True  # Abilita la sessione permanente
            session['logged_in'] = True
            return jsonify({'success': True})
    
    return jsonify({'success': False}), 401

@app.route('/login_ticket')
def login_backhand():
    return render_template_string(login_backdesk)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login_fronthand'))

login = "login_fronthand/login.html"
with open(login, "r", encoding='utf-8') as file:
    login_front = file.read()

login_back = "login_backdesk/login_back.html"
with open(login_back, "r", encoding='utf-8') as file:
    login_backdesk = file.read()

@app.route('/login')
def login_fronthand():
    return render_template_string (login_front)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002, ssl_context=context)