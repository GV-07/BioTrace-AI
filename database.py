import sqlite3
import pandas as pd

def get_connection():
    # check_same_thread=False prevents Streamlit threading errors with SQLite
    return sqlite3.connect("biotrace.db", check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            email TEXT,
            password TEXT
        )
    """)
    
    # 2. Medications Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            med_name TEXT,
            dosage TEXT,
            timing TEXT
        )
    """)
    
    # 3. Fitness Logs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fitness_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            steps INTEGER,
            heart_rate INTEGER
        )
    """)
    
    conn.commit()
    conn.close()

# --- USER REGISTRATION & LOGIN ---

def register_user(username, email, password):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", (username, email, password))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False # Username already exists

def verify_user(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = cursor.fetchone()
    conn.close()
    return user is not None

# --- MEDICATIONS ---

def add_medication(username, med_name, dosage, timing):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO medications (username, med_name, dosage, timing) VALUES (?, ?, ?, ?)", (username, med_name, dosage, timing))
    conn.commit()
    conn.close()

def get_medications(username):
    conn = get_connection()
    df = pd.read_sql_query("SELECT med_name as 'Medication Name', dosage as 'Dosage', timing as 'Timing' FROM medications WHERE username = ?", conn, params=(username,))
    conn.close()
    return df

# --- FITNESS LOGS ---

def log_health_metrics(username, steps, heart_rate):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO fitness_logs (username, steps, heart_rate) VALUES (?, ?, ?)", (username, steps, heart_rate))
    conn.commit()
    conn.close()

def get_health_logs(username):
    conn = get_connection()
    df = pd.read_sql_query("SELECT date as 'Date', steps as 'Steps', heart_rate as 'Heart Rate (bpm)' FROM fitness_logs WHERE username = ?", conn, params=(username,))
    conn.close()
    return df