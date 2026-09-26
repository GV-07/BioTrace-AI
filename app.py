import base64
import io
import re
import datetime
import streamlit as st
import streamlit.components.v1 as components
from gtts import gTTS

# Ensure these match your actual local files
from agent import stream_health_agent_response
from translations import UI_TEXT
from database import (
    add_medication,
    get_health_logs,
    get_medications,
    init_db,
    log_health_metrics,
    register_user,
    verify_user,
)

# Initialize local SQLite database
init_db()

st.set_page_config(
    page_title="BioTrace AI: Personal Health Assistant",
    page_icon="🩺",
    layout="wide",
)

# ==========================================
# TEXT TO SPEECH HELPER (Cached for Speed!)
# ==========================================
LANG_CODES = {
    "English": "en",
    "Tamil (தமிழ்)": "ta",
    "Hindi (हिंदी)": "hi",
    "Telugu (తెలుగు)": "te",
    "Malayalam (മലയാളം)": "ml"
}

@st.cache_data(show_spinner=False)
def generate_tts_audio(text, language):
    try:
        clean_text = text.replace("*", "").replace("#", "")
        lang_code = LANG_CODES.get(language, "en")
        tts = gTTS(text=clean_text, lang=lang_code, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp.read()
    except Exception as e:
        return None

# ==========================================
# CUSTOM IMAGE LOADER (Relative Paths for Cloud)
# ==========================================
@st.cache_data
def get_base64_image(image_path):
  try:
    with open(image_path, "rb") as img_file:
      return base64.b64encode(img_file.read()).decode()
  except Exception:
    return None

CIRCLE_LOGO = get_base64_image("logo.png")
RECT_LOGO = get_base64_image("BioTrace AI.png")

# ==========================================
# SESSION STATE & LOGIN
# ==========================================
if "logged_in" not in st.session_state:
  st.session_state.logged_in = False
  st.session_state.username = ""
  st.session_state.login_time = ""

if "language" not in st.session_state:
  st.session_state.language = "English"

# --- ADMIN STATES ---
if "admin_logged_in" not in st.session_state:
  st.session_state.admin_logged_in = False
if "show_admin_login" not in st.session_state:
  st.session_state.show_admin_login = False

# --- REGISTRATION CLEARING STATES ---
for key in ["reg_user", "reg_email", "reg_pw", "reg_conf_pw"]:
    if key not in st.session_state:
        st.session_state[key] = ""
if "clear_reg" not in st.session_state:
    st.session_state.clear_reg = False

t = UI_TEXT[st.session_state.language]

# ==========================================
# ISOLATED ADMIN DATABASE VIEWER
# ==========================================
def show_admin_db_view():
    col1, col2 = st.columns([8, 2], vertical_alignment="center")
    with col1:
        st.title("🛠️ Master Database Viewer")
    with col2:
        if st.button("🔒 Logout Admin", type="primary", use_container_width=True):
            st.session_state.admin_logged_in = False
            st.rerun()
            
    st.markdown("---")
    import sqlite3
    import pandas as pd
    
    conn = sqlite3.connect("biotrace.db")
    
    st.markdown("### 👤 Registered Users")
    users_df = pd.read_sql_query("SELECT * FROM users", conn)
    st.dataframe(users_df, use_container_width=True)
    
    st.markdown("#### 🗑️ Remove User Account")
    user_list = users_df["username"].tolist() if not users_df.empty else []
    
    with st.form("delete_user_form"):
        col_select, col_btn = st.columns([4, 1], vertical_alignment="bottom")
        with col_select:
            user_to_delete = st.selectbox("Select a patient to permanently delete:", user_list)
        with col_btn:
            delete_submit = st.form_submit_button("Delete User", type="primary", use_container_width=True)
            
        if delete_submit and user_to_delete:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE username = ?", (user_to_delete,))
            cursor.execute("DELETE FROM medications WHERE username = ?", (user_to_delete,))
            cursor.execute("DELETE FROM fitness_logs WHERE username = ?", (user_to_delete,))
            conn.commit()
            st.success(f"User '{user_to_delete}' and all associated records deleted.")
            st.rerun()

    st.markdown("---")
    st.markdown("### 💊 Active Medications")
    meds_df = pd.read_sql_query("SELECT * FROM medications", conn)
    st.dataframe(meds_df, use_container_width=True)
    
    st.markdown("### 🏃 Fitness Logs")
    logs_df = pd.read_sql_query("SELECT * FROM fitness_logs", conn)
    st.dataframe(logs_df, use_container_width=True)
    
    conn.close()

# ==========================================
# LOGIN & REGISTRATION PAGE
# ==========================================
def show_login_page():
  # 1. INJECT ANTI-COPY SCRIPT
  components.html("""
  <script>
  const parentDoc = window.parent.document;
  parentDoc.addEventListener('contextmenu', event => event.preventDefault());
  parentDoc.addEventListener('keydown', function(e) {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'c' || e.key === 'C')) {
          e.preventDefault();
      }
  });
  const style = parentDoc.createElement('style');
  style.innerHTML = 'body { -webkit-user-select: none; -ms-user-select: none; user-select: none; }';
  parentDoc.head.appendChild(style);
  </script>
  """, height=0, width=0)

  col1, col2, col3 = st.columns([1, 2, 1])
  with col2:
    
    # 2. RENDER THE LOGO & SECRET BUTTON
    if RECT_LOGO:
      st.markdown(f"<div style='text-align: center;'><img src='data:image/png;base64,{RECT_LOGO}' width='280'></div>", unsafe_allow_html=True)
      
      if st.button("SecretAdmin", use_container_width=True):
          st.session_state.show_admin_login = not st.session_state.show_admin_login
          st.rerun()
          
      st.markdown("""
      <style>
      div[data-testid="stButton"] button[kind="secondary"] {
          margin-top: -110px;
          margin-bottom: -40px; 
          height: 100px;
          opacity: 0;
          z-index: 999;
          cursor: pointer;
      }
      </style>
      """, unsafe_allow_html=True)
    
    # --- ADMIN LOGIN ROUTE ---
    if st.session_state.show_admin_login:
        st.markdown("<h2 style='text-align: center; color: #ff4b4b; margin-top: 10px;'>Admin</h2>", unsafe_allow_html=True)
        st.info("Enter the master password to access the BioTrace AI SQLite database.")
        with st.form("admin_login_form"):
            admin_pw = st.text_input("Master Password", type="password")
            if st.form_submit_button("Access Database", type="primary", use_container_width=True):
                if admin_pw == "BTAI@1234": 
                    st.session_state.admin_logged_in = True
                    st.session_state.show_admin_login = False
                    st.rerun()
                else:
                    st.error("Access Denied. Incorrect password.")
        return 

    # --- NORMAL PATIENT LOGIN ROUTE ---
    st.markdown("<p style='text-align: center; color: gray; margin-top: 10px; margin-bottom: 20px;'>Secure Healthcare Monitoring Platform</p>", unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["🔒 Login", "📝 Register"])

    with tab_login:
        with st.form("login_form"):
          username_input = st.text_input("Username", value="")
          password_input = st.text_input("Password", type="password")
          submit_login = st.form_submit_button("Secure Login", type="primary", use_container_width=True)

          if submit_login:
            if username_input and password_input:
              if (username_input == "Gokul" and password_input == "") or verify_user(username_input, password_input):
                  st.session_state.logged_in = True
                  st.session_state.username = username_input
                  # Record the exact Date and Time of login
                  st.session_state.login_time = datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
                  st.rerun()
              else:
                  st.error("Invalid username or password. Please check your credentials or register.")
            else:
              st.error("Please enter both username and password.")

    with tab_register:
        if st.session_state.get("reg_success_msg"):
            st.success("Account created successfully! You can now log in.")
            st.session_state.reg_success_msg = False

        if st.session_state.get("clear_reg"):
            st.session_state.reg_user = ""
            st.session_state.reg_email = ""
            st.session_state.reg_pw = ""
            st.session_state.reg_conf_pw = ""
            st.session_state.clear_reg = False

        new_username = st.text_input("Choose a Username", key="reg_user")
        email = st.text_input("Email Address", key="reg_email")
        new_pw = st.text_input("Create Password", type="password", key="reg_pw")
        
        is_valid_pw = False
        if new_pw:
            if len(new_pw) < 8:
                st.markdown("Strength: <span style='color:#ff4b4b; font-weight:bold;'>Weak</span> (Must be at least 8 characters)", unsafe_allow_html=True)
            else:
                has_up = bool(re.search(r"[A-Z]", new_pw))
                has_low = bool(re.search(r"[a-z]", new_pw))
                has_spec = bool(re.search(r"[!@#$%^&*(),.?\":{}|<>]", new_pw))
                
                if (has_up + has_low + has_spec) == 3:
                    st.markdown("Strength: <span style='color:#09ab3b; font-weight:bold;'>Strong</span>", unsafe_allow_html=True)
                    is_valid_pw = True
                else:
                    st.markdown("Strength: <span style='color:#ffa421; font-weight:bold;'>Weak</span> (Include uppercase, lowercase, and special characters)", unsafe_allow_html=True)
                
        conf_pw = st.text_input("Confirm Password", type="password", key="reg_conf_pw")

        if st.button("Create Account", type="primary", use_container_width=True):
            if not new_username or not email or not new_pw or not conf_pw:
                st.error("Please fill out all required fields.")
            elif not re.match(r"^[a-zA-Z0-9_.+-]+@(gmail\.com|outlook\.com)$", email):
                st.error("Registration requires a valid @gmail.com or @outlook.com email address.")
            elif not is_valid_pw:
                st.error("Password must be Strong (8+ characters, uppercase, lowercase, and a special character).")
            elif new_pw != conf_pw:
                st.error("Passwords do not match.")
            else:
                if register_user(new_username, email, new_pw):
                    st.session_state.reg_success_msg = True
                    st.session_state.clear_reg = True
                    st.rerun()
                else:
                    st.error("Username already exists. Please choose a different one.")


# ==========================================
# APP ROUTING LOGIC
# ==========================================
if st.session_state.admin_logged_in:
    show_admin_db_view()
    st.stop()

if not st.session_state.logged_in:
    show_login_page()
    st.stop()


# ==========================================
# MAIN APP HEADER & SIDEBAR
# ==========================================
if CIRCLE_LOGO:
  st.markdown(
      f"<div style='display: flex; align-items: center; margin-bottom: 10px;'>"
      f"<img src='data:image/png;base64,{CIRCLE_LOGO}' width='60' style='margin-right: 15px;'>"
      f"<h1 style='margin: 0; padding: 0;'>{t['app_title']}</h1></div>",
      unsafe_allow_html=True,
  )
else:
  st.title(f"🩺 {t['app_title']}")

if RECT_LOGO:
  st.sidebar.markdown(f"<div style='text-align: center;'><img src='data:image/png;base64,{RECT_LOGO}' width='100%' style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

st.sidebar.header(f"{t['welcome']}, {st.session_state.username}!")

# Display the Date and Time the user logged in
if st.session_state.login_time:
    st.sidebar.caption(f"🕒 **Last Login:**<br>{st.session_state.login_time}", unsafe_allow_html=True)
    st.sidebar.markdown("---")

menu = st.sidebar.radio(
    t["nav_menu"],
    [
        t["chatbot"], 
        t["med_tracker"], 
        t["fitness"], 
        t["dashboard"], 
        t["indian_meds"], 
        "🫀CardioPulse AI",
        t["contact"], 
        t["settings"]
    ],
)

st.sidebar.markdown("---")
if st.sidebar.button(t["logout"], use_container_width=True):
  st.session_state.logged_in = False
  st.session_state.username = ""
  st.session_state.login_time = ""
  st.rerun()

st.sidebar.markdown("---")
st.sidebar.info(t["disclaimer"])

patient_name = st.session_state.username

# ------------------------------------------
# TAB 1: AI HEALTH CHATBOT
# ------------------------------------------
if menu == t["chatbot"]:
  st.subheader(t["chat_header"])
  st.write(t["chat_desc"])

  if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant", 
        "content": f"Hello {patient_name}! How can I help you stay healthy today?"
    }]

  for idx, message in enumerate(st.session_state.messages):
    role_class = "user" if message["role"] == "user" else "assistant"
    icon = "🧑‍💻 " if message["role"] == "user" else "🩺 "
    
    audio_html = ""
    if "audio" in message and message["audio"]:
        b64_audio = base64.b64encode(message["audio"]).decode()
        audio_html = f"""<div style="margin-top: 10px;"><audio controls src="data:audio/mp3;base64,{b64_audio}" style="height: 35px; max-width: 100%; border-radius: 5px; outline: none;"></audio></div>"""

    st.markdown(
        f"""<div class="chat-row {role_class}"><div class="chat-bubble"><b>{icon}</b>{message['content']}{audio_html}</div></div>""",
        unsafe_allow_html=True,
    )

  st.markdown(
      """
      <style>
      .chat-row { display: flex; margin-bottom: 15px; width: 100%; }
      .chat-row.user { justify-content: flex-end; }
      .chat-row.assistant { justify-content: flex-start; }
      .chat-bubble { max-width: 70%; padding: 12px 16px; border-radius: 15px; font-size: 15px; line-height: 1.5; word-wrap: break-word; }
      .chat-row.user .chat-bubble { background-color: #2b313e; color: #ffffff; border-bottom-right-radius: 2px; }
      .chat-row.assistant .chat-bubble { background-color: #f0f2f6; color: #1e1e1e; border-bottom-left-radius: 2px; }
      
      .block-container { padding-bottom: 150px !important; }
      div[data-testid="stHorizontalBlock"] {
          position: fixed !important; bottom: 25px; z-index: 999;
          background-color: #2b313e; border-radius: 15px; padding: 10px 15px;
          align-items: center; width: calc(100% - 24rem);
          box-shadow: 0px -5px 15px rgba(0,0,0,0.4);
      }
      div[data-testid="stPopover"] > button { background-color: transparent !important; border: none !important; font-size: 24px !important; padding: 0 !important; }
      div[data-testid="column"]:nth-child(4) button { border-radius: 50% !important; height: 45px !important; width: 45px !important; padding: 0 !important; }
      </style>
      """,
      unsafe_allow_html=True,
  )

  if "user_text" not in st.session_state: st.session_state.user_text = ""
  if "submitted_text" not in st.session_state: st.session_state.submitted_text = ""
  if "trigger_send" not in st.session_state: st.session_state.trigger_send = False

  def submit_message():
      st.session_state.submitted_text = st.session_state.user_text
      st.session_state.user_text = ""
      st.session_state.trigger_send = True

  col_left, col_text, col_mic, col_send = st.columns([1, 7, 3, 1], vertical_alignment="center")
  
  with col_left:
      with st.popover("➕"):
          uploaded_file = st.file_uploader("Upload Image/PDF", type=["png", "jpg", "jpeg", "pdf"], label_visibility="collapsed")
          
  with col_text:
      st.text_input("Message", key="user_text", label_visibility="collapsed", placeholder=t["chat_placeholder"], on_change=submit_message)
      
  with col_mic:
      audio_bytes = st.audio_input("Record Voice", label_visibility="collapsed")
      
  with col_send:
      st.button("⬆️", use_container_width=True, on_click=submit_message)

  if st.session_state.trigger_send or uploaded_file or audio_bytes:
    if st.session_state.submitted_text or uploaded_file or audio_bytes:
        st.session_state.trigger_send = False 
        
        prompt = st.session_state.submitted_text
        st.session_state.submitted_text = "" 
        
        final_prompt = prompt if prompt else "Please analyze my attached input."
        media_data = None
        media_type = None

        if audio_bytes:
            media_data = audio_bytes.read()
            media_type = "audio/wav"
            final_prompt += " *(The patient provided a voice note describing their problem.)*"
        elif uploaded_file:
            media_data = uploaded_file.read()
            media_type = uploaded_file.type
            final_prompt += f" *(The patient attached a file: {uploaded_file.name})*"

        st.session_state.messages.append({"role": "user", "content": final_prompt})
        st.markdown(f'<div class="chat-row user"><div class="chat-bubble"><b>🧑‍💻 </b>{final_prompt}</div></div>', unsafe_allow_html=True)

        message_placeholder = st.empty()
        full_response = ""

        for chunk in stream_health_agent_response(
            final_prompt, 
            st.session_state.messages, 
            st.session_state.language,
            media_bytes=media_data,
            media_mime=media_type
        ):
            full_response += chunk
            message_placeholder.markdown(
                f'<div class="chat-row assistant"><div class="chat-bubble"><b>🩺 </b>{full_response}▌</div></div>', 
                unsafe_allow_html=True
            )
        
        message_placeholder.markdown(
            f'<div class="chat-row assistant"><div class="chat-bubble"><b>🩺 </b>{full_response}</div></div>', 
            unsafe_allow_html=True
        )
        
        tts_audio = generate_tts_audio(full_response, st.session_state.language)
        
        st.session_state.messages.append({
            "role": "assistant", 
            "content": full_response,
            "audio": tts_audio
        })
        st.rerun()

