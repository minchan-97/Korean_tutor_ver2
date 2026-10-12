"""Korean Magnet Tutor — 인도네시아어 화자를 위한 한국어 쓰기 튜터 (몰랑이 코어 연동).

화면 글자 읽는 법 (민찬기 선생님용)
  L('인도네시아어', '한국어')  ← 학습자는 앞쪽만 보고, 교사 모드에서 '한국어 번역 보기'를 켜면
  뒤쪽 한국어가 〔 〕 안에 같이 뜬다. 즉 코드에서는 L(...)의 두 번째 인자가 한국어 주석이고,
  실행 중에는 화면에서 바로 대조할 수 있다. L()을 안 쓰는 인도네시아어 줄에는  # 🇰🇷  주석을 달았다.
"""
import html
import json
import os
import random
import hmac
import streamlit as st
import streamlit.components.v1 as components

from graph_data import NODES, EDGES, EXERCISES, TOPICS, LABEL_KO
from engine import connection, save_attempt, history, mastery, demo_evaluate, next_exercise
from molang_adapter import choose, update, policy, reset_policy, audit, add_document, magnet_neighbors, approved_documents, STRATEGIES
from llm_client import configured, evaluate
import vocab_bank as vb
from dynamic_magnet import build as build_dynamic, explore as explore_dynamic, propose as propose_words, candidates as word_candidates, review as review_word

st.set_page_config(page_title='Korean Magnet Tutor', page_icon='🇰🇷', layout='wide')
BY_ID = {e['id']: e for e in EXERCISES}


# ─── 공통 도우미 ───────────────────────────────────────────────
def setting(name):
    try:
        return st.secrets.get(name, os.getenv(name, ''))
    except Exception:
        return os.getenv(name, '')


def same(a, b):
    """비밀번호 비교. 수정: 예전 코드는 str을 바로 compare_digest에 넣어서
    한글 등 비ASCII 문자를 입력하면 TypeError로 앱이 죽었다. bytes로 바꿔 비교한다."""
    return hmac.compare_digest((a or '').encode('utf-8'), (b or '').encode('utf-8'))


def L(idn, ko):
    """학습자 화면 문구. 교사 확인 모드일 때만 한국어 번역을 덧붙인다."""
    if st.session_state.get('teacher_view') and ko:
        return f'{idn}  〔{ko}〕'
    return idn


def speak(text):
    """🔊 발음 듣기 — 브라우저 내장 음성(Web Speech API, ko-KR). API 키·비용 없음.
    기기에 한국어 음성이 없으면 소리가 안 날 수 있다(대부분의 안드로이드/아이폰/크롬은 있음)."""
    label = L('🔊 Dengar', '듣기')  # 🇰🇷 듣기
    components.html(f"""
      <button id="b" style="font-size:14px;padding:4px 10px;border-radius:8px;border:1px solid #ccc;background:#fff;cursor:pointer">{html.escape(label)}</button>
      <script>
        document.getElementById('b').onclick = () => {{
          const u = new SpeechSynthesisUtterance({json.dumps(text)});
          u.lang = 'ko-KR'; u.rate = 0.85;
          speechSynthesis.cancel(); speechSynthesis.speak(u);
        }};
      </script>""", height=42)


def render_blocks(ex, prefix):
    """낱말 블록으로 문장 만들기. 블록 순서는 문제마다 고정된 방식으로 섞는다.
    수정: 예전에는 정답 블록이 정답 순서대로 맨 앞에 놓여 있어서 답이 그대로 보였다.
    반환: '순서 확인'을 누른 순간 True(맞음)/False(틀림), 안 눌렀으면 None — 단어장 연습이 결과를 기록할 때 쓴다."""
    state_key = f'{prefix}blocks_{ex["id"]}'
    st.session_state.setdefault(state_key, [])
    chosen = st.session_state[state_key]
    shown = ex['blocks'][:]
    random.Random(ex['id']).shuffle(shown)
    st.write(L('**Kalimat Anda:**', '내 문장'), ' '.join(chosen) if chosen else '—')
    if chosen:
        rm = st.columns(len(chosen))
        for i, word in enumerate(chosen):
            if rm[i].button('✕ ' + word, key=f'{prefix}rm_{ex["id"]}_{i}'):
                chosen.pop(i); st.rerun()
    st.write(L('**Pilih blok:**', '블록 고르기'))
    cols = st.columns(3)
    for i, word in enumerate(shown):
        with cols[i % 3]:
            if st.button('＋ ' + word, key=f'{prefix}add_{ex["id"]}_{i}', disabled=word in chosen):
                chosen.append(word); st.rerun()
    c1, c2 = st.columns(2)
    if c1.button(L('Ulangi', '처음부터'), key=f'{prefix}reset_{ex["id"]}'):
        st.session_state[state_key] = []; st.rerun()
    result = None
    if c2.button(L('Periksa susunan', '순서 확인'), key=f'{prefix}check_{ex["id"]}', type='primary'):
        result = chosen == ex['targets']
        if chosen == ex['targets']:
            st.success(L('Bagus! Susunannya benar. 🎉', '좋아요! 순서가 맞아요.'))
            speak(' '.join(chosen))
        elif sorted(chosen) == sorted(ex['targets']):
            st.warning(L('Bloknya sudah benar, tetapi urutannya belum tepat.', '블록은 맞는데 순서가 틀렸어요.'))
        else:
            st.info(L('Belum cocok. Periksa bentuk kata kerja dan partikelnya.', '아직 아니에요. 동사 형태와 조사를 확인하세요.'))
    st.caption(L('Blok hanya mengecek satu susunan contoh; kalimat lain bisa juga benar.',
                 '블록은 예시 순서 하나만 확인함. 다른 순서도 맞을 수 있음'))
    return result


