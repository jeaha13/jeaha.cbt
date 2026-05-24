import streamlit as st
import pandas as pd
import os
import json
import time
import zipfile
import io
import glob
import base64
import datetime
import re

# ==========================================
# 1. 웹사이트 기본 설정
# ==========================================
st.set_page_config(page_title="자격증 문제풀이 CBT", page_icon="🎓", layout="centered")

FILE_PILDAP = "산업안전기사_실기_문제은행.xlsx"
FILE_JAKUP = "산업안전기사_작업형_문제은행.xlsx"
FILE_SOBANG_PILGI = "소방설비기사_필기_문제은행.xlsx"
FILE_SOBANG_SILGI = "소방설비기사_실기_문제은행.xlsx"
STATS_FILE = "stats.json" 
GUESTBOOK_FILE = "guestbook.json"

# ==========================================
# ⚙️ 똑똑한 이미지 크기 조절
# ==========================================
st.markdown("""
<style>
    .cbt-img-box {
        width: 100%;
        display: flex;
        justify-content: center;
        margin: 15px 0;
    }
    .cbt-img-box img {
        max-width: 100%;  
        height: auto;     
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        box-shadow: 1px 1px 3px rgba(0,0,0,0.1);
    }
    .stButton button { margin-bottom: 0px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ⚙️ 확장자 무시 & 통합 폴더 탐색
# ==========================================
def find_image_path(filename):
    filename = str(filename).strip()
    if not filename or filename.lower() == 'nan': return None
    base_name = os.path.splitext(filename)[0]
    extensions = ['', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.PNG', '.JPG', '.JPEG']
    search_folders = ["사진폴더", "실습형사진폴더", "소방설비기사필기사진", "소방설비기사실기사진"]

    for folder in search_folders:
        if not os.path.exists(folder): continue
        for ext in extensions:
            target_name = base_name + ext
            for root, _, files in os.walk(folder):
                for f in files:
                    if f.lower() == target_name.lower():
                        return os.path.join(root, f)
            
    for root, _, files in os.walk("."):
        if ".git" in root or "venv" in root: continue
        for ext in extensions:
            target_name = base_name + ext
            for f in files:
                if f.lower() == target_name.lower():
                    return os.path.join(root, f)
    return None

# 💡 에러 메시지 없이 조용히 넘어가는 기능 추가 (텍스트 해설과 겹칠 때 대비)
def get_images_html(img_names_raw, show_error=False):
    if pd.isna(img_names_raw): return ""
    img_names_raw = str(img_names_raw).strip()
    if not img_names_raw or img_names_raw.lower() == 'nan': return ""
    
    # 엑셀 숫자 .0 꼬리표 제거
    if re.match(r'^\d+\.0$', img_names_raw): img_names_raw = img_names_raw[:-2]

    img_html = ""
    img_names = [name.strip() for name in img_names_raw.replace(';', ',').split(',') if name.strip()]
    for img_name in img_names:
        img_path = find_image_path(img_name)
        if img_path:
            with open(img_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode()
            img_html += f'<div class="cbt-img-box"><img src="data:image/png;base64,{encoded_string}"></div>'
        elif show_error:
            img_html += f'<div style="color: red; text-align: center; margin-top: 10px; font-weight: bold;">🚨 이미지 없음: {img_name}</div>'
    return img_html

# ==========================================
# ⚙️ 데이터 및 조회수 관리 로직
# ==========================================
def load_guestbook():
    if os.path.exists(GUESTBOOK_FILE):
        try:
            with open(GUESTBOOK_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: return []
    return []

def save_guestbook(entries):
    with open(GUESTBOOK_FILE, 'w', encoding='utf-8') as f: json.dump(entries, f, ensure_ascii=False, indent=2)

def get_client_ip():
    ip = "Guest"
    try:
        if hasattr(st, 'context') and hasattr(st.context, 'headers'):
            x_forwarded = st.context.headers.get("X-Forwarded-For")
            if x_forwarded: ip = x_forwarded.split(',')[0].strip()
    except: pass
    safe_ip = "".join(c for c in ip if c.isalnum() or c in ".-_")
    return safe_ip if safe_ip else "Guest"

def load_stats():
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    default_stats = {"total_visits": 0, "today_visits": 0, "last_date": today_str, "today_ips": []}
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f: 
                stats = json.load(f)
                if stats.get("last_date") != today_str:
                    stats["today_visits"] = 0
                    stats["last_date"] = today_str
                    stats["today_ips"] = []
                if "today_ips" not in stats:
                    stats["today_ips"] = []
                return stats
        except: return default_stats
    return default_stats

def increment_visits(ip):
    stats = load_stats()
    if ip not in stats["today_ips"]:
        stats["today_ips"].append(ip)
        stats["total_visits"] += 1
        stats["today_visits"] += 1
        with open(STATS_FILE, 'w', encoding='utf-8') as f: 
            json.dump(stats, f, ensure_ascii=False, indent=2)

def load_history():
    history_file = f"{st.session_state.nickname}_학습기록.json"
    st.session_state.history = {} 
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if loaded and isinstance(loaded, dict): st.session_state.history = loaded
        except: pass

def save_history(question_text, is_correct):
    if not isinstance(st.session_state.get('history'), dict): st.session_state.history = {}
    if question_text not in st.session_state.history:
        st.session_state.history[question_text] = {"correct": 0, "incorrect": 0}
    if is_correct: st.session_state.history[question_text]["correct"] += 1
    else: st.session_state.history[question_text]["incorrect"] += 1
    history_file = f"{st.session_state.nickname}_학습기록.json"
    with open(history_file, 'w', encoding='utf-8') as f: json.dump(st.session_state.history, f, ensure_ascii=False, indent=2)

def save_incorrect_answer(row):
    note_filename = f"{st.session_state.nickname}_오답노트.xlsx"
    df_new = pd.DataFrame([row])
    if os.path.exists(note_filename):
        df_old = pd.read_excel(note_filename)
        if row['문제'] not in df_old['문제'].values:
            df_combined = pd.concat([df_old, df_new], ignore_index=True)
            df_combined.to_excel(note_filename, index=False)
    else: df_new.to_excel(note_filename, index=False)

def remove_from_incorrect_note(question_text):
    note_filename = f"{st.session_state.nickname}_오답노트.xlsx"
    if os.path.exists(note_filename):
        df_old = pd.read_excel(note_filename)
        df_new = df_old[df_old['문제'] != question_text]
        if df_new.empty: 
            if os.path.exists(note_filename): os.remove(note_filename)
        else: df_new.to_excel(note_filename, index=False)

def is_bookmarked(question_text):
    mark_filename = f"{st.session_state.nickname}_즐겨찾기.xlsx"
    if not os.path.exists(mark_filename): return False
    try:
        df_mark = pd.read_excel(mark_filename)
        return question_text in df_mark['문제'].values
    except: return False

def toggle_bookmark(row):
    mark_filename = f"{st.session_state.nickname}_즐겨찾기.xlsx"
    q_text = row['문제']
    df_new_row = pd.DataFrame([row])
    if os.path.exists(mark_filename):
        df_old = pd.read_excel(mark_filename)
        if q_text in df_old['문제'].values:
            df_new = df_old[df_old['문제'] != q_text]
            if df_new.empty: 
                if os.path.exists(mark_filename): os.remove(mark_filename)
            else: df_new.to_excel(mark_filename, index=False)
            return False 
        else:
            df_combined = pd.concat([df_old, df_new_row], ignore_index=True)
            df_combined.to_excel(mark_filename, index=False)
            return True 
    else:
        df_new_row.to_excel(mark_filename, index=False)
        return True

def get_question_point(df, index):
    row = df.iloc[index]
    for col_name in ['점수', '배점']:
        if col_name in df.columns and pd.notna(row[col_name]):
            try: return int(row[col_name])
            except: pass
    return 5 

def calculate_total_possible_score(df):
    total = 0
    for i in range(len(df)): total += get_question_point(df, i)
    return total

def init_quiz_state(df, is_mock, is_review, is_bookmark, cert_type=None, exam_type=None, study_mode="문제풀이"):
    st.session_state.df = df
    st.session_state.total_possible_score = calculate_total_possible_score(df)
    st.session_state.index = 0
    st.session_state.user_answers = {} 
    st.session_state.show_answer = False
    st.session_state.clicked_opt = None 
    st.session_state.is_mock_exam = is_mock
    st.session_state.is_review_mode = is_review
    st.session_state.is_bookmark_mode = is_bookmark
    st.session_state.cert_type = cert_type
    st.session_state.exam_type = exam_type
    st.session_state.study_mode = study_mode
    st.session_state.start_time = time.time()
    st.session_state.page = 'quiz'

# ==========================================
# 🛠️ 세션 상태 초기화
# ==========================================
client_ip = get_client_ip()

keys_to_init = [
    'page', 'df', 'index', 'total_possible_score', 'user_answers',
    'show_answer', 'start_time', 'is_review_mode', 'is_bookmark_mode', 
    'is_mock_exam', 'has_visited', 'cert_type', 'exam_type',
    'clicked_opt', 'study_mode', 'is_admin', 'nickname'
]
for key in keys_to_init:
    if key not in st.session_state: st.session_state[key] = None

MY_IPS = ["192.168.1.240", "192.168.0.171"]

if st.query_params.get("admin") == "vip" or client_ip in MY_IPS:
    st.session_state.nickname = "펭귄주인장"
    st.session_state.is_admin = True
else:
    if st.session_state.nickname is None or st.session_state.nickname == "펭귄주인장":
        st.session_state.nickname = client_ip
    st.session_state.is_admin = False

if not isinstance(st.session_state.get('history'), dict):
    st.session_state.history = {}
if st.session_state.user_answers is None: st.session_state.user_answers = {}

if st.session_state.page is None or st.session_state.page == 'login': 
    st.session_state.page = 'selection'
    load_history()

if st.session_state.has_visited is None: st.session_state.has_visited = False
if not st.session_state.has_visited:
    if not st.session_state.is_admin:
        increment_visits(client_ip)
    st.session_state.has_visited = True

# ==========================================
# ⭐ 화면 1: 단원 선택 화면
# ==========================================
if st.session_state.page == 'selection':
    st.markdown("<h1 style='text-align: center;'>🎓 자격증 문제풀이 CBT</h1>", unsafe_allow_html=True)
    
    st.markdown("""
    <div style="background-color: #f8f9fa; padding: 18px; border-radius: 12px; border-left: 6px solid #3498db; margin-bottom: 25px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
        <strong style="color: #2c3e50; font-size: 16px;">🎯 여러분의 합격을 진심으로 기원합니다!</strong><br>
        <span style="color: #555; font-size: 14px;">본 사이트는 개발자가 자격증을 직접 공부하기 위해 제작한 <b>개인 학습용 플랫폼</b>입니다.<br>관련 학습 자료나 소통을 원하시면 언제든 블로그에 방문해 주세요.</span><br>
        👉 <a href="https://blog.naver.com/jeaha_" target="_blank" style="color: #2980b9; font-weight: bold; text-decoration: none;">펭귄주인장 블로그 방문하기</a>
    </div>
    """, unsafe_allow_html=True)
    
    stats = load_stats()
    admin_tag = "👑 펭귄주인장 접속중" if st.session_state.is_admin else f"접속 기기 IP: {st.session_state.nickname}"
    
    st.markdown(f"""
    <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; border-bottom: 1px solid #eee; padding-bottom: 10px;'>
        <div style='color:gray; font-size:13px;'>{admin_tag}</div>
        <div style='font-size:14px; font-weight:bold; color:#2c3e50;'>
            📈 Today <span style='color:#e74c3c;'>{stats['today_visits']}</span> / Total <span style='color:#3498db;'>{stats['total_visits']}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    cert_type = st.radio("📚 자격증 선택", ["🚧 산업안전기사", "🔥 소방설비기사(전기)"], horizontal=True)
    
    if "소방설비기사" in cert_type:
        exam_type = st.radio("📝 시험 유형 선택", ["📖 필기 (객관식)", "✍️ 실기 (주관식/서술)"], horizontal=True)
        
        if "필기" in exam_type:
            st.markdown("---")
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                study_mode = st.radio("🛠️ 학습 모드 설정", ["💡 문제풀이 모드", "⏱️ 실제시험 모드"], help="문제풀이 모드는 정답을 바로 확인하고, 실제시험 모드는 제출 후에 확인합니다.")
            with col_m2:
                target_subject = st.selectbox("📖 과목 선택", ["전체 과목 (80문제)", "1과목: 소방원론", "2과목: 소방전기회로", "3과목: 소방관계법규", "4과목: 소방전기시설의 구조 및 원리"])
            target_file = FILE_SOBANG_PILGI
        else:
            study_mode = "💡 문제풀이 모드"
            target_subject = "전체"
            target_file = FILE_SOBANG_SILGI
            st.write("")
    else:
        exam_type = st.radio("📝 시험 유형 선택", ["✍️ 필답형 (주관식/서술)", "💻 작업형 (동영상/도면)"], horizontal=True)
        target_file = FILE_PILDAP if "필답형" in exam_type else FILE_JAKUP
        study_mode = "💡 문제풀이 모드"
        target_subject = "전체"

    if not os.path.exists(target_file):
        st.error(f"⚠️ '{target_file}' 파일이 없습니다!"); st.stop()
        
    xls = pd.ExcelFile(target_file)
    sheet_names = xls.sheet_names
    is_shuffle = st.checkbox("🔀 문제 순서 랜덤하게 섞기", value=False)
    
    def start_new_quiz(target_sheet, current_file, current_cert, current_exam, mode, subject):
        df = pd.read_excel(current_file, sheet_name=target_sheet)
        df.columns = df.columns.str.replace(' ', '')
        if '출처' not in df.columns: df['출처'] = target_sheet 
        
        df['원본번호'] = range(1, len(df) + 1)
        
        if "소방설비기사" in current_cert and "필기" in current_exam:
            if "1과목" in subject: df = df.iloc[0:20]
            elif "2과목" in subject: df = df.iloc[20:40]
            elif "3과목" in subject: df = df.iloc[40:60]
            elif "4과목" in subject: df = df.iloc[60:80]
        
        if is_shuffle: df = df.sample(frac=1).reset_index(drop=True)
        is_mock = any(kw in target_sheet for kw in ["년", "회", "기출", "과년도"])
        init_quiz_state(df, is_mock, False, False, current_cert, current_exam, mode)
        st.rerun()

    st.write("---")
    selected_sheet = st.selectbox("📚 회차(단원) 선택", sheet_names)
    if st.button("문제 풀기 🚀", use_container_width=True, type="primary"): 
        start_new_quiz(selected_sheet, target_file, cert_type, exam_type, study_mode, target_subject)
                
    st.write("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📝 내 오답노트 풀기", use_container_width=True):
            note_file = f"{st.session_state.nickname}_오답노트.xlsx"
            if not os.path.exists(note_file): st.warning("오답이 없습니다!")
            else:
                df = pd.read_excel(note_file); df.columns = df.columns.str.replace(' ', '')
                df['원본번호'] = range(1, len(df) + 1)
                if is_shuffle: df = df.sample(frac=1).reset_index(drop=True)
                init_quiz_state(df, False, True, False, "오답노트", "종합", "💡 문제풀이 모드"); st.rerun()
    with col2:
        if st.button("⭐ 내 즐겨찾기 풀기", use_container_width=True):
            mark_file = f"{st.session_state.nickname}_즐겨찾기.xlsx"
            if not os.path.exists(mark_file): st.warning("즐겨찾기가 없습니다!")
            else:
                df = pd.read_excel(mark_file); df.columns = df.columns.str.replace(' ', '')
                df['원본번호'] = range(1, len(df) + 1)
                if is_shuffle: df = df.sample(frac=1).reset_index(drop=True)
                init_quiz_state(df, False, False, True, "즐겨찾기", "종합", "💡 문제풀이 모드"); st.rerun()

    st.write("---")
    with st.expander("💬 방문자 방명록"):
        entries = load_guestbook()
        for entry in reversed(entries[-15:]):
            st.markdown(f'<div style="background-color:#f9f9f9; padding:10px; border-radius:8px; margin-bottom:5px;">👤 {entry["name"]} | {entry["time"]}<br>{entry["msg"]}</div>', unsafe_allow_html=True)
        new_msg = st.text_input("방명록 작성", placeholder="응원 한마디 부탁드려요!", label_visibility="collapsed")
        if st.button("✏️ 남기기", use_container_width=True):
            if new_msg.strip():
                writer_name = "👑 펭귄주인장" if st.session_state.is_admin else f"익명({st.session_state.nickname[:5]})"
                entries.append({"name": writer_name, "msg": new_msg.strip(), "time": datetime.datetime.now().strftime("%m-%d %H:%M")})
                save_guestbook(entries); st.rerun()

# ==========================================
# ⭐ 화면 2: 퀴즈 화면 
# ==========================================
elif st.session_state.page == 'quiz':
    df, idx = st.session_state.df, st.session_state.index
    if idx >= len(df): st.session_state.page = 'result'; st.rerun()
    row = df.iloc[idx]; q_text = row['문제']
    
    c_prev, c_mark, c_submit, c_home = st.columns([1, 1, 1.5, 1])
    with c_prev:
        if st.button("◀ 이전", use_container_width=True): 
            st.session_state.index = max(0, idx - 1)
            st.session_state.show_answer = False; st.session_state.clicked_opt = None; st.rerun()
    with c_mark:
        bookmarked = is_bookmarked(q_text)
        if st.button("🌟 저장" if bookmarked else "⭐ 저장", type="primary" if bookmarked else "secondary", use_container_width=True): toggle_bookmark(row); st.rerun() 
    with c_submit:
        if st.button("🏁 시험 제출", use_container_width=True): st.session_state.page = 'result'; st.rerun()
    with c_home:
        if st.button("🏠 홈", use_container_width=True): st.session_state.page = 'selection'; st.rerun()
            
    st.progress((idx + 1) / len(df))
    
    with st.expander(f"🗺️ 전체 문제 이동판 펼쳐보기 (현재 {idx+1}/{len(df)}번)"):
        cols = st.columns(8) 
        for i in range(len(df)):
            ans_status = st.session_state.user_answers.get(i)
            icon = "⬜"
            if ans_status is True: icon = "✅"
            elif ans_status is False: icon = "❌"
            elif st.session_state.study_mode == "⏱️ 실제시험 모드" and ans_status is not None: icon = "🟦"
            if i == idx: icon = "📍"
            if cols[i % 8].button(f"{icon} {i+1}", key=f"grid_btn_{i}", use_container_width=True):
                st.session_state.index = i; st.session_state.show_answer = False; st.session_state.clicked_opt = None; st.rerun()
                
    subject_badge = ""
    if st.session_state.cert_type == "🔥 소방설비기사(전기)" and "필기" in st.session_state.exam_type:
        orig_q_num = int(row.get('원본번호', idx + 1))
        if 1 <= orig_q_num <= 20: subj = "1과목: 소방원론"
        elif 21 <= orig_q_num <= 40: subj = "2과목: 소방전기회로"
        elif 41 <= orig_q_num <= 60: subj = "3과목: 소방관계법규"
        else: subj = "4과목: 소방전기시설의 구조 및 원리"
        subject_badge = f"<span style='background-color:#e74c3c; color:white; padding:4px 10px; border-radius:6px; font-size:12px; font-weight:bold;'>{subj}</span>"
        
    st.markdown(f"<br>{subject_badge}<h3 style='margin-top:5px;'>{q_text}</h3>", unsafe_allow_html=True)
    
    # [보기] 및 [화면설명] 완벽 줄바꿈 지원
    bogi_col = next((c for c in ['참고', '보기', '[보기]'] if c in df.columns), None)
    bogi_raw = str(row[bogi_col]).strip() if bogi_col and pd.notna(row.get(bogi_col)) else ""
    if bogi_raw.lower() == 'nan': bogi_raw = ""
    
    desc_col = next((c for c in ['그림설명', '화면설명', '동영상설명'] if c in df.columns), None)
    desc_text = str(row[desc_col]).strip() if desc_col and pd.notna(row.get(desc_col)) else ""
    if desc_text.lower() == 'nan': desc_text = ""

    if bogi_raw:
        if '\n' not in bogi_raw and find_image_path(bogi_raw):
            st.markdown(get_images_html(bogi_raw), unsafe_allow_html=True)
        else:
            bogi_html = bogi_raw.replace('\n', '<br>')
            st.markdown(f'<div style="background-color: white; padding: 20px; border-radius: 8px; border: 2px solid #bdc3c7; color: #2c3e50; font-size: 15px; margin-bottom: 15px;"><strong>[보기]</strong><br><br>{bogi_html}</div>', unsafe_allow_html=True)

    if desc_text:
        desc_html = desc_text.replace('\n', '<br>')
        st.markdown(f'<div style="background-color: #eaf2f8; padding: 15px; border-radius: 8px; border-left: 5px solid #3498db; margin-bottom: 15px; color: #2c3e50; font-size: 15px; line-height: 1.6;">🎬 <strong>[화면 설명]</strong><br>{desc_html}</div>', unsafe_allow_html=True)

    raw_opts = str(row.get('객관식보기', '')).strip()
    is_img_opts = False; opts_list = []
    if raw_opts and raw_opts.lower() != 'nan':
        if '\n' not in raw_opts and find_image_path(raw_opts):
            is_img_opts = True; opts_list = ["①", "②", "③", "④"]
        else: opts_list = [opt.strip() for opt in raw_opts.split('\n') if opt.strip()]

    if is_img_opts: st.markdown(get_images_html(raw_opts), unsafe_allow_html=True)

    img_col = next((c for c in ['문제이미지', '사진', '그림'] if c in df.columns), None)
    if img_col: st.markdown(get_images_html(row.get(img_col)), unsafe_allow_html=True)

    ans_val = str(row.get('정답', '')).strip().replace(".0", "")
    
    def go_next(is_correct):
        save_history(q_text, is_correct); st.session_state.user_answers[idx] = is_correct 
        if is_correct and st.session_state.is_review_mode: remove_from_incorrect_note(q_text)
        elif not is_correct and not st.session_state.is_review_mode: save_incorrect_answer(row)
        st.session_state.index += 1; st.session_state.show_answer = False; st.session_state.clicked_opt = None; st.rerun()

    if st.session_state.study_mode == "💡 문제풀이 모드":
        if st.session_state.clicked_opt is None and not st.session_state.show_answer:
            if opts_list:
                for i, opt in enumerate(opts_list):
                    if st.button(opt, key=f"opt_{i}_{idx}", use_container_width=True):
                        st.session_state.clicked_opt = i
                        if str(i+1) == ans_val: st.toast("🎉 정답!")
                        else: st.session_state.show_answer = True
                        st.rerun()
            else:
                if st.button("👀 정답 및 해설 보기", use_container_width=True): st.session_state.show_answer = True; st.rerun()
        
        if st.session_state.clicked_opt is not None:
            for i, opt in enumerate(opts_list):
                if str(i+1) == ans_val: st.success(f"{opt} (✅ 정답)")
                elif i == st.session_state.clicked_opt: st.error(f"{opt} (❌ 오답)")
                else: st.markdown(f'<div style="color:gray; padding:10px; border:1px solid #eee; border-radius:5px; margin-bottom:5px;">{opt}</div>', unsafe_allow_html=True)
            if str(st.session_state.clicked_opt + 1) == ans_val:
                if st.button("다음 문제로 ➔", type="primary", use_container_width=True): go_next(True)
    
    else: 
        current_choice = st.session_state.user_answers.get(idx)
        for i, opt in enumerate(opts_list):
            is_selected = (current_choice == i+1)
            if st.button(opt, key=f"exam_opt_{i}_{idx}", use_container_width=True, type="primary" if is_selected else "secondary"):
                st.session_state.user_answers[idx] = i+1
                st.rerun()
        
        c_prev_btn, c_next_btn = st.columns(2)
        with c_prev_btn:
            if st.button("이전 문제", use_container_width=True): st.session_state.index -= 1; st.rerun()
        with c_next_btn:
            if st.button("다음 문제", type="primary", use_container_width=True): st.session_state.index += 1; st.rerun()

    # 💡 [핵심] 해설 파트 줄바꿈 보장 & 이미지 파일명 중복 텍스트 출력 방지
    if st.session_state.show_answer:
        st.divider()
        ans_text_html = ""
        ans_imgs_html = ""
        seen_texts = set()
        seen_imgs = set()

        is_first_text = True
        for c in ['정답', '답', '해설', '설명', '해설이미지', '해설사진', '해답ㆍ해설', '해답·해설']:
            if st.session_state.clicked_opt is not None and c in ['정답', '답']: continue
            if c in df.columns and pd.notna(row.get(c)):
                val = str(row[c]).strip()
                if val.lower() == 'nan' or not val: continue
                
                # float ".0" 이슈 수정
                if re.match(r'^\d+\.0$', val): val = val[:-2]

                parts = [p.strip() for p in val.replace(';', ',').split(',') if p.strip()]
                all_found = True
                found_paths = []
                for p in parts:
                    path = find_image_path(p)
                    if path: found_paths.append(p)
                    else: all_found = False
                
                if parts and all_found:
                    # 100% 이미지 파일명일 때 (텍스트로 출력 방지)
                    for p in found_paths:
                        if p not in seen_imgs:
                            ans_imgs_html += get_images_html(p, show_error=False)
                            seen_imgs.add(p)
                else:
                    # 일반 텍스트 해설일 때 (줄바꿈 허용)
                    if val not in seen_texts:
                        val_html = val.replace('\n', '<br>')
                        if not is_first_text and c in ['해설', '설명', '해답ㆍ해설', '해답·해설']:
                            ans_text_html += "<br><br><strong>[해설]</strong><br>"
                        ans_text_html += f"{val_html}"
                        seen_texts.add(val)
                        is_first_text = False
                        
        if ans_text_html:
            st.markdown(f'<div style="background-color: #e8f4f8; padding: 15px; border-radius: 8px; color: #1e5266; margin-bottom: 15px; font-size: 15px; line-height: 1.6;">💡 <strong>정답 및 해설</strong><br><br>{ans_text_html}</div>', unsafe_allow_html=True)
            
        if ans_imgs_html:
            st.markdown(ans_imgs_html, unsafe_allow_html=True)
        
        if st.session_state.clicked_opt is not None:
            if st.button("해설 확인 완료! 다음 문제로 ➔", type="primary", use_container_width=True): go_next(False)
        else:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("⭕ 정답", use_container_width=True): go_next(True)
            with c2:
                if st.button("❌ 오답", use_container_width=True): go_next(False)

# ==========================================
# 화면 3: 결과 대시보드 
# ==========================================
elif st.session_state.page == 'result':
    st.title("🎉 학습 완료!"); st.balloons()
    
    grading_results = {}
    
    if st.session_state.study_mode == "⏱️ 실제시험 모드":
        correct_count = 0
        for i in range(len(st.session_state.df)):
            user_pick = st.session_state.user_answers.get(i)
            actual_ans = str(st.session_state.df.iloc[i].get('정답', '')).strip().replace(".0", "")
            if str(user_pick) == actual_ans:
                correct_count += 1
                grading_results[i] = True 
            else:
                grading_results[i] = False
                save_incorrect_answer(st.session_state.df.iloc[i])
        correct = correct_count
    else:
        correct = sum(1 for v in st.session_state.user_answers.values() if v is True)
        grading_results = st.session_state.user_answers.copy()
        
    total_q = len(st.session_state.df)
    mins, secs = divmod(int(time.time() - st.session_state.start_time), 60)
    st.subheader(f"⏱️ 소요 시간: {mins}분 {secs}초")
    
    if st.session_state.cert_type == "🔥 소방설비기사(전기)" and "필기" in st.session_state.exam_type:
        subj_names = ["1과목: 소방원론", "2과목: 소방전기회로", "3과목: 소방관계법규", "4과목: 소방전기시설의 구조 및 원리"]
        subj_correct = [0, 0, 0, 0]; subj_total = [0, 0, 0, 0]
        
        for i in range(total_q):
            row = st.session_state.df.iloc[i]
            orig_q_num = int(row.get('원본번호', i + 1))
            s_idx = min((orig_q_num - 1) // 20, 3)
            
            subj_total[s_idx] += 1
            if grading_results.get(i) is True: subj_correct[s_idx] += 1

        subj_scores = [int((c / t * 100) if t > 0 else 0) for c, t in zip(subj_correct, subj_total)]
        active_subjs = [s for s in subj_scores if s > 0 or any(t > 0 for t in subj_total)]
        avg_score = sum(subj_scores) / len([t for t in subj_total if t > 0]) if len([t for t in subj_total if t > 0]) > 0 else 0
        
        is_fail = any(s < 40 for i, s in enumerate(subj_scores) if subj_total[i] > 0)
        is_pass = (avg_score >= 60) and not is_fail

        if is_pass: st.success(f"🎊 합격입니다! (평균 {avg_score:.1f}점)")
        else: st.error(f"⚠️ 불합격입니다. ({'과락 발생' if is_fail else '평균 미달'}, 평균 {avg_score:.1f}점)")

        for i in range(4):
            if subj_total[i] == 0: continue
            st.write(f"**{subj_names[i]}**: {subj_scores[i]}점 ({subj_correct[i]}/{subj_total[i]}) {'🚨 과락' if subj_scores[i] < 40 else '✅ 통과'}")
    else:
        st.metric("🎯 정답률", f"{(correct/total_q*100):.1f}%" if total_q > 0 else "0.0%")
    
    st.write("---")

    if st.session_state.study_mode == "⏱️ 실제시험 모드":
        st.subheader("📝 상세 채점 결과 및 해설 복습")
        st.caption("틀린 문제들을 바로 복습하고 내 선택과 정답을 확인하세요!")
        
        for i in range(total_q):
            row = st.session_state.df.iloc[i]
            q_text = row['문제']
            user_pick = st.session_state.user_answers.get(i, "미선택")
            actual_ans = str(row.get('정답', '')).strip().replace(".0", "")
            is_corr = grading_results.get(i, False)
            
            icon = "✅" if is_corr else "❌"
            
            with st.expander(f"{icon} {i+1}번: {q_text[:35]}..."):
                st.markdown(f"**{q_text}**")
                
                img_col = next((c for c in ['문제이미지', '사진', '그림'] if c in st.session_state.df.columns), None)
                if img_col and pd.notna(row.get(img_col)):
                    st.markdown(get_images_html(row.get(img_col)), unsafe_allow_html=True)
                
                raw_opts = str(row.get('객관식보기', '')).strip()
                if raw_opts and raw_opts.lower() != 'nan':
                    if '\n' not in raw_opts and find_image_path(raw_opts):
                        st.markdown(get_images_html(raw_opts), unsafe_allow_html=True)
                    else:
                        raw_opts_html = raw_opts.replace('\n', '<br>')
                        st.markdown(f'<div style="background-color: white; padding: 15px; border-radius: 8px; border: 1px solid #ccc; margin-bottom: 10px;">{raw_opts_html}</div>', unsafe_allow_html=True)
                
                st.markdown("---")
                c1, c2 = st.columns(2)
                c1.markdown(f"🙋‍♂️ **내 선택:** {user_pick}번" if user_pick != "미선택" else "🙋‍♂️ **내 선택:** 미선택")
                c2.markdown(f"🎯 **실제 정답:** {actual_ans}번")
                
                # 결과창 상세 해설 로직 완벽 동기화
                ans_text_html = ""
                ans_imgs_html = ""
                seen_texts = set()
                seen_imgs = set()

                is_first_text = True
                for c in ['해설', '설명', '해설이미지', '해설사진', '해답ㆍ해설', '해답·해설']:
                    if c in st.session_state.df.columns and pd.notna(row.get(c)):
                        val = str(row[c]).strip()
                        if val.lower() == 'nan' or not val: continue
                        
                        if re.match(r'^\d+\.0$', val): val = val[:-2]

                        parts = [p.strip() for p in val.replace(';', ',').split(',') if p.strip()]
                        all_found = True
                        found_paths = []
                        for p in parts:
                            path = find_image_path(p)
                            if path: found_paths.append(p)
                            else: all_found = False
                        
                        if parts and all_found:
                            for p in found_paths:
                                if p not in seen_imgs:
                                    ans_imgs_html += get_images_html(p, show_error=False)
                                    seen_imgs.add(p)
                        else:
                            if val not in seen_texts:
                                val_html = val.replace('\n', '<br>')
                                if not is_first_text:
                                    ans_text_html += "<br><br><strong>[해설]</strong><br>"
                                ans_text_html += f"{val_html}"
                                seen_texts.add(val)
                                is_first_text = False
                                
                if ans_text_html or ans_imgs_html:
                    st.info("💡 **해설**")
                    if ans_text_html:
                        st.markdown(f"{ans_text_html}", unsafe_allow_html=True)
                    if ans_imgs_html:
                        st.markdown(ans_imgs_html, unsafe_allow_html=True)
    
    st.write("---")
    if st.button("🏠 홈으로 돌아가기", use_container_width=True): st.session_state.page = 'selection'; st.rerun()

st.markdown("""
    <br><br><br>
    <p style='text-align: center; color: gray; font-size: 11px;'>
        © 2026 Designed by [펭귄주인장]. 무단 복제 및 상업적 배포 금지.<br>
        🌐 <a href='https://blog.naver.com/jeaha_' target='_blank' style='color: #888; text-decoration: none;'>펭귄주인장 블로그 방문하기</a>
    </p>
""", unsafe_allow_html=True)