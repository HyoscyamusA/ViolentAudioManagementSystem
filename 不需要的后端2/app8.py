from flask import Flask, render_template, request, redirect, url_for, session, g
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key'
DATABASE = 'database.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.executescript('''
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT CHECK(role IN ('admin', 'user')) NOT NULL
            );
            INSERT OR IGNORE INTO user (username, password, role) VALUES ('admin', 'root', 'admin');
        ''')
        db.commit()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = 'user'
        
        db = get_db()
        try:
            db.execute('INSERT INTO user (username, password, role) VALUES (?, ?, ?)',
                       (username, password, role))
            db.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "Username already exists!"
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    print(request.method)  # 调试输出
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = query_db('SELECT * FROM user WHERE username = ? AND password = ?', (username, password), one=True)
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            return "Invalid credentials!"
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return f"Welcome, {session['username']}! Role: {session['role']}"

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
