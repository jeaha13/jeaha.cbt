import streamlit as st
import pandas as pd
import os
import json
import time
import matplotlib.pyplot as plt
from PIL import Image
import zipfile
import io
import glob

# ==========================================
# 1. 웹사이트 기본 설정 및 폰트 세팅
# ==========================================
st.set_page_config(page_title="산업안전기사 마스터 CBT", page_icon="🚧", layout="centered")

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

FILE_NAME = "산업안전기사_실기_문제은행.xlsx"
STATS_FILE = "stats.json" 

# ==========================================
# ⚙️ 접속자 IP 추출 도우미 (스트림릿 최신 기능)
# ==========================================
def get_client_ip():
    ip = "Guest"
    try:
        if hasattr(st, 'context') and hasattr(st.context, 'headers'):
            x_forwarded = st.context.headers.get("X-Forwarded-For")
            if x_forwarded:
                ip = x_forwarded.split(',')[0].strip()
    except: pass
    
    # 윈도우 파일명에 쓸 수 없는 특수문자 제거
    safe_ip = "".join(c for c in ip if c.isalnum() or c in ".-_")
    return safe_ip if safe_ip else "Guest"

# ==========================================
# ⚙️ 통계 및 데이터 관리 도우미
# ==========================================
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
                if loaded: st.session_state.history = loaded
        except: pass

def save_history(question_text, is_correct):
    if getattr(st.session_state, 'history', None) is None: st.session_state.history = {}
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
            if df_new.empty: os.remove(mark_filename)
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
    st.session_state.score = 0
    st.session_state.correct_cnt = 0
    st.session_state.incorrect_cnt = 0
    st.session_state.show_answer = False
    st.session_state.is_mock_exam = is_mock
    st.session_state.is_review_mode = is_review
    st.session_state.is_bookmark_mode = is_bookmark
    st.session_state.start_time = time.time()
    st.session_state.page = 'quiz'

# ==========================================
# ⭐ 세션 상태 초기화 및 로그인 생략!
# ==========================================
keys_to_init = [
    'page', 'df', 'index', 'score', 'total_possible_score', 
    'correct_cnt', 'incorrect_cnt', 'show_answer', 'start_time',
    'is_review_mode', 'is_bookmark_mode', 'is_mock_exam', 'has_visited', 'is_admin'
]
for key in keys_to_init:
    if key not in st.session_state: st.session_state[key] = None

if st.session_state.is_admin is None: st.session_state.is_admin = False

# 닉네임이 없으면 접속한 사람의 IP를 닉네임으로 부여!
if 'nickname' not in st.session_state or st.session_state.nickname is None:
    st.session_state.nickname = get_client_ip()

if 'history' not in st.session_state or st.session_state.history is None:
    st.session_state.history = {}

# 처음에 무조건 selection(단원 선택) 화면으로 직행!
if st.session_state.page is None or st.session_state.page == 'login': 
    st.session_state.page = 'selection'
    load_history()

if st.session_state.has_visited is None: st.session_state.has_visited = False
if not st.session_state.has_visited:
    increment_visits()
    st.session_state.has_visited = True

# ==========================================
# 👑 사이드바: 관리자 비밀 접속로
# ==========================================
with st.sidebar:
    st.caption("⚙️ 사이트 설정")
    admin_pw = st.text_input("관리자 코드", type="password")
    
    # 펭귄주인장님 비밀번호 확인!
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
        if st.session_state.is_admin: # 비밀번호 지우면 다시 일반 IP 모드로 강등
            st.session_state.is_admin = False
            st.session_state.nickname = get_client_ip()
            load_history()