# ─── 접속 비밀번호 (학습자·교사 공통) ─────────────────────────────
password = setting('APP_PASSWORD')
if password and not st.session_state.get('authorized'):
    st.title('🔐 Korean Magnet Tutor')
    entered = st.text_input('Kata sandi / 비밀번호', type='password')
    if st.button('Masuk', type='primary'):                # 🇰🇷 들어가기
        if same(entered, password):
            st.session_state.authorized = True; st.rerun()
        else:
            st.error('Kata sandi salah.')                  # 🇰🇷 비밀번호가 틀렸어요
    st.stop()

connection().close()

# ─── 사이드바: 교사 모드 ──────────────────────────────────────
# 교사 모드에서만: 한국어 번역 보기, AI 낱말 승인, 말뭉치 승인, NM 감사 기록, 오류 원문.
# 이유: 예전에는 학습자도 'AI 제안 낱말 승인' 버튼을 누를 수 있어서 사람 검토라는 안전장치가 무의미했다.
# 그리고 한국어 번역에는 정답이 그대로 들어 있으므로 학습자 화면에서는 꺼져 있어야 한다.
with st.sidebar:
    st.subheader('🧑‍🏫 Guru / 교사')
    teacher_pw = setting('TEACHER_PASSWORD')
    if not st.session_state.get('teacher'):
        if teacher_pw:
            pin = st.text_input('PIN', type='password', key='teacher_pin')
            if st.button('Masuk / 교사 로그인', key='teacher_login'):
                if same(pin, teacher_pw):
                    st.session_state.teacher = True; st.session_state.teacher_view = True; st.rerun()
                else:
                    st.error('PIN salah / PIN이 틀림')
        else:
            st.caption('⚠️ TEACHER_PASSWORD 미설정 — 학습자도 교사 모드를 켤 수 있음. 배포 전에 secrets에 설정하세요.')
            if st.button('교사 모드 켜기', key='teacher_open'):
                st.session_state.teacher = True; st.session_state.teacher_view = True; st.rerun()
    else:
        st.toggle('화면에 한국어 번역 함께 보기', key='teacher_view')
        if st.button('교사 모드 나가기', key='teacher_exit'):
            st.session_state.teacher = False; st.session_state.teacher_view = False; st.rerun()
TEACHER = bool(st.session_state.get('teacher'))

# ─── 머리말 ─────────────────────────────────────────────────
st.title('🇮🇩 → 🇰🇷 Korean Magnet Tutor')
st.caption(L('Belajar menulis bahasa Korea dengan blok kata, peta kosakata, dan umpan balik',
             '낱말 블록, 어휘 지도, 피드백으로 한국어 쓰기 배우기'))
if not configured():
    st.warning(L('Mode demo (tanpa AI): jawaban hanya dicocokkan dengan beberapa contoh. Jawaban lain yang benar bisa dianggap salah.',
                 '데모 모드(AI 없음): 등록된 몇 개 예시와만 비교. 맞는 다른 답도 오답 처리될 수 있음'))

tab_names = [L('📚 Kosakata harian', '오늘의 단어'), L('✍️ Latihan menulis', '쓰기 연습'),
             L('🧲 Blok kata', '낱말 블록'), L('🕸️ Peta kata', '어휘 지도'), L('📈 Kemajuan', '진도')]
if TEACHER:
    tab_names.append('🧑‍🏫 교사')
tabs = st.tabs(tab_names)
daily, study, magnet, vocab, progress = tabs[:5]

# ─── 0. 오늘의 단어 (생성 단어장 + 간격 반복 연습) ───────────────
POS_ID = {'명사': 'kata benda', '동사': 'kata kerja', '형용사': 'kata sifat', '부사': 'kata keterangan', '표현': 'ungkapan'}
# 🇰🇷 명사 / 동사 / 형용사 / 부사 / 표현


