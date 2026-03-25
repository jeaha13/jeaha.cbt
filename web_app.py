import streamlit as st
import pandas as pd
import os
import json
import time
import zipfile
import io
import glob
import base64

# ==========================================
# 1. 웹사이트 기본 설정
# ==========================================
st.set_page_config(page_title="산업안전기사 마스터 CBT", page_icon="🚧", layout="centered")

FILE_NAME = "산업안전기사_실기_문제은행.xlsx"
STATS_FILE = "stats.json" 

# ==========================================
# ⚙️ [V26] 이미지 자연스러운 핏(Natural Fit) 도우미
# ==========================================
# 이제 억지로 400px에 가두지 않습니다! 표나 긴 그림도 원본 비율대로 딱 맞게 들어갑니다.
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
# ⚙️ 접속자 IP 및 통계 관리 도우미
# ==========================================
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
                # 에러 원천 차단: 불러온 데이터가 딕셔너리일 때만 적용!
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
        if df_new.empty: os.remove(note_filename) if os.path.exists(note_filename) else None
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
            if df_new.empty: os.remove(mark_filename) if os.path.exists(mark_filename) else None
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

# ⭐ [V26] 퀴즈 세션 초기화 (점수 누적 방식 -> 딕셔너리 기록 방식으로 변경!)
def init_quiz_state(df, is_mock, is_review, is_bookmark):
    st.session_state.df = df
    st.session_state.total_possible_score = calculate_total_possible_score(df)
    st.session_state.index = 0
    st.session_state.user_answers = {} # 각 문제별 정답 여부 기록!
    st.session_state.show_answer = False
    st.session_state.is_mock_exam = is_mock
    st.session_state.is_review_mode = is_review
    st.session_state.is_bookmark_mode = is_bookmark
    st.session_state.start_time = time.time()
    st.session_state.page = 'quiz'

# ==========================================
# ⭐ 세션 상태 초기화 및 로그인 생략
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
    if not os.path.exists(FILE_NAME):
        st.error(f"⚠️ '{FILE_NAME}' 파일이 없습니다!")
        st.stop()
    xls = pd.ExcelFile(FILE_NAME)
    sheet_names = xls.sheet_names
    is_shuffle = st.checkbox("🔀 문제 순서 랜덤하게 섞기", value=True)
    view_mode = st.radio("보기 방식", ["🔽 드롭다운", "🔠 펼쳐보기"], horizontal=True, label_visibility="collapsed")
    
    def start_new_quiz(target_sheet):
        df = pd.read_excel(FILE_NAME, sheet_name=target_sheet)
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
        if st.button("문제 풀기 🚀", use_container_width=True, type="primary"): start_new_quiz(selected_sheet)
    else:
        st.markdown("##### 📚 클릭하면 즉시 시작됩니다!")
        cols = st.columns(2)
        for i, sheet in enumerate(sheet_names):
            with cols[i % 2]:
                if st.button(f"📖 {sheet}", use_container_width=True): start_new_quiz(sheet)
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

