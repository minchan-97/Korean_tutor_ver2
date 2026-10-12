"""학습 기록 저장(SQLite), 숙달도·복습 일정, 다음 문제 고르기, 데모 채점."""
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def now():
    return datetime.now(KST)


def db_path():
    return os.getenv('DATABASE_PATH', 'learner.db')


def connection():
    con = sqlite3.connect(db_path())
    con.row_factory = sqlite3.Row
    con.execute('CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY, ts TEXT, exercise TEXT, answer TEXT, score INTEGER, correct INTEGER, diagnosis TEXT, strategy TEXT, feedback TEXT)')
    con.execute('CREATE TABLE IF NOT EXISTS mastery (topic TEXT PRIMARY KEY, value REAL, due TEXT)')
    # 기존 DB 호환: 한국어 피드백 칸이 없으면 추가 (이전 버전 DB도 그대로 열린다)
    cols = {r['name'] for r in con.execute('PRAGMA table_info(attempts)')}
    if 'feedback_ko' not in cols:
        con.execute('ALTER TABLE attempts ADD COLUMN feedback_ko TEXT')
    con.commit()
    return con


def save_attempt(exercise, answer, result, strategy):
    """시도 1건 저장 + 주제 숙달도/복습일 갱신.

    변경: 예전 버전은 여기서 '방금 답의 정답 여부'로 전략 가중치(policy)를 올렸다.
    README의 원칙(전략은 학습자 명시 피드백으로만 학습)과 어긋나서 제거했다.
    전략 학습은 molang_adapter.update() 한 곳에서만 일어난다.
    """
    con = connection()
    score = result['score']
    con.execute('INSERT INTO attempts(ts,exercise,answer,score,correct,diagnosis,strategy,feedback,feedback_ko) VALUES (?,?,?,?,?,?,?,?,?)',
                (now().isoformat(), exercise['id'], answer, score, int(result['correct']), result['diagnosis_id'],
                 strategy, result['explanation_id'], result.get('explanation_ko', '')))
    old = con.execute('SELECT value FROM mastery WHERE topic=?', (exercise['topic'],)).fetchone()
    value = float(old['value']) if old else 0.2
    value = max(0.0, min(1.0, value * 0.75 + (score / 100) * 0.25))
    # 숙달도가 낮을수록 빨리 다시 나온다: 0.5 미만 → 1일, 0.8 미만 → 3일, 그 이상 → 7일
    days = 1 if value < 0.5 else (3 if value < 0.8 else 7)
    con.execute('INSERT INTO mastery(topic,value,due) VALUES(?,?,?) ON CONFLICT(topic) DO UPDATE SET value=excluded.value,due=excluded.due',
                (exercise['topic'], value, (now() + timedelta(days=days)).isoformat()))
    con.commit()
    con.close()
    return value


def history(limit=40):
    con = connection()
    rows = con.execute('SELECT * FROM attempts ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def mastery():
    con = connection()
    rows = con.execute('SELECT * FROM mastery').fetchall()
    con.close()
    return {r['topic']: dict(r) for r in rows}


def next_exercise(exercises, current_id=None):
    """다음에 풀 문제 고르기 (실제로 쓰이는 복습 일정).

    순서: ① 한 번도 안 푼 문제(목록 순) → ② 복습일이 지난 주제 중 숙달도 낮은 것
         → ③ 그래도 없으면 숙달도가 가장 낮은 주제. 지금 문제는 되도록 피한다.
    """
    con = connection()
    done = {r['exercise'] for r in con.execute('SELECT DISTINCT exercise FROM attempts')}
    last_ok = {r['exercise']: r['correct'] for r in con.execute(
        'SELECT exercise, correct FROM attempts WHERE id IN (SELECT MAX(id) FROM attempts GROUP BY exercise)')}
    con.close()
    pool = [e for e in exercises if e['id'] != current_id] or exercises
    fresh = [e for e in pool if e['id'] not in done]
    if fresh:
        return fresh[0]['id']
    levels = mastery()
    t = now().isoformat()

    def key(e):
        m = levels.get(e['topic'], {'value': 0.0, 'due': ''})
        overdue = 0 if (m['due'] or '') <= t else 1          # 복습일 지난 것 먼저
        wrong_last = 0 if not last_ok.get(e['id'], 0) else 1  # 마지막에 틀린 문제 먼저
        return (overdue, wrong_last, m['value'])
    return sorted(pool, key=key)[0]['id']


def _norm(x):
    """띄어쓰기·마침표·물음표 차이는 무시하고 비교."""
    return re.sub(r'[\s.?!,]', '', x or '')


def demo_evaluate(exercise, answer):
    """API 키가 없을 때의 채점. 등록된 정답 표현(reference+accepted)과만 비교한다.
    목록에 없는 맞는 문장은 틀렸다고 나올 수 있다 — 화면에도 그렇게 안내된다."""
    ok_forms = [exercise['reference']] + exercise.get('accepted', [])
    correct = _norm(answer) in {_norm(f) for f in ok_forms}
    diagnosis = 'none' if correct else 'expression'
    if not correct:
        past = re.search(r'(었|았|갔|했|났|왔)', exercise['reference'])
        if past and not re.search(r'(었|았|갔|했|났|왔)', answer):
            diagnosis = 'tense'
        elif not any(p in _norm(answer) for p in ['을', '를', '이', '가', '에', '은', '는']):  # 조사 글자가 하나도 없으면
            diagnosis = 'particle'
    msgs = {
        'none': ('Benar! Cocok dengan jawaban yang tersedia.',                      # 🇰🇷 정답! 등록된 답과 일치
                 '정답! 등록된 답과 일치합니다.'),
        'tense': ('Kalimat ini tentang masa lalu. Periksa bentuk lampau (었/았).',   # 🇰🇷 과거 이야기다. 과거형(었/았)을 확인하자
                  '과거 문장입니다. 과거형(었/았)을 확인하세요.'),
        'particle': ('Sepertinya partikel (을/를, 이/가, 에, 에서) belum ada.',       # 🇰🇷 조사가 빠진 것 같다
                     '조사(을/를, 이/가, 에, 에서)가 빠진 것 같습니다.'),
        'expression': ('Mode demo: jawaban hanya dibandingkan dengan beberapa contoh, jadi jawaban lain yang benar bisa dianggap salah.',  # 🇰🇷 데모 모드: 몇 개 예시와만 비교하므로 맞는 다른 답도 오답 처리될 수 있음
                       '데모 모드: 몇 개 예시와만 비교하므로 맞는 다른 답도 오답 처리될 수 있습니다.'),
    }
    exp_id, exp_ko = msgs[diagnosis]
    return {'correct': correct, 'score': 100 if correct else 30, 'reference': exercise['reference'],
            'corrected': '', 'diagnosis_id': diagnosis,
            'explanation_id': exp_id, 'explanation_ko': exp_ko,
            'hint_id': 'Perhatikan urutan kata, partikel, dan bentuk kata kerja.',  # 🇰🇷 어순, 조사, 동사 형태를 살펴보자
            'hint_ko': '어순, 조사, 동사 형태를 살펴보세요.',
            'suggested_words': []}
