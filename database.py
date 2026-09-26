import sqlite3
import pandas as pd
import datetime

def get_connection():
    return sqlite3.connect("biotrace.db")

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Users Table (With registration_date)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            email TEXT,
            password TEXT,
            registration_date TEXT
        )
    ''')
    
    # Safely attempt to add the new column to existing databases
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN registration_date TEXT")
    except sqlite3.OperationalError:
        pass # Column already exists, safe to ignore
    
    # 2. Medications Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            med_name TEXT,
            dosage TEXT,
            timing TEXT
        )
    ''')
    
    # 3. Fitness Logs Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fitness_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            steps INTEGER,
            heart_rate INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

def register_user(username, email, password):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # --- TIMEZONE FIX: Lock to Indian Standard Time (UTC + 5:30) ---
        ist_offset = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        reg_date = datetime.datetime.now(ist_offset).strftime("%A, %B %d, %Y at %I:%M %p")
        
        cursor.execute(
            "INSERT INTO users (username, email, password, registration_date) VALUES (?, ?, ?, ?)", 
            (username, email, password, reg_date)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def verify_user(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = cursor.fetchone()
    conn.close()
    return user is not None

def add_medication(username, med_name, dosage, timing):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO medications (username, med_name, dosage, timing) VALUES (?, ?, ?, ?)", 
        (username, med_name, dosage, timing)
    )
    conn.commit()
    conn.close()

def get_medications(username):
    conn = get_connection()
    df = pd.read_sql_query("SELECT med_name, dosage, timing FROM medications WHERE username = ?", conn, params=(username,))
    conn.close()
    return df

def log_health_metrics(username, steps, heart_rate):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO fitness_logs (username, steps, heart_rate) VALUES (?, ?, ?)", 
        (username, steps, heart_rate)
    )
    conn.commit()
    conn.close()

def get_health_logs(username):
    conn = get_connection()
    df = pd.read_sql_query("SELECT date, steps, heart_rate FROM fitness_logs WHERE username = ?", conn, params=(username,))
    conn.close()
    return df