# ==========================================
# 화면 2: 퀴즈 화면 
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
    
    # 상단 네비게이션 바
    c_prev, c_prog, c_mark, c_home = st.columns([1.5, 4.5, 2.5, 1.5])
    with c_prev:
        if idx > 0:
            if st.button("◀ 이전", use_container_width=True):
                st.session_state.index -= 1
                st.session_state.show_answer = False
                st.rerun()
        else: st.write("") 
            
    with c_prog:
        prefix = "[오답]" if st.session_state.is_review_mode else "[⭐]" if st.session_state.is_bookmark_mode else "[모의]" if st.session_state.is_mock_exam else "[연습]"
        st.progress((idx) / total_q)
        st.caption(f"{prefix} {idx + 1}/{total_q} ({point}점)")
        
    with c_mark:
        bookmarked = is_bookmarked(q_text)
        btn_text = "🌟 저장됨" if bookmarked else "⭐ 저장"
        btn_type = "primary" if bookmarked else "secondary" 
        if st.button(btn_text, type=btn_type, use_container_width=True):
            now_saved = toggle_bookmark(row)
            if now_saved: st.toast("⭐ 즐겨찾기에 추가되었습니다!")
            else: st.toast("🗑️ 즐겨찾기에서 삭제되었습니다.")
            st.rerun() 
            
    with c_home:
        if st.button("🏠", use_container_width=True):
            st.session_state.page = 'selection'
            st.rerun()
    
    if not isinstance(st.session_state.get('history'), dict):
        st.session_state.history = {}
        
    q_history = st.session_state.history.get(q_text, {"correct": 0, "incorrect": 0})
    total_attempts = q_history["correct"] + q_history["incorrect"]
    
    source_name = row.get('출처', '')
    source_str = ""
    if pd.notna(source_name) and str(source_name).strip() != '':
        source_str = f"🏷️ 출처: {str(source_name).strip()} ┃ "

    if total_attempts > 0: 
        st.caption(f"{source_str}📊 이력: 맞음 {q_history['correct']} / 틀림 {q_history['incorrect']}")
    else: 
        st.caption(f"{source_str}✨ 처음 푸는 문제입니다!")
            
    st.divider()
    st.subheader(f"{q_text}")
    
    bogi_col = '보기' if '보기' in df.columns else '[보기]' if '[보기]' in df.columns else None
    bogi_text = ""
    if bogi_col and pd.notna(row.get(bogi_col)):
        bogi_text = str(row[bogi_col]).strip()
        if bogi_text.lower() == 'nan': bogi_text = ""

    q_imgs_html = get_images_html(row.get('문제이미지'))

    if bogi_text or q_imgs_html:
        combined_q_html = f'<div style="background-color: white; padding: 20px; border-radius: 8px; border: 2px solid #bdc3c7; color: #2c3e50; font-size: 15px; line-height: 1.6;">'
        if bogi_text:
            combined_q_html += f'<strong>[보기]</strong><br><br><div style="white-space: pre-wrap;">{bogi_text}</div>'
        if q_imgs_html:
            combined_q_html += q_imgs_html
        combined_q_html += '</div><br>'
        st.markdown(combined_q_html, unsafe_allow_html=True)
                
    st.write("")
    is_mcq = '객관식보기' in df.columns and pd.notna(row.get('객관식보기'))

    # ⭐ [V26] 점수 뻥튀기 방지: 현재 문제(idx)의 결과만 정확히 기록!
    def go_next(is_correct):
        save_history(q_text, is_correct)
        st.session_state.user_answers[st.session_state.index] = is_correct 
        
        if is_correct and st.session_state.is_review_mode:
            remove_from_incorrect_note(q_text)
        elif not is_correct and not st.session_state.is_review_mode:
            save_incorrect_answer(row)
            
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
        ans_imgs_html = get_images_html(row.get('해설이미지'))
        
        combined_a_html = f'<div style="background-color: white; padding: 20px; border-radius: 8px; border: 2px solid #bdc3c7; color: #2c3e50; font-size: 15px; line-height: 1.6;"><strong>[정답 및 해설]</strong><br><br>'
        if ans_text:
            combined_a_html += f'<div style="white-space: pre-wrap;">{ans_text}</div>'
        if ans_imgs_html:
            combined_a_html += ans_imgs_html
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
    
    # ⭐ [V26] 기록된 user_answers를 바탕으로 정확한 점수 계산!
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
            # ⭐ [V26] 최종 점수 동적 계산 (100% 초과 원천 차단)
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
            # 진행률 오류 방지를 위해 0~1 사이로 강제 고정
            progress_val = (final_score / total_score) if total_score > 0 else 0
            st.progress(min(max(progress_val, 0.0), 1.0))
            
        else:
            st.markdown(f"### {title_prefix}")
            acc = (correct / total_q * 100) if total_q > 0 else 0
            
            c1, c2, c3 = st.columns(3)
            c1.metric("🎯 정답률", f"{acc:.1f}%")
            c2.metric("⭕ 맞은 문제", f"{correct} 개")
            c3.metric("❌ 틀린 문제", f"{incorrect} 개")
            
            st.caption("나의 달성도")
            progress_val2 = correct / total_q if total_q > 0 else 0
            st.progress(min(max(progress_val2, 0.0), 1.0))

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