# ==========================================
# 👑 화면 0-1: 관리자 전용 대시보드 
# ==========================================
if st.session_state.page == 'admin_dashboard' and st.session_state.is_admin:
    st.title(f"👑 펭귄주인장님의 대시보드")
    stats = load_stats()
    
    # 유저 DB가 없으니, 생성된 학습기록 파일 개수로 IP 수를 측정합니다.
    ip_users = len(glob.glob("*_학습기록.json"))
    
    col1, col2 = st.columns(2)
    with col1: st.metric(label="👁️ 총 누적 문제풀이 횟수", value=f"{stats.get('total_visits', 0)} 회")
    with col2: st.metric(label="👥 문제를 푼 기기(IP) 수", value=f"{ip_users} 대")
    st.write("---")
    
    # V15 백업 및 복구 센터 유지!
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
    if st.button("나도 문제 풀러 가기 🚀", use_container_width=True):
        st.session_state.page = 'selection'
        st.rerun()

# ==========================================
# 화면 1: 단원 선택 화면 (로그인 없이 바로 뜸!)
# ==========================================
elif st.session_state.page == 'selection':
    st.markdown("<h1 style='text-align: center;'>🚧 산업안전기사 마스터 CBT</h1>", unsafe_allow_html=True)
    
    if st.session_state.is_admin:
        st.info("👑 현재 관리자(펭귄주인장) 권한으로 접속 중입니다.")
    else:
        st.caption(f"접속 기기 IP: {st.session_state.nickname}")

    if not os.path.exists(FILE_NAME):
        st.error(f"⚠️ '{FILE_NAME}' 파일이 폴더에 없습니다! 엑셀 파일을 준비해 주세요.")
        st.stop()
        
    xls = pd.ExcelFile(FILE_NAME)
    sheet_names = xls.sheet_names
    selected_sheet = st.selectbox("📚 학습할 단원이나 회차를 선택하세요", sheet_names)
    is_shuffle = st.checkbox("🔀 문제 순서 랜덤하게 섞기", value=True)
    st.write("---")
    
    if st.button("새로운 문제 풀기 🚀", use_container_width=True, type="primary"):
        df = pd.read_excel(FILE_NAME, sheet_name=selected_sheet)
        df.columns = df.columns.str.replace(' ', '')
        if is_shuffle: df = df.sample(frac=1).reset_index(drop=True)
        keywords = ["년", "회", "기출", "과년도"]
        is_mock = any(kw in selected_sheet for kw in keywords)
        init_quiz_state(df, is_mock, False, False)
        st.rerun()
        
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📝 내 오답노트 풀기", use_container_width=True):
            note_filename = f"{st.session_state.nickname}_오답노트.xlsx"
            if not os.path.exists(note_filename): st.warning("아직 틀린 문제가 없습니다! 완벽하네요 🎉")
            else:
                df = pd.read_excel(note_filename)
                df.columns = df.columns.str.replace(' ', '')
                if is_shuffle: df = df.sample(frac=1).reset_index(drop=True)
                init_quiz_state(df, False, True, False)
                st.rerun()
    with col2:
        if st.button("⭐ 내 즐겨찾기 풀기", use_container_width=True):
            mark_filename = f"{st.session_state.nickname}_즐겨찾기.xlsx"
            if not os.path.exists(mark_filename): st.warning("아직 저장한 문제가 없습니다! 문제 풀이 중 ⭐ 버튼을 눌러보세요.")
            else:
                df = pd.read_excel(mark_filename)
                df.columns = df.columns.str.replace(' ', '')
                if is_shuffle: df = df.sample(frac=1).reset_index(drop=True)
                init_quiz_state(df, False, False, True)
                st.rerun()