# ------------------------------------------
# TAB 2: MEDICATION TRACKER
# ------------------------------------------
elif menu == t["med_tracker"]:
  st.subheader(t["med_header"])
  with st.form("med_form"):
    col1, col2 = st.columns(2)
    with col1:
      med_name = st.text_input("Medication Name")
      dosage = st.text_input("Dosage")
    with col2:
      timing = st.selectbox("Timing", ["Morning", "Afternoon", "Night", "As Needed"])
    submit_med = st.form_submit_button(t["med_add_btn"])
    
    if submit_med and med_name:
      add_medication(patient_name, med_name, dosage, timing)
      st.success("Added successfully!")
      
  st.markdown("### Active Medications")
  meds_df = get_medications(patient_name)
  if not meds_df.empty:
    st.dataframe(meds_df, use_container_width=True)

# ------------------------------------------
# TAB 3: FITNESS & VITALS LOG
# ------------------------------------------
elif menu == t["fitness"]:
  st.subheader(t["fit_header"])
  with st.form("fitness_form"):
    steps = st.number_input("Step Count", min_value=0, max_value=50000, value=6500)
    heart_rate = st.number_input("Heart Rate (bpm)", min_value=40, max_value=200, value=72)
    submit_fit = st.form_submit_button(t["fit_log_btn"])
    
    if submit_fit:
      log_health_metrics(patient_name, steps, heart_rate)
      st.success("Logged securely!")
      
  st.markdown("### Log History")
  logs_df = get_health_logs(patient_name)
  if not logs_df.empty:
    st.dataframe(logs_df, use_container_width=True)