def vq_next():
    for k in ['vq', 'vq_done', 'vq_eval']:
        st.session_state.pop(k, None)


with daily:
    lv_keys = list(vb.LEVELS)
    saved_lv = vb.get_setting('learner_level', 'A1')
    level = st.selectbox(L('Level', '수준'), lv_keys, index=lv_keys.index(saved_lv) if saved_lv in lv_keys else 0,
                         format_func=lambda k: L(vb.LEVELS[k]['id'], vb.LEVELS[k]['ko']), key='vocab_level')
    if level != saved_lv:
        vb.set_setting('learner_level', level); vq_next()

    # 새 단어가 5개 미만이면 자동 생성 (하루 한도 안에서). 실패하면 이번 세션에서는 다시 시도하지 않는다.
    if configured() and not st.session_state.get('topup_failed'):
        try:
            if vb.unseen_count(level) < 5:
                with st.spinner(L('Menyiapkan kata baru...', '새 단어 만드는 중')):  # 🇰🇷 새 단어 준비 중
                    vb.topup(level)
        except Exception as err:
            st.session_state.topup_failed = True
            if TEACHER:
                st.exception(err)

    pg = vb.level_progress(level)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(L('Jumlah kata', '전체 단어'), pg['total'])        # 🇰🇷 전체 단어
    m2.metric(L('Sudah dikuasai', '익힌 단어'), pg['learned'])   # 🇰🇷 익힌 단어(상자 3 이상)
    m3.metric(L('Perlu diulang', '복습할 단어'), pg['due'])      # 🇰🇷 지금 복습할 단어
    m4.metric(L('Kata baru', '새 단어'), pg['unseen'])           # 🇰🇷 아직 안 본 단어
    if pg['ready']:
        st.success(L('Hebat! Kamu siap naik ke level berikutnya. 🎉', '익힌 단어 80% 이상 — 다음 수준으로 올려도 됨'))

    mode = st.radio(L('Mode', '모드'), ['practice', 'list'], horizontal=True, key='vocab_mode',
                    format_func=lambda m: {'practice': L('Latihan', '연습'), 'list': L('Daftar kata', '단어장')}[m])

    if mode == 'practice':
        cur = st.session_state.get('vq')
        if cur is None or cur.get('level') != level:
            vq_next(); st.session_state.vq = vb.next_question(level)
        q = st.session_state.vq
        if not q:
            st.info(L('Latihan hari ini selesai! Datang lagi besok. 👏', '오늘 분량 끝 (새 단어 하루 한도·복습 모두 완료). 내일 다시'))
            if not configured():
                st.caption(L('Mode demo: kata baru hanya bisa dibuat jika AI aktif.', '데모 모드: 새 단어 생성은 API 키가 있어야 함'))
            st.button(L('Muat ulang', '새로고침'), on_click=vq_next, key='vq_reload')  # 🇰🇷 새로고침
        else:
            w = q['word']; done = st.session_state.get('vq_done')

            def finish(correct):
                if st.session_state.get('vq_done') is None:
                    st.session_state.vq_done = {'correct': correct, 'box': vb.record(w['id'], correct)}

            if q['kind'] == 'intro':
                st.caption(L('✨ Kata baru', '새 단어'))  # 🇰🇷 새 단어
                st.markdown(f"## {w['korean']}")
                speak(w['korean'])
                st.markdown(f"**{w['meaning_id']}** · _{POS_ID.get(w['pos'], w['pos'])}_")
                if TEACHER:
                    st.caption(f"〔한국어 뜻: {w['meaning_ko']} · {w['pos']} · 상태: {w['status']}〕")
                st.write(L('**Contoh:**', '예문'), w['example_ko'])  # 🇰🇷 예문
                speak(w['example_ko'])
                st.caption(w['example_id'])
                if st.button(L('Saya mengerti → Kuis', '알겠어요 → 퀴즈'), key=f"vq_intro_{q['qid']}", type='primary'):
                    st.session_state.vq = vb.make_question(w, 'meaning', level); st.rerun()

            elif q['kind'] in ('meaning', 'reverse'):
                if q['kind'] == 'meaning':
                    st.markdown(f"## {w['korean']}"); speak(w['korean'])
                    ask = L('Apa artinya?', '뜻이 뭐예요?')  # 🇰🇷 뜻이 뭐예요?
                else:
                    st.markdown(f"## {w['meaning_id']}")
                    ask = L('Pilih kata Korea yang tepat.', '알맞은 한국어 단어를 고르세요')  # 🇰🇷 알맞은 한국어 단어 고르기
                choice = st.radio(ask, q['options'], index=None, key=f"vq_r_{q['qid']}", disabled=done is not None)
                if done is None and st.button(L('Periksa', '확인'), key=f"vq_c_{q['qid']}", type='primary', disabled=choice is None):
                    finish(choice == q['answer']); st.rerun()

            elif q['kind'] == 'blocks':
                st.info(L(f"Susun kalimat ini dalam bahasa Korea: {w['example_id']}", f"문장 만들기: {w['example_ko']}"))  # 🇰🇷 이 문장을 한국어로 조립하세요
                st.caption(L(f"Kata kunci: {w['korean']} ({w['meaning_id']})", f"핵심 단어: {w['korean']}"))  # 🇰🇷 핵심 단어
                if done is None:
                    res = render_blocks(q['exercise'], 'vq_')
                    if res is not None:
                        finish(res); st.rerun()

            else:  # write
                st.info(L(q['exercise']['instruction'], q['exercise']['meaning_ko']))
                st.caption(L(f"Gunakan kata: {w['korean']} ({w['meaning_id']})", f"사용할 단어: {w['korean']}"))  # 🇰🇷 이 단어를 써서
                ans = st.text_input(L('Jawaban Anda', '내 답'), key=f"vq_w_{q['qid']}", disabled=done is not None)  # 🇰🇷 내 답
                if done is None and st.button(L('Periksa', '확인'), key=f"vq_wc_{q['qid']}", type='primary', disabled=not ans.strip()):
                    try:
                        result = evaluate(q['exercise'], ans.strip()) if configured() else demo_evaluate(q['exercise'], ans.strip())
                        st.session_state.vq_eval = result; finish(result['correct']); st.rerun()
                    except Exception as err:
                        st.error(L('Gagal memeriksa jawaban.', '채점 실패'))  # 🇰🇷 채점 실패
                        if TEACHER:
                            st.exception(err)

            if done is not None:
                if done['correct']:
                    st.success(L('Benar! 🎉', '정답!'))
                    days = vb.BOX_DAYS[done['box']]
                    st.caption(L(f'Kata ini akan diulang {days} hari lagi.', f'{days}일 뒤 복습'))  # 🇰🇷 n일 뒤 다시 나옴
                else:
                    st.error(L('Belum tepat. Kata ini akan muncul lagi sebentar lagi.', '틀림. 이 단어는 5분 뒤 다시 나옴'))
                ev = st.session_state.get('vq_eval')
                if ev and not ev['correct']:
                    st.write(L(ev['explanation_id'], ev.get('explanation_ko', '')))
                st.markdown(f"**{w['korean']}** — {w['meaning_id']}")
                st.write(w['example_ko']); speak(w['example_ko']); st.caption(w['example_id'])
                st.button(L('Berikutnya ➜', '다음'), on_click=vq_next, key='vq_next', type='primary')  # 🇰🇷 다음

            if TEACHER:
                with st.expander('🔍 교사용: 이 단어의 검증 정보'):
                    st.write(f"상태 {w['status']} · 출처 {w['source']} · 상자 {w['box']} · 문제 유형 {q['kind']}")
                    st.write(f"뜻 {w['meaning_ko']} ↔ 역번역 {w.get('back_meaning_ko') or '—'}")
                    st.write(f"예문 {w['example_ko']} ↔ 역번역 {w.get('back_example_ko') or '—'}")

    else:  # list
        topic_f = st.selectbox(L('Topik', '주제'), ['*'] + list(vb.TOPICS), key='vocab_topic_filter',
                               format_func=lambda t: L('Semua', '전체') if t == '*' else L(vb.TOPICS[t], t))  # 🇰🇷 전체
        rows = [r for r in vb.word_list(level) if topic_f == '*' or r['topic'] == topic_f]
        box_label = lambda b: '—' if b is None else '⭐' * min(b, 5)
        table = []
        for r in rows:
            row = {L('Korea', '한국어'): r['korean'], L('Arti', '뜻'): r['meaning_id'],
                   L('Contoh', '예문'): r['example_ko'], L('Arti contoh', '예문 뜻'): r['example_id'],
                   L('Hafalan', '익힘'): box_label(r['box'])}   # 🇰🇷 익힘 정도(별 = 상자 번호)
            if TEACHER:
                row['한국어 뜻'] = r['meaning_ko']; row['상태'] = r['status']
            table.append(row)
        st.dataframe(table, hide_index=True, use_container_width=True)
        if rows:
            pick = st.selectbox(L('Dengarkan kata', '단어 듣기'), [r['korean'] for r in rows], key='vocab_listen')  # 🇰🇷 단어 듣기
            speak(pick)