# ==========================================
# 화면 2: 퀴즈 화면 (기존과 동일)
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
    
    c_prog, c_mark, c_home = st.columns([6, 2, 2])
    with c_prog:
        prefix = "[오답노트]" if st.session_state.is_review_mode else "[⭐ 즐겨찾기]" if st.session_state.is_bookmark_mode else "[모의고사]" if st.session_state.is_mock_exam else "[연습모드]"
        st.progress((idx) / total_q)
        st.caption(f"{prefix} 문제 {idx + 1} / {total_q} (배점: {point}점)")
        
    with c_mark:
        bookmarked = is_bookmarked(q_text)
        btn_text = "🌟 저장됨 (취소)" if bookmarked else "⭐ 문제 저장"
        btn_type = "primary" if bookmarked else "secondary"
        if st.button(btn_text, type=btn_type, use_container_width=True):
            now_saved = toggle_bookmark(row)
            if now_saved: st.toast("⭐ 즐겨찾기에 추가되었습니다!")
            else: st.toast("🗑️ 즐겨찾기에서 삭제되었습니다.")
            st.rerun() 
            
    with c_home:
        if st.button("🏠 홈", use_container_width=True):
            st.session_state.page = 'selection'
            st.rerun()

    if getattr(st.session_state, 'history', None) is None:
        st.session_state.history = {}
        
    q_history = st.session_state.history.get(q_text, {"correct": 0, "incorrect": 0})
    
    total_attempts = q_history["correct"] + q_history["incorrect"]
    if total_attempts > 0: st.caption(f"📊 내 풀이 이력: 총 {total_attempts}회 시도 ┃ 맞음 {q_history['correct']}회 / 틀림 {q_history['incorrect']}회")
    else: st.caption("✨ 처음 푸는 문제입니다!")
            
    st.divider()
    st.subheader(f"{q_text}")
    
    bogi_col = '보기' if '보기' in df.columns else '[보기]' if '[보기]' in df.columns else None
    if bogi_col and pd.notna(row.get(bogi_col)):
        bogi_text = str(row[bogi_col]).strip()
        if bogi_text and bogi_text.lower() != 'nan':
            bogi_html = f"""<div style="background-color: #ffffff; padding: 15px; border-radius: 8px; white-space: pre-wrap; border: 2px solid #bdc3c7; color: #2c3e50; font-size: 15px; line-height: 1.6;"><strong>[보기]</strong><br><br>{bogi_text}</div><br>"""
            st.markdown(bogi_html, unsafe_allow_html=True)
            
    if '문제이미지' in df.columns and pd.notna(row['문제이미지']):
        img_names_raw = str(row['문제이미지']).strip()
        if img_names_raw and img_names_raw.lower() != 'nan':
            img_names = [name.strip() for name in img_names_raw.replace(';', ',').split(',') if name.strip()]
            for img_name in img_names:
                img_path = os.path.join("사진폴더", img_name)
                if os.path.exists(img_path): 
                    st.image(Image.open(img_path), use_container_width=True)
                    st.write("") 
                else: st.error(f"이미지 없음: {img_path}")
                
    st.write("")
    is_mcq = '객관식보기' in df.columns and pd.notna(row.get('객관식보기'))

    def go_next(is_correct):
        save_history(q_text, is_correct)
        if is_correct:
            st.session_state.correct_cnt += 1
            st.session_state.score += point
            if st.session_state.is_review_mode: remove_from_incorrect_note(q_text)
        else:
            st.session_state.incorrect_cnt += 1
            if not st.session_state.is_review_mode: save_incorrect_answer(row)
        st.session_state.index += 1
        st.session_state.show_answer = False
        st.rerun()

    if not st.session_state.show_answer:
        if is_mcq:
            options_text = str(row['객관식보기'])
            opts = [opt.strip() for opt in options_text.split('\n') if opt.strip()]
            if len(opts) < 2: opts = ["1번", "2번", "3번", "4번"]
            for i, opt in enumerate(opts):
                if st.button(opt, key=f"opt_{i}", use_container_width=True):
                    ans_val = str(row.get('정답', '')).strip()
                    if ans_val.endswith(".0"): ans_val = ans_val[:-2]
                    if str(i+1) == ans_val:
                        if st.session_state.is_review_mode: st.toast("⭕ 정답입니다! (오답노트에서 삭제됨)")
                        else: st.toast("⭕ 정답입니다!")
                        time.sleep(0.5)
                        go_next(True)
                    else:
                        st.session_state.show_answer = True
                        st.rerun()
        else:
            if st.button("👀 정답 및 해설 보기", type="primary", use_container_width=True):
                st.session_state.show_answer = True
                st.rerun()

    if st.session_state.show_answer:
        st.write("---")
        raw_ans = row.get('해설')
        ans_text = "" if pd.isna(raw_ans) else str(raw_ans).strip()
        ans_html = f"""<div style="background-color: #f1f8e9; padding: 20px; border-radius: 8px; white-space: pre-wrap; font-size: 15px; color: #2c3e50; border-left: 5px solid #8bc34a; line-height: 1.6;"><strong>[정답 및 해설]</strong><br><br>{ans_text}</div><br>"""
        st.markdown(ans_html, unsafe_allow_html=True)
        
        if '해설이미지' in df.columns and pd.notna(row['해설이미지']):
            img_names_raw = str(row['해설이미지']).strip()
            if img_names_raw and img_names_raw.lower() != 'nan':
                img_names = [name.strip() for name in img_names_raw.replace(';', ',').split(',') if name.strip()]
                for img_name in img_names:
                    img_path = os.path.join("사진폴더", img_name)
                    if os.path.exists(img_path): 
                        st.image(Image.open(img_path), use_container_width=True)
                        st.write("")
                    else: st.error(f"이미지 없음: {img_path}")
                
        st.write("결과를 스스로 채점해 주세요.")
        c1, c2 = st.columns(2)
        with c1:
            btn_text = "⭕ 맞혔음 (오답에서 지우기)" if st.session_state.is_review_mode else "⭕ 맞혔음 (다음 문제로)"
            if st.button(btn_text, type="primary", use_container_width=True): go_next(True)
        with c2:
            if st.button("❌ 틀렸음 (다음 문제로)", use_container_width=True): go_next(False)