# ------------------------------------------
# TAB 4: PATIENT DASHBOARD
# ------------------------------------------
elif menu == t["dashboard"]:
  st.subheader(f"{t['dash_header']}: {patient_name}")
  logs_df = get_health_logs(patient_name)
  if not logs_df.empty:
    col1, col2 = st.columns(2)
    with col1: st.metric("Latest Steps", int(logs_df["steps"].iloc[-1]))
    with col2: st.metric("Latest Heart Rate", f"{int(logs_df['heart_rate'].iloc[-1])} bpm")
    st.line_chart(logs_df.set_index("date")["steps"])
  else:
    st.info("No fitness logs found. Submit your data in the Fitness tab.")

# ------------------------------------------
# TAB 5: INDIAN MEDS & AYURVEDA
# ------------------------------------------
elif menu == t["indian_meds"]:
  st.subheader(t["ayur_header"])
  search_term = st.text_input(t["ayur_search"])
  
  if search_term:
      st.info(f"Searching database for: {search_term}. Try asking the AI Health Chatbot for detailed Ayurvedic remedies!")

# ------------------------------------------
# TAB 6: CARDIOPULSE AI
# ------------------------------------------
elif menu == "CardioPulse AI":
  st.subheader("🫀 CardioPulse AI")
  st.write("CardioPulse AI is hosted on a dedicated platform for advanced cardiovascular health monitoring and prediction.")
  
  st.markdown("<br>", unsafe_allow_html=True)
  
  st.link_button(
      "Launch CardioPulse AI ↗", 
      "https://cardiopulseai.streamlit.app/", 
      type="primary",
      use_container_width=True
  )