# ─── 1. 쓰기 연습 ───────────────────────────────────────────
ids = [e['id'] for e in EXERCISES]
if st.session_state.get('exercise_choice') not in BY_ID:
    st.session_state['exercise_choice'] = next_exercise(EXERCISES)


def go_next():
    st.session_state.exercise_choice = next_exercise(EXERCISES, st.session_state.get('exercise_choice'))


with study:
    top_l, top_r = st.columns([4, 1])
    with top_l:
        st.selectbox(L('Pilih latihan', '연습 고르기'), ids, key='exercise_choice',
                     format_func=lambda i: f"{BY_ID[i]['level']} · {TOPICS[BY_ID[i]['topic']]} · {BY_ID[i]['instruction'].split(': ', 1)[-1]}")
    with top_r:
        st.write('')
        # 다음 문제 = 안 푼 문제 → 복습일 지난 주제 → 숙달도 낮은 주제 순 (engine.next_exercise)
        st.button(L('Soal berikutnya ➜', '다음 문제'), on_click=go_next, key='next_top', use_container_width=True)
    ex = BY_ID[st.session_state.exercise_choice]
    st.info(L(ex['instruction'], ex['meaning_ko']))
    answer = st.text_area(L('Jawaban Anda dalam bahasa Korea', '한국어로 쓴 답'), key=f"answer_{ex['id']}", height=90,
                          placeholder=L('Tulis kalimat bahasa Korea...', '한국어 문장을 쓰세요'))
    st.caption(L('Tidak punya keyboard Korea? Pakai tab 🧲 Blok kata.', '한글 자판이 없으면 낱말 블록 탭을 쓰세요'))

    if st.button(L('Periksa jawaban', '답 확인'), key='check_answer', type='primary', disabled=not answer.strip()):
        try:
            result = evaluate(ex, answer.strip()) if configured() else demo_evaluate(ex, answer.strip())
            if result['correct']:
                strategy = 'next'  # 맞으면 전략을 고르지 않고 다음 문제로
                st.session_state.pop('pending_nm', None)
            else:
                strategy, record = choose(result['diagnosis_id'], ex['id'])
                # 이 답으로 바로 학습하지 않는다. 학습자가 전략을 써 본 뒤 누르는 피드백으로만 학습.
                st.session_state['pending_nm'] = (ex['id'], result['diagnosis_id'], record)
            value = save_attempt(ex, answer.strip(), result, strategy)
            add_document(answer.strip(), source='learner', approved=False)
            propose_words(result.get('suggested_words', []), source='llm')
            st.session_state['latest'] = (ex['id'], result, strategy, value)
        except Exception as err:
            st.error(L('Gagal memeriksa jawaban. Coba lagi sebentar lagi.', '채점 실패. 잠시 후 다시 시도'))
            if TEACHER:
                st.exception(err)  # 교사에게만 실제 오류 내용을 보여준다 (예전에는 오류가 통째로 숨겨졌다)

    latest = st.session_state.get('latest')
    if latest and latest[0] == ex['id']:
        _, r, strategy, value = latest
        st.divider()
        if r['correct']:
            st.success(L(f"Benar! 🎉  Skor: {r['score']}/100", f"정답! 점수 {r['score']}/100"))
            st.write(L('**Contoh jawaban:**', '예시 답'), r['reference'])
            speak(r['reference'])
            st.write(L(r['explanation_id'], r.get('explanation_ko', '')))
            st.button(L('Soal berikutnya ➜', '다음 문제'), on_click=go_next, key='next_after_ok', type='primary')
        else:
            st.metric(L('Skor perkiraan', '추정 점수'), f"{r['score']}/100")
            st.write(L('**Umpan balik:**', '피드백'), L(r['explanation_id'], r.get('explanation_ko', '')))
            corrected = r.get('corrected') or ''
            st.markdown(L(f"**Langkah berikutnya: {STRATEGIES[strategy]}**", f"다음 단계: {strategy}"))

            # 고른 전략을 화면에서 실제로 실행한다.
            # (예전에는 전략 이름만 보여주고 정답은 항상 공개해서, 힌트·다시 쓰기 전략이 의미가 없었다)
            if strategy == 'hint':
                st.info('💡 ' + L(r['hint_id'], r.get('hint_ko', '')))
                with st.expander(L('Lihat contoh jawaban', '예시 답 보기')):
                    st.write(r['reference'])
                    if corrected:
                        st.write(L('Jawaban Anda yang diperbaiki:', '고친 내 답:'), corrected)
            elif strategy == 'blocks':
                st.caption(L('Susun kalimatnya dengan blok di bawah.', '아래 블록으로 문장을 만들어 보세요'))
                render_blocks(ex, 'inline_')
            elif strategy == 'example':
                ko_ex, id_ex, _ = ex['extra']
                st.write(L('**Contoh lain:**', '다른 예문'), f'{ko_ex}  —  _{id_ex}_')
                speak(ko_ex)
                st.write(L('**Contoh jawaban untuk soal ini:**', '이 문제의 예시 답'), r['reference'])
                if corrected:
                    st.write(L('Jawaban Anda yang diperbaiki:', '고친 내 답:'), corrected)
            elif strategy == 'retry':
                st.info(L('Coba tulis lagi di kotak jawaban di atas, lalu periksa lagi.', '위 칸에 다시 써서 다시 확인해 보세요'))
                with st.expander(L('Menyerah? Lihat jawaban', '포기? 답 보기')):
                    st.write(r['reference'])

            st.write(L('**Apakah langkah ini membantu?**', '이 단계가 도움이 됐나요?'))
            left, right = st.columns(2)
            if left.button(L('👍 Ya, membantu', '도움 됨'), key='nm_yes'):
                pending = st.session_state.pop('pending_nm', None)
                if pending:
                    update(*pending, feedback=1.0); st.success(L('Terima kasih!', '고마워요!'))
            if right.button(L('👎 Tidak membantu', '도움 안 됨'), key='nm_no'):
                pending = st.session_state.pop('pending_nm', None)
                if pending:
                    update(*pending, feedback=-1.0)
                    st.info(L('Terima kasih! Lain kali kami coba cara lain.', '고마워요! 다음엔 다른 방법을 써 볼게요'))

        st.caption(L(f"Perkiraan penguasaan topik '{TOPICS[ex['topic']]}': {value:.0%} (perkiraan, bukan tes resmi)",
                     f"'{ex['topic']}' 숙달도 추정 {value:.0%} (추정치, 공식 시험 아님)"))
        if r.get('suggested_words'):
            st.write(L('**Kosakata usulan AI (belum diperiksa guru):**', 'AI 추천 낱말 (교사 검토 전)'))
            for word in r['suggested_words']:
                st.write(f"• {word['korean']} — {word['indonesian']}")
        if TEACHER:
            with st.expander('🔍 교사용: 채점 원본 / NM 경로'):
                st.json(r)
                pending = st.session_state.get('pending_nm')
                if pending and pending[0] == ex['id']:
                    st.json({'path': pending[2].path, 'probabilities_at_choice': pending[2].at_probs})

