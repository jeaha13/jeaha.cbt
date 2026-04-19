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

# ==========================================
# 1. 웹사이트 기본 설정
# ==========================================
st.set_page_config(page_title="산업안전기사 마스터 CBT", page_icon="🚧", layout="centered")

# ⭐ 파일 분리 (필답형 vs 작업형)
FILE_PILDAP = "산업안전기사_실기_문제은행.xlsx"
FILE_JAKUP = "산업안전기사_작업형_문제은행.xlsx"  # 우리가 만든 엑셀 파일 이름으로 변경해서 쓰셔도 됩니다.
STATS_FILE = "stats.json" 
GUESTBOOK_FILE = "guestbook.json"

# ==========================================
# ⚙️ 이미지 자연스러운 핏(Natural Fit) 도우미
# ==========================================
def get_images_html(img_names_raw):
    if pd.isna(img_names_raw): return ""
    img_names_raw = str(img_names_raw).strip()
    if not img_names_raw or img_names_raw.lower() == 'nan': return ""
    
    img_html = ""
    img_names = [name.strip() for name in img_names_raw.replace(';', ',').split(',') if name.strip()]
    for img_name in img_names:
        img_path = os.path.join("사진폴더", img_name)
        if os.path.exists(img_path):
            with open(img_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode()
            img_html += f'<div style="display: flex; justify-content: center; margin-top: 15px; margin-bottom: 15px;"><img src="data:image/png;base64,{encoded_string}" style="max-width: 100%; height: auto; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 1px 1px 3px rgba(0,0,0,0.1);"></div>'
        else:
            img_html += f'<div style="color: red; text-align: center; margin-top: 10px;">이미지 없음: {img_path}</div>'
    return img_html

# ==========================================
# ⚙️ 방명록 및 데이터 관리 도우미
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
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {"total_visits": 0}
    return {"total_visits": 0}

def increment_visits():
    stats = load_stats()
    stats["total_visits"] = stats.get("total_visits", 0) + 1
    with open(STATS_FILE, 'w', encoding='utf-8') as f: json.dump(stats, f)

def load_history():
    history_file = f"{st.session_state.nickname}_학습기록.json"
    st.session_state.history = {} 
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if loaded and isinstance(loaded, dict): 
                    st.session_state.history = loaded
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

def init_quiz_state(df, is_mock, is_review, is_bookmark):
    st.session_state.df = df
    st.session_state.total_possible_score = calculate_total_possible_score(df)
    st.session_state.index = 0
    st.session_state.user_answers = {} 
    st.session_state.show_answer = False
    st.session_state.is_mock_exam = is_mock
    st.session_state.is_review_mode = is_review
    st.session_state.is_bookmark_mode = is_bookmark
    st.session_state.start_time = time.time()
    st.session_state.page = 'quiz'

# ==========================================
# ⭐ 세션 상태 초기화
# ==========================================
keys_to_init = [
    'page', 'df', 'index', 'total_possible_score', 'user_answers',
    'show_answer', 'start_time', 'is_review_mode', 'is_bookmark_mode', 
    'is_mock_exam', 'has_visited', 'is_admin'
]
for key in keys_to_init:
    if key not in st.session_state: st.session_state[key] = None

if st.session_state.is_admin is None: st.session_state.is_admin = False
if 'nickname' not in st.session_state or st.session_state.nickname is None:
    st.session_state.nickname = get_client_ip()
if not isinstance(st.session_state.get('history'), dict):
    st.session_state.history = {}
if st.session_state.user_answers is None: st.session_state.user_answers = {}

if st.session_state.page is None or st.session_state.page == 'login': 
    st.session_state.page = 'selection'
    load_history()

if st.session_state.has_visited is None: st.session_state.has_visited = False
if not st.session_state.has_visited:
    increment_visits()
    st.session_state.has_visited = True

# ==========================================
# 👑 사이드바 및 대시보드
# ==========================================
with st.sidebar:
    st.caption("⚙️ 사이트 설정")
    admin_pw = st.text_input("관리자 코드", type="password")
    if admin_pw == "산업안전기사1회!":
        if not st.session_state.is_admin:
            st.session_state.is_admin = True
            st.session_state.nickname = "펭귄주인장"
            load_history()
            st.toast("👑 최고 관리자 권한 활성화!")
        st.success("관리자 모드 접속 중")
        if st.button("👑 대시보드 열기", use_container_width=True):
            st.session_state.page = 'admin_dashboard'
            st.rerun()
    else:
        if st.session_state.is_admin:
            st.session_state.is_admin = False
            st.session_state.nickname = get_client_ip()
            load_history()

if st.session_state.page == 'admin_dashboard' and st.session_state.is_admin:
    st.title(f"👑 펭귄주인장님의 대시보드")
    stats = load_stats()
    ip_users = len(glob.glob("*_학습기록.json"))
    col1, col2 = st.columns(2)
    with col1: st.metric(label="👁️ 총 누적 문제풀이 횟수", value=f"{stats.get('total_visits', 0)} 회")
    with col2: st.metric(label="👥 문제를 푼 기기(IP) 수", value=f"{ip_users} 대")
    st.write("---")
    
    st.subheader("💾 서버 초기화 방어 센터 (백업/복구)")
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in glob.glob("*.json"): zf.write(f)
        for f in glob.glob("*_오답노트.xlsx"): zf.write(f)
        for f in glob.glob("*_즐겨찾기.xlsx"): zf.write(f)
    st.download_button("📥 모든 데이터 백업 (ZIP)", data=zip_buffer.getvalue(), file_name="cbt_all_backup.zip", mime="application/zip", use_container_width=True, type="primary")
    
    uploaded_zip = st.file_uploader("📤 ZIP 파일 복구하기", type="zip")
    if uploaded_zip is not None:
        with zipfile.ZipFile(uploaded_zip, "r") as zf:
            zf.extractall()
        st.success("✅ 완벽하게 복구되었습니다! F5를 눌러주세요.")
        
    st.write("---")
    st.subheader("💬 방명록 관리")
    if st.button("🗑️ 방명록 전체 싹 지우기", type="secondary"):
        save_guestbook([])
        st.success("방명록이 깨끗하게 초기화되었습니다.")

    st.write("---")
    if st.button("나도 문제 풀러 가기 🚀", use_container_width=True):
        st.session_state.page = 'selection'
        st.rerun()

# ==========================================
# ⭐ 화면 1: 단원 선택 화면
# ==========================================
elif st.session_state.page == 'selection':
    st.markdown("<h1 style='text-align: center;'>🚧 산업안전기사 마스터 CBT</h1>", unsafe_allow_html=True)
    if st.session_state.is_admin: st.info("👑 현재 관리자 권한으로 접속 중입니다.")
    else: st.caption(f"접속 기기 IP: {st.session_state.nickname}")
    
    st.write("")
    exam_type = st.radio("시험 유형 선택", ["✍️ 필답형 (주관식/서술)", "💻 작업형 (동영상/도면)"], horizontal=True)
    
    target_file = FILE_PILDAP if "필답형" in exam_type else FILE_JAKUP
    
    if not os.path.exists(target_file):
        st.error(f"⚠️ 현재 폴더에 '{target_file}' 파일이 없습니다! 엑셀 파일을 업로드해 주세요.")
        st.stop()
        
    xls = pd.ExcelFile(target_file)
    sheet_names = xls.sheet_names
    
    is_shuffle = st.checkbox("🔀 문제 순서 랜덤하게 섞기", value=True)
    view_mode = st.radio("보기 방식", ["🔽 드롭다운", "🔠 펼쳐보기"], horizontal=True, label_visibility="collapsed")
    
    def start_new_quiz(target_sheet, current_file):
        df = pd.read_excel(current_file, sheet_name=target_sheet)
        df.columns = df.columns.str.replace(' ', '')
        if '출처' not in df.columns:
            df['출처'] = target_sheet 
            
        if is_shuffle: df = df.sample(frac=1).reset_index(drop=True)
        keywords = ["년", "회", "기출", "과년도"]
        is_mock = any(kw in target_sheet for kw in keywords)
        init_quiz_state(df, is_mock, False, False)
        st.rerun()

    st.write("---")
    if "드롭다운" in view_mode:
        selected_sheet = st.selectbox("📚 단원 선택", sheet_names)
        if st.button("문제 풀기 🚀", use_container_width=True, type="primary"): start_new_quiz(selected_sheet, target_file)
    else:
        st.markdown("##### 📚 클릭하면 즉시 시작됩니다!")
        cols = st.columns(2)
        for i, sheet in enumerate(sheet_names):
            with cols[i % 2]:
                if st.button(f"📖 {sheet}", use_container_width=True): start_new_quiz(sheet, target_file)
                
    st.write("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📝 내 오답노트 풀기", use_container_width=True):
            note_filename = f"{st.session_state.nickname}_오답노트.xlsx"
            if not os.path.exists(note_filename): st.warning("틀린 문제가 없습니다!")
            else:
                df = pd.read_excel(note_filename)
                df.columns = df.columns.str.replace(' ', '')
                if is_shuffle: df = df.sample(frac=1).reset_index(drop=True)
                init_quiz_state(df, False, True, False)
                st.rerun()
    with col2:
        if st.button("⭐ 내 즐겨찾기 풀기", use_container_width=True):
            mark_filename = f"{st.session_state.nickname}_즐겨찾기.xlsx"
            if not os.path.exists(mark_filename): st.warning("저장한 문제가 없습니다!")
            else:
                df = pd.read_excel(mark_filename)
                df.columns = df.columns.str.replace(' ', '')
                if is_shuffle: df = df.sample(frac=1).reset_index(drop=True)
                init_quiz_state(df, False, False, True)
                st.rerun()

    # 방명록
    st.write("---")
    with st.expander("💬 방문자 방명록 (건의사항이나 응원을 남겨주세요!)", expanded=False):
        entries = load_guestbook()
        if not entries:
            st.info("아직 등록된 방명록이 없습니다. 첫 번째 글을 남겨보세요! 🎉")
        else:
            for entry in reversed(entries[-15:]): 
                is_owner = "👑" in entry['name']
                border_color = "#f1c40f" if is_owner else "#e0e0e0"
                bg_color = "#fffbf0" if is_owner else "#f9f9f9"
                
                st.markdown(f"""
                <div style="background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 8px; padding: 10px; margin-bottom: 10px;">
                    <div style="font-size: 12px; color: gray; margin-bottom: 5px;">👤 {entry['name']} ┃ 🕒 {entry['time']}</div>
                    <div style="font-size: 14px; color: #2c3e50;">{entry['msg']}</div>
                </div>
                """, unsafe_allow_html=True)
        
        st.write("")
        new_msg = st.text_input("방명록 작성", placeholder="여기에 글을 입력하세요...", label_visibility="collapsed")
        if st.button("✏️ 방명록 남기기", use_container_width=True):
            if new_msg.strip():
                writer_name = "👑 펭귄주인장" if st.session_state.is_admin else f"익명 ({st.session_state.nickname[:7]}...)"
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                entries.append({"name": writer_name, "msg": new_msg.strip(), "time": now_str})
                save_guestbook(entries)
                st.toast("✅ 방명록이 성공적으로 등록되었습니다!")
                time.sleep(0.5)
                st.rerun()
            else:
                st.warning("글 내용을 입력해 주세요!")

# ==========================================
# ⭐ 화면 2: 퀴즈 화면 (엑셀 신규 컬럼 반영)
# ==========================================
elif st.session_state.page == 'quiz':
    df = st.session_state.df
    idx = st.session_state.index
    total_q = len(df)
    if idx >= total_q:
        st.session_state.page = 'result'
        st.rerun()
        
    row = df.iloc[idx]
    q_text = row['문제']
    point = get_question_point(df, idx)
    
    c_prev, c_nav, c_mark, c_home = st.columns([1.5, 3, 1.5, 1.5])
    with c_prev:
        if idx > 0:
            if st.button("◀ 이전", use_container_width=True):
                st.session_state.index -= 1
                st.session_state.show_answer = False
                st.rerun()
        else: st.write("") 
            
    with c_nav:
        q_list = [f"{i+1}번 문제 이동" for i in range(total_q)]
        jump_select = st.selectbox("이동", q_list, index=idx, label_visibility="collapsed")
        jump_idx = q_list.index(jump_select)
        if jump_idx != idx:
            st.session_state.index = jump_idx
            st.session_state.show_answer = False
            st.rerun()
            
    with c_mark:
        bookmarked = is_bookmarked(q_text)
        btn_type = "primary" if bookmarked else "secondary" 
        if st.button("🌟 저장" if bookmarked else "⭐ 저장", type=btn_type, use_container_width=True):
            toggle_bookmark(row)
            st.rerun() 
            
    with c_home:
        if st.button("🏠", use_container_width=True):
            st.session_state.page = 'selection'
            st.rerun()
            
    st.progress((idx) / total_q)
    
    with st.expander(f"🗺️ 전체 문제 현황판 ({idx+1}/{total_q}) - 클릭해서 펼치기"):
        status_html = '<div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:5px; margin-bottom:15px; justify-content:center;">'
        for i in range(total_q):
            bg_color = "#f1f2f6"; text_color = "#7f8c8d"; border = "1px solid #dcdde1"
            ans_status = st.session_state.user_answers.get(i)
            if ans_status is True: bg_color = "#2ecc71"; text_color = "white"; border = "1px solid #27ae60"
            elif ans_status is False: bg_color = "#e74c3c"; text_color = "white"; border = "1px solid #c0392b"
            if i == idx: 
                border = "3px solid #3498db" 
                if ans_status is None: bg_color = "white"; text_color = "#3498db"
            status_html += f'<div style="width:38px; height:38px; border-radius:8px; background-color:{bg_color}; color:{text_color}; display:flex; align-items:center; justify-content:center; font-weight:bold; border:{border}; font-size:14px; box-shadow: 1px 1px 3px rgba(0,0,0,0.1);">{i+1}</div>'
        status_html += '</div>'
        st.markdown(status_html, unsafe_allow_html=True)
        st.markdown("<p style='text-align:center; font-size:12px; color:gray;'>⬜ 안 푼 문제 &nbsp;┃&nbsp; 🟩 맞은 문제 &nbsp;┃&nbsp; 🟥 틀린 문제 &nbsp;┃&nbsp; 🟦 현재 위치</p>", unsafe_allow_html=True)
    
    if not isinstance(st.session_state.get('history'), dict): st.session_state.history = {}
    q_history = st.session_state.history.get(q_text, {"correct": 0, "incorrect": 0})
    total_attempts = q_history["correct"] + q_history["incorrect"]
    
    # ⭐ [업데이트] 참고 및 출제빈도 메타데이터 추가 반영
    source_name = row.get('참고') if '참고' in df.columns and pd.notna(row.get('참고')) else row.get('출처', '')
    freq = row.get('출제빈도', '')
    
    source_str = f"🏷️ 출처: {str(source_name).strip()} " if pd.notna(source_name) and str(source_name).strip() != '' else ""
    freq_str = f"┃ ⭐ 빈도: {str(freq).strip()} " if pd.notna(freq) and str(freq).strip() != '' else ""

    if total_attempts > 0: st.caption(f"{source_str}{freq_str}┃ 📊 이력: 맞음 {q_history['correct']} / 틀림 {q_history['incorrect']}")
    else: st.caption(f"{source_str}{freq_str}┃ ✨ 처음 푸는 문제입니다!")
            
    st.divider()
    
    # ⭐ [업데이트] 분류(실습형/작업형) 뱃지 렌더링
    category = row.get('분류', '')
    cat_badge = f"<span style='color: #8e44ad;'>[{str(category).strip()}]</span> " if pd.notna(category) and str(category).strip() != '' else ""
    st.markdown(f"### {cat_badge}{q_text}", unsafe_allow_html=True)
    
    # 보기, 그림설명, 이미지 조합
    bogi_col = '보기' if '보기' in df.columns else '[보기]' if '[보기]' in df.columns else None
    bogi_text = str(row[bogi_col]).strip() if bogi_col and pd.notna(row.get(bogi_col)) else ""
    if bogi_text.lower() == 'nan': bogi_text = ""
    
    # ⭐ [업데이트] 화면/그림설명 추가
    desc_col = '그림설명' if '그림설명' in df.columns else None
    desc_text = str(row[desc_col]).strip() if desc_col and pd.notna(row.get(desc_col)) else ""
    if desc_text.lower() == 'nan': desc_text = ""
    
    # ⭐ [업데이트] 이미지 경로 가져오기 ('그림 및 동영상' 열 우선 체크)
    img_col = '그림및동영상' if '그림및동영상' in df.columns else '문제이미지'
    q_imgs_html = get_images_html(row.get(img_col))

    # 위 3가지 중 하나라도 있으면 박스 생성
    if bogi_text or q_imgs_html or desc_text:
        combined_q_html = f'<div style="background-color: white; padding: 20px; border-radius: 8px; border: 2px solid #bdc3c7; color: #2c3e50; font-size: 15px; line-height: 1.6;">'
        if desc_text: combined_q_html += f'<div style="color: #2980b9; font-weight: bold; margin-bottom: 12px; background-color: #eaf2f8; padding: 10px; border-radius: 5px;">🎬 화면 설명: {desc_text}</div>'
        if bogi_text: combined_q_html += f'<strong>[보기]</strong><br><br><div style="white-space: pre-wrap;">{bogi_text}</div>'
        if q_imgs_html: combined_q_html += q_imgs_html
        combined_q_html += '</div><br>'
        st.markdown(combined_q_html, unsafe_allow_html=True)
                
    st.write("")
    is_mcq = '객관식보기' in df.columns and pd.notna(row.get('객관식보기'))

    def go_next(is_correct):
        save_history(q_text, is_correct)
        st.session_state.user_answers[st.session_state.index] = is_correct 
        if is_correct and st.session_state.is_review_mode: remove_from_incorrect_note(q_text)
        elif not is_correct and not st.session_state.is_review_mode: save_incorrect_answer(row)
        st.session_state.index += 1
        st.session_state.show_answer = False
        st.rerun()

    if not st.session_state.show_answer:
        if is_mcq:
            options_text = str(row['객관식보기'])
            opts = [opt.strip() for opt in options_text.split('\n') if opt.strip()]
            for i, opt in enumerate(opts):
                if st.button(opt, key=f"opt_{i}", use_container_width=True):
                    ans_val = str(row.get('정답', '')).strip()
                    if ans_val.endswith(".0"): ans_val = ans_val[:-2]
                    if str(i+1) == ans_val:
                        st.toast("⭕ 정답!")
                        time.sleep(0.5); go_next(True)
                    else: st.session_state.show_answer = True; st.rerun()
        else:
            if st.button("👀 정답 및 해설 보기", type="primary", use_container_width=True):
                st.session_state.show_answer = True; st.rerun()

    if st.session_state.show_answer:
        st.divider()
        ans_text = "" if pd.isna(row.get('해설')) else str(row['해설']).strip()
        
        # 정답 출력 부분 (엑셀에 '정답' 컬럼이 있는 경우 최우선으로 보여줌)
        real_ans = "" if pd.isna(row.get('정답')) else str(row['정답']).strip()
        if real_ans and not is_mcq: 
            ans_text = f"**[정답]**\n{real_ans}\n\n" + ans_text
            
        ans_imgs_html = get_images_html(row.get('해설이미지'))
        
        combined_a_html = f'<div style="background-color: white; padding: 20px; border-radius: 8px; border: 2px solid #bdc3c7; color: #2c3e50; font-size: 15px; line-height: 1.6;"><strong>[정답 및 해설]</strong><br><br>'
        if ans_text: combined_a_html += f'<div style="white-space: pre-wrap;">{ans_text}</div>'
        if ans_imgs_html: combined_a_html += ans_imgs_html
        combined_a_html += '</div><br>'
        st.markdown(combined_a_html, unsafe_allow_html=True)
                
        c1, c2 = st.columns(2)
        with c1:
            if st.button("⭕ 맞혔음", type="primary", use_container_width=True): go_next(True)
        with c2:
            if st.button("❌ 틀렸음", use_container_width=True): go_next(False)

# ==========================================
# 화면 3: 결과 대시보드 
# ==========================================
elif st.session_state.page == 'result':
    st.title("🎉 학습 완료!")
    st.balloons()
    mins, secs = divmod(int(time.time() - st.session_state.start_time), 60)
    
    correct = sum(1 for v in st.session_state.user_answers.values() if v)
    incorrect = sum(1 for v in st.session_state.user_answers.values() if not v)
    total_q = len(st.session_state.df)
    
    st.subheader(f"⏱️ 소요 시간: {mins}분 {secs}초")
    st.write("---")
    
    if st.session_state.is_review_mode:
        st.markdown(f"### 📝 오답노트 복습 결과")
        st.success(f"이번 학습으로 **총 {correct}문제**를 오답노트에서 완전히 덜어냈습니다! 🥳")
        note_filename = f"{st.session_state.nickname}_오답노트.xlsx"
        left_cnt = len(pd.read_excel(note_filename)) if os.path.exists(note_filename) else 0
        st.info(f"💡 현재 오답노트에 남은 문제: **{left_cnt}문제**")
        
        if left_cnt > 0:
            if st.button(f"🔁 남은 오답 다시 풀기", use_container_width=True, type="primary"):
                df_left = pd.read_excel(note_filename)
                df_left.columns = df_left.columns.str.replace(' ', '')
                df_left = df_left.sample(frac=1).reset_index(drop=True) 
                init_quiz_state(df_left, False, True, False)
                st.rerun()
                
    else:
        title_prefix = "⭐ 즐겨찾기 복습 결과" if st.session_state.is_bookmark_mode else "📚 문제 풀이 결과"
        if st.session_state.is_mock_exam:
            final_score = sum(get_question_point(st.session_state.df, i) for i, v in st.session_state.user_answers.items() if v)
            total_score = st.session_state.total_possible_score
            acc_score = (final_score / total_score * 100) if total_score > 0 else 0
            
            st.markdown(f"### {title_prefix}")
            st.markdown(f"#### 내 점수: <span style='color:#3498db'>{final_score}점</span> / 총점: {total_score}점", unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("🎯 득점률", f"{acc_score:.1f}%")
            c2.metric("⭕ 맞은 문제", f"{correct} 개")
            c3.metric("❌ 틀린 문제", f"{incorrect} 개")
            st.caption("전체 진행률")
            st.progress(min(max(final_score / total_score if total_score > 0 else 0, 0.0), 1.0))
        else:
            st.markdown(f"### {title_prefix}")
            acc = (correct / total_q * 100) if total_q > 0 else 0
            c1, c2, c3 = st.columns(3)
            c1.metric("🎯 정답률", f"{acc:.1f}%")
            c2.metric("⭕ 맞은 문제", f"{correct} 개")
            c3.metric("❌ 틀린 문제", f"{incorrect} 개")
            st.caption("나의 달성도")
            st.progress(min(max(correct / total_q if total_q > 0 else 0, 0.0), 1.0))

        if st.session_state.is_bookmark_mode:
            st.write("")
            if st.button("🔁 즐겨찾기 다시 풀기", use_container_width=True):
                mark_filename = f"{st.session_state.nickname}_즐겨찾기.xlsx"
                if os.path.exists(mark_filename):
                    df_left = pd.read_excel(mark_filename)
                    df_left.columns = df_left.columns.str.replace(' ', '')
                    df_left = df_left.sample(frac=1).reset_index(drop=True)
                    init_quiz_state(df_left, False, False, True)
                    st.rerun()

    st.write("---")
    if st.button("🏠 홈으로 돌아가기", use_container_width=True):
        st.session_state.page = 'selection'
        st.rerun()

st.markdown("<br><br><br><p style='text-align: center; color: gray; font-size: 12px;'>© 2026 Designed & Programmed by [펭귄주인장]. 무단 복제 및 상업적 배포 금지.</p>", unsafe_allow_html=True)