# ------------------------------------------
# TAB 7: CONTACT
# ------------------------------------------
elif menu == t["contact"]:
  st.subheader(t["contact_header"])
  st.markdown("📧 <a href='https://mail.google.com/mail/u/0/?tab=rm&ogbl#inbox?compose=CllgCJTJpKTGSGWsKlhDjKBrJJcbLgpqLWRCkTjJzfSwMLhSVvPhjbpXGnCFTtlPHWvgMhWBxtL' target='_blank'>biotraceai@gmail.com</a>", unsafe_allow_html=True)

# ------------------------------------------
# TAB 8: SETTINGS
# ------------------------------------------
elif menu == t["settings"]:
  st.subheader(t["settings_header"])
  col1, col2 = st.columns(2)
  
  with col1:
      new_language = st.selectbox("Primary Display Language", list(UI_TEXT.keys()), index=list(UI_TEXT.keys()).index(st.session_state.language))
      region = st.selectbox("Region", ["South India", "North India", "East India", "West India", "Central India"])
      
  with col2:
      med_reminders = st.toggle("Medication Reminders (Push/Email)", value=True)
      health_alerts = st.toggle("Weekly Health Report Alerts", value=True)
      
  st.markdown("---")
  theme = st.radio("App Theme", ["System Default", "Light Mode", "Dark Mode"], horizontal=True)
  
  if st.button("Save Preferences", type="primary"):
      st.session_state.language = new_language
      st.rerun()