# ─── 2. 낱말 블록 ───────────────────────────────────────────
with magnet:
    st.subheader(L('Susun kalimat dengan blok kata', '낱말 블록으로 문장 만들기'))
    exm_id = st.selectbox(L('Pilih kalimat', '문장 고르기'), ids, key='magnet_exercise',
                          format_func=lambda i: BY_ID[i]['instruction'].split(': ', 1)[-1])
    exm = BY_ID[exm_id]
    st.info(L(exm['instruction'], exm['meaning_ko']))
    render_blocks(exm, 'tab_')

# ─── 3. 어휘 지도 (교사가 고른 관계만) ─────────────────────────
with vocab:
    st.subheader(L('Peta kosakata', '어휘 지도'))
    center = st.selectbox(L('Kata pusat', '중심 낱말'), list(NODES), index=0, key='vocab_center')
    meaning, pos = NODES[center]
    st.markdown(f'### {center} — {meaning}')
    st.caption(L(pos, LABEL_KO.get(pos, '')))
    speak(center)
    related = [(b, rel) if a == center else (a, rel) for a, b, rel in EDGES if center in (a, b)]
    if related:
        st.write(L('**Kata yang berhubungan:**', '관련 낱말'))
        for word, relation in related:
            st.write(f'🔗 **{word}** — {NODES[word][0]} · _{L(relation, LABEL_KO.get(relation, ""))}_')
    else:
        st.write(L('Belum ada hubungan untuk kata ini.', '이 낱말의 관계가 아직 없음'))
    st.caption(L('Peta ini disusun guru. Usulan AI tidak masuk otomatis.', '교사가 만든 지도. AI 제안은 자동으로 안 들어감'))