# ==========================================
# 화면 3: 결과 대시보드 화면 
# ==========================================
elif st.session_state.page == 'result':
    st.title("🎉 학습 완료!")
    st.balloons()
    elapsed_sec = int(time.time() - st.session_state.start_time)
    mins, secs = divmod(elapsed_sec, 60)
    hours, mins = divmod(mins, 60)
    time_str = f"{hours}시간 {mins}분 {secs}초" if hours > 0 else f"{mins}분 {secs}초"
    total_q = len(st.session_state.df)
    correct = st.session_state.correct_cnt
    incorrect = st.session_state.incorrect_cnt
    acc = (correct / total_q * 100) if total_q > 0 else 0
    
    st.subheader(f"⏱️ 소요 시간: {time_str}")
    
    if st.session_state.is_review_mode:
        note_filename = f"{st.session_state.nickname}_오답노트.xlsx"
        st.markdown(f"### 📝 오답노트 복습 결과")
        st.success(f"이번 학습으로 **총 {correct}문제**를 오답노트에서 완전히 덜어냈습니다! 🥳")
        left_cnt = len(pd.read_excel(note_filename)) if os.path.exists(note_filename) else 0
        st.info(f"💡 현재 오답노트에 남은 문제: **{left_cnt}문제**")
        st.write("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🏠 메인으로 돌아가기", use_container_width=True):
                st.session_state.page = 'selection'
                st.rerun()
        with col2:
            if left_cnt > 0:
                if st.button(f"🔁 남은 오답 다시 풀기", use_container_width=True, type="primary"):
                    df_left = pd.read_excel(note_filename)
                    df_left.columns = df_left.columns.str.replace(' ', '')
                    df_left = df_left.sample(frac=1).reset_index(drop=True) 
                    init_quiz_state(df_left, False, True, False)
                    st.rerun()
            else: st.success(f"🎉 오답노트를 모두 정복했습니다!")
                
    else:
        title_prefix = "⭐ 즐겨찾기 복습 결과" if st.session_state.is_bookmark_mode else "📚 문제 풀이 결과"
        if st.session_state.is_mock_exam:
            final_score = st.session_state.score
            total_score = st.session_state.total_possible_score
            st.markdown(f"### 내 점수: <span style='color:#3498db'>{final_score}점</span> / 총점: {total_score}점", unsafe_allow_html=True)
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4))
            fig.patch.set_facecolor('#f9f9f9')
            labels = ['맞은 문제', '틀린 문제']
            sizes = [correct, incorrect]
            if sum(sizes) == 0: sizes = [1, 0]
            ax1.pie(sizes, labels=labels, colors=['#2ecc71', '#e74c3c'], autopct='%1.1f%%', startangle=90, textprops={'fontsize': 12, 'fontweight': 'bold'})
            ax1.set_title('문제 풀이 결과', fontweight='bold', pad=15)
            ax2.bar(['내 점수', '총점'], [final_score, total_score], color=['#3498db', '#95a5a6'], width=0.5)
            ax2.text(0, final_score + 1, f'{final_score}점', ha='center', fontweight='bold', color='#3498db')
            ax2.text(1, total_score + 1, f'{total_score}점', ha='center', fontweight='bold', color='#7f8c8d')
            ax2.set_title('점수 현황', fontweight='bold', pad=15)
            fig.tight_layout()
            st.pyplot(fig)
        else:
            st.markdown(f"### {title_prefix}")
            st.markdown(f"### 총 {total_q}문제 중 {correct}문제를 맞혔습니다! (정답률: <span style='color:#3498db'>{acc:.1f}%</span>)", unsafe_allow_html=True)
            fig, ax = plt.subplots(figsize=(6, 4))
            fig.patch.set_facecolor('#f9f9f9')
            labels = ['맞은 문제', '틀린 문제']
            sizes = [correct, incorrect]
            if sum(sizes) == 0: sizes = [1, 0]
            ax.pie(sizes, labels=labels, colors=['#2ecc71', '#e74c3c'], autopct='%1.1f%%', startangle=90, textprops={'fontsize': 14, 'fontweight': 'bold'})
            ax.set_title('나의 달성도', fontweight='bold', pad=15)
            st.pyplot(fig)

        st.write("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🏠 메인으로 돌아가기", use_container_width=True, type="primary"):
                st.session_state.page = 'selection'
                st.rerun()
        with col2:
            if st.session_state.is_bookmark_mode:
                mark_filename = f"{st.session_state.nickname}_즐겨찾기.xlsx"
                if os.path.exists(mark_filename):
                    if st.button("🔁 즐겨찾기 다시 풀기", use_container_width=True):
                        df_left = pd.read_excel(mark_filename)
                        df_left.columns = df_left.columns.str.replace(' ', '')
                        df_left = df_left.sample(frac=1).reset_index(drop=True)
                        init_quiz_state(df_left, False, False, True)
                        st.rerun()
            else:
                if st.button("📝 오답노트 바로가기", use_container_width=True):
                    note_filename = f"{st.session_state.nickname}_오답노트.xlsx"
                    if not os.path.exists(note_filename): st.warning("아직 틀린 문제가 없습니다!")
                    else:
                        df_left = pd.read_excel(note_filename)
                        df_left.columns = df_left.columns.str.replace(' ', '')
                        df_left = df_left.sample(frac=1).reset_index(drop=True)
                        init_quiz_state(df_left, False, True, False)
                        st.rerun()

# 하단 워터마크
st.markdown("<br><br><br><p style='text-align: center; color: gray; font-size: 12px;'>© 2026 Designed & Programmed by [펭귄주인장]. 프로그램 무단 복제 및 상업적 배포를 엄격히 금지합니다.</p>", unsafe_allow_html=True)