# ─── 4. 진도 ───────────────────────────────────────────────
with progress:
    st.subheader(L('Riwayat belajar', '학습 기록'))
    records = history(); levels = mastery()
    if records:
        c1, c2 = st.columns(2)
        c1.metric(L('Jumlah latihan', '연습 횟수'), len(records))
        c2.metric(L('Benar', '정답'), sum(r['correct'] for r in records))
        rows = []
        for r in records:
            row = {L('Waktu', '시각'): r['ts'][:16].replace('T', ' '),
                   L('Soal', '문제'): r['exercise'],
                   L('Jawaban', '답'): r['answer'],
                   L('Skor', '점수'): r['score']}
            if TEACHER:
                row['진단'] = r['diagnosis']; row['전략'] = r['strategy']; row['피드백(한국어)'] = r.get('feedback_ko') or ''
            rows.append(row)
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info(L('Belum ada latihan.', '아직 연습 없음'))
    if levels:
        st.write(L('**Penguasaan & jadwal ulang:**', '숙달도와 복습 일정'))
        st.dataframe([{L('Topik', '주제'): L(TOPICS.get(k, k), k),
                       L('Penguasaan', '숙달도'): f"{v['value']:.0%}",
                       L('Ulang lagi', '복습일'): v['due'][:10]} for k, v in levels.items()],
                     hide_index=True, use_container_width=True)
    st.write(L('**Kosakata per level:**', '수준별 단어'))  # 🇰🇷 수준별 단어 현황
    st.dataframe([{L('Level', '수준'): L(vb.LEVELS[k]['id'], vb.LEVELS[k]['ko']),
                   L('Jumlah kata', '전체'): p['total'], L('Dikuasai', '익힘'): p['learned'],
                   L('Perlu diulang', '복습'): p['due'], L('Kata baru', '새 단어'): p['unseen']}
                  for k in vb.LEVELS for p in [vb.level_progress(k)]], hide_index=True, use_container_width=True)
    st.caption(L('Data disimpan di server. Jika server dimulai ulang, riwayat bisa hilang.',
                 '서버에 저장됨. 서버 재시작 시 기록이 사라질 수 있음 (Streamlit Cloud 주의)'))

# ─── 5. 교사 탭 (한국어 전용) ─────────────────────────────────
if TEACHER:
    with tabs[5]:
        st.subheader('📚 단어 생성 · 검토')
        g1, g2, g3 = st.columns(3)
        gl = g1.selectbox('수준', list(vb.LEVELS), key='gen_level', format_func=lambda k: vb.LEVELS[k]['ko'])
        gt = g2.selectbox('주제', list(vb.TOPICS), key='gen_topic')
        gn = g3.slider('개수', 5, 20, 10, key='gen_n')
        if st.button('단어 생성 (생성 → 역번역 → 규칙 검사)', key='gen_go', type='primary', disabled=not configured()):
            try:
                with st.spinner('생성·검증 중...'):
                    res = vb.generate(gl, gt, gn)
                st.success(f"추가 {res['added']} · 검토 필요(flagged) {res['flagged']} · 중복 제외 {res['skipped']}")
            except Exception as err:
                st.exception(err)
        if not configured():
            st.caption('API 키가 없으면 생성 불가. 기본 단어(seed) 36개만 사용됨.')
        s1, s2 = st.columns(2)
        strict_now = vb.get_setting('require_approval', '0') == '1'
        strict = s1.toggle('엄격 모드: 교사가 승인한 단어만 연습에 사용', value=strict_now, key='strict_mode')
        if strict != strict_now:
            vb.set_setting('require_approval', int(strict)); vq_next()
        cap_now = int(vb.get_setting('daily_cap', '60'))
        cap = s2.number_input('하루 자동 생성 한도(비용 관리)', 0, 500, cap_now, step=10, key='daily_cap_input')
        if cap != cap_now:
            vb.set_setting('daily_cap', int(cap))
        st.caption(f'오늘 생성 {vb.generated_today()}개 · 새 단어가 5개 미만이면 학습자 화면에서 {vb.TOPUP_BATCH}개씩 자동 생성')

        st.markdown('**검토 대기** — 원래 한국어와 역번역(인도네시아어만 보고 다시 한국어로 옮긴 것)을 비교하세요. '
                    '뜻이 다르면 인도네시아어 번역이 틀렸을 가능성이 큽니다.')
        queue = vb.review_queue(20)
        if not queue:
            st.info('검토할 단어 없음')
        for r in queue:
            checks = json.loads(r['checks'] or '{}')
            fails = [k for k, v in checks.items() if not v]
            with st.container(border=True):
                st.write(f"{'⚠️' if r['status'] == 'flagged' else '✅'} **{r['korean']}** · {vb.LEVELS[r['level']]['ko']} · {r['topic']} · `{r['status']}`")
                st.write(f"뜻: {r['meaning_ko']}  ↔  역번역: **{r['back_meaning_ko'] or '—'}**  _(인니어: {r['meaning_id']})_")
                st.write(f"예문: {r['example_ko']}  ↔  역번역: **{r['back_example_ko'] or '—'}**")
                st.caption(f"인니어 예문: {r['example_id']}")
                if fails:
                    st.warning('걸린 검사: ' + ', '.join(fails))
                a, b, _ = st.columns([1, 1, 4])
                if a.button('✓ 승인', key=f"vok_{r['id']}"):
                    ex_ko = vb.set_status(r['id'], 'approved')
                    add_document(ex_ko, source='teacher', approved=True)  # 승인된 예문만 몰랑이 말뭉치로
                    st.rerun()
                if b.button('✕ 거절', key=f"vno_{r['id']}"):
                    vb.set_status(r['id'], 'rejected'); st.rerun()

        st.divider()
        st.subheader('🛡️ 쓰기 피드백에서 나온 AI 추천 낱말')
        st.caption('LLM이 낸 낱말 쌍. 승인해도 번역 쌍으로만 저장되고, 예문 말뭉치에는 들어가지 않는다.')
        pending_words = word_candidates()
        if not pending_words:
            st.info('검토 대기 낱말 없음')
        for item in pending_words[:30]:
            a, b, c = st.columns([5, 1, 1])
            a.write(f"**{item['korean']}** — {item['indonesian']}")
            if b.button('✓', key=f"approve_{item['id']}", help='승인'):
                review_word(item['id'], True); st.rerun()
            if c.button('✕', key=f"reject_{item['id']}", help='거절'):
                review_word(item['id'], False); st.rerun()

        st.divider()
        st.subheader('📚 검증된 예문 말뭉치')
        corpus = st.text_area('확인한 한국어 예문 추가 (한 줄에 한 문장)', key='corpus_input')
        if st.button('승인하고 저장', key='corpus_save', disabled=not corpus.strip()):
            n = 0
            for line in corpus.splitlines():
                if line.strip():
                    add_document(line, source='teacher', approved=True); n += 1
            st.success(f'{n}문장 처리 (이미 있던 문장은 건너뜀)'); st.session_state.pop('dynamic_state', None)
        if st.button('연습 문제의 정답·예문을 말뭉치에 한 번에 넣기', key='corpus_seed'):
            for e in EXERCISES:
                for s in [e['reference'], e['extra'][0]] + e.get('accepted', []):
                    add_document(s, source='teacher', approved=True)
            st.success('넣음 (중복 제외)'); st.session_state.pop('dynamic_state', None)
        st.caption(f'승인된 문장 {len(approved_documents(1000))}개 · 학습자 답은 자동 승인되지 않음')

        st.divider()
        st.subheader('🧲 몰랑이 Markov 자석 낱말')
        mc = st.selectbox('중심 낱말', list(NODES), key='markov_center')
        nxt, forms = magnet_neighbors(mc)
        st.write('말뭉치에서 잡힌 형태:', ', '.join(forms) if forms else '없음')
        st.write('그 뒤에 자주 오는 낱말:', nxt or '반복 예문이 아직 부족')
        st.caption('어간 앞부분 일치로 찾는 단순 규칙. "가다"의 "가"가 "가방"에도 걸릴 수 있으니 위 형태 목록을 확인할 것.')

        st.divider()
        st.subheader('🌱 동적 지도: Semantic Map + Word Gravity + Markov')
        if st.button('지도 다시 만들기', key='rebuild_map') or 'dynamic_state' not in st.session_state:
            st.session_state['dynamic_state'] = build_dynamic()
        state = st.session_state['dynamic_state']
        st.write(f"승인 문서 {state['docs']} · 노드 {len(state['map']['freq'])} · 연결 {len(state['map']['edges'])} · 군집 {len(state['clusters'])}")
        dyn_vocab = sorted(state['map']['freq'])
        if dyn_vocab:
            sel = st.selectbox('관찰된 노드', dyn_vocab, key='dynamic_center')
            d = explore_dynamic(sel, state)
            c1, c2 = st.columns(2)
            with c1:
                st.write('**함께 나온 낱말**'); st.dataframe([{'낱말': a, '가중치': b} for a, b in d['cooccurrence']], hide_index=True)
                st.write('**Markov 다음 낱말**'); st.write(d['sequences'])
            with c2:
                st.write('**Word Gravity 끌림**'); st.dataframe([{'낱말': a, '끌림': b} for a, b in d['gravity']], hide_index=True)
                st.write('**추정 갈래**'); st.json(d['branch'])
            st.dataframe([{'이름': c['name'], '구성': ', '.join(c['members']), '크기': c['size']} for c in state['clusters'][:15]], hide_index=True)
        else:
            st.info('연결이 아직 없음. 같은 낱말이 반복되는 예문을 몇 개 더 넣고 다시 만들기.')
        st.caption('함께 나옴·끌림·순서는 유의어나 문법 관계의 증거가 아니다.')

        st.divider()
        st.subheader('🧭 NM 전략 확률 / 감사 기록')
        st.dataframe(policy(), hide_index=True, use_container_width=True)
        st.caption('이전 버전에서 피드백을 누른 적이 있다면, 저장된 확률에 시작값 치우침(retry 50%)이 섞여 있다. 아래 버튼으로 초기화 권장.')
        if st.button('NM 전략 확률 초기화 (감사 기록은 유지)', key='nm_reset'):
            reset_policy(); st.success('초기화함')
        st.dataframe(audit(), use_container_width=True)

st.divider()
st.caption(L('Prototipe untuk satu pelajar · Jangan menulis informasi pribadi di jawaban.',
             '학습자 1명용 시제품 · 답에 개인정보를 쓰지 마세요'))
