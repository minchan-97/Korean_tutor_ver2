"""단어 은행 — 난이도별 단어 생성 · 역번역 검증 · 간격 반복(SRS) · 연습 문제 자동 생성.

흐름
  1) 생성  : LLM이 수준·주제에 맞는 단어 + 예문(한국어/인도네시아어)을 만든다.
  2) 검증  : 다른 호출이 '인도네시아어만' 보고 한국어로 되돌려 번역한다(원문을 안 보여줌).
            → 선생님은 인도네시아어를 몰라도 '원래 한국어 ↔ 역번역 한국어'만 비교하면 된다.
            + 코드 규칙 검사(예문에 그 단어가 있나, 길이가 수준에 맞나, 한글만인가).
  3) 상태  : 모두 통과 → auto(연습에 사용) / 하나라도 실패 → flagged(교사 검토 전 사용 안 함)
            교사 승인 → approved(예문이 몰랑이 말뭉치에도 들어감) / 거절 → rejected
            '엄격 모드'를 켜면 approved(+seed)만 연습에 나온다.
  4) 연습  : 단어마다 상자(box) 번호가 있고, 맞히면 올라가고 틀리면 1로 내려간다.
            상자가 올라갈수록 문제가 어려워진다: 뜻 고르기 → 단어 고르기 → 블록 문장 → 직접 쓰기.
            연습 문제는 저장된 단어에서 코드가 만든다 → 연습할 때는 API 비용이 없다(쓰기 채점 제외).

한계: 역번역 비교와 규칙 검사는 '이상 신호'를 잡는 장치지 정답 보증이 아니다. 원어민 검수가 가장 확실하다.
"""
import json
import random
import re
from datetime import timedelta
from engine import connection, now
from llm_client import configured, chat_json, verify_model

# ─── 수준 정의 ───────────────────────────────────────────────
LEVELS = {
    'A1': {'id': 'Pemula 1 (setara TOPIK 1)',   # 🇰🇷 초급1 (TOPIK 1급 수준)
           'ko': '초급1 (TOPIK 1급)', 'max_eojeol': 6,
           'grammar': '해요체 present/past (-아요/어요, -았어요/었어요), 이/가, 을/를, 은/는, 에, 에서, 안 negation, -고 싶다'},
    'A2': {'id': 'Pemula 2 (setara TOPIK 2)',   # 🇰🇷 초급2 (TOPIK 2급 수준)
           'ko': '초급2 (TOPIK 2급)', 'max_eojeol': 8,
           'grammar': 'A1 + -(으)ㄹ 거예요, -고 있다, -아서/어서 (reason), -지만, -(으)세요, -(으)러 가다, -고 (and)'},
    'B1': {'id': 'Menengah (setara TOPIK 3)',   # 🇰🇷 중급 (TOPIK 3급 수준)
           'ko': '중급 (TOPIK 3급)', 'max_eojeol': 12,
           'grammar': 'A2 + -(으)니까, -는데, -(으)면, -기 때문에, -(으)ㄴ/는/(으)ㄹ noun modifiers, -아/어야 하다, -(으)ㄹ 수 있다'},
}

TOPICS = {
    '음식': 'makanan',                    # 🇰🇷 음식
    '장소': 'tempat',                     # 🇰🇷 장소
    '교통': 'transportasi',               # 🇰🇷 교통
    '쇼핑': 'belanja',                    # 🇰🇷 쇼핑
    '가족·사람': 'keluarga & orang',      # 🇰🇷 가족·사람
    '시간·일상': 'waktu & kegiatan harian',  # 🇰🇷 시간·일상
    '날씨': 'cuaca',                      # 🇰🇷 날씨
    '감정': 'perasaan',                   # 🇰🇷 감정
    '학교·일': 'sekolah & pekerjaan',     # 🇰🇷 학교·일
    '건강': 'kesehatan',                  # 🇰🇷 건강
    '취미': 'hobi',                       # 🇰🇷 취미
    '여행': 'perjalanan',                 # 🇰🇷 여행
}

BOX_DAYS = [0, 1, 2, 4, 8, 16, 30]   # 상자 번호별 다음 복습까지 일수. 틀리면 상자 1 + 5분 뒤 다시
DAILY_NEW = 10                         # 하루 새 단어 최대 개수
TOPUP_BATCH = 8                        # 새 단어가 떨어지면 한 번에 만드는 개수

# ─── 기본 단어 (API 키 없어도 바로 쓸 수 있게) ───────────────────
# Claude가 작성 · 원어민 미검수 → 상태 'seed'로 구분된다.
# (한국어, 품사, 수준, 주제, 인니어 뜻, 한국어 뜻, 한국어 예문, 인니어 예문)  # 🇰🇷 인니어 예문의 뜻 = 한국어 예문
SEED = [
    ('사과', '명사', 'A1', '음식', 'apel', '사과(과일)', '저는 사과를 좋아해요.', 'Saya suka apel.'),
    ('우유', '명사', 'A1', '음식', 'susu', '우유', '아침에 우유를 마셔요.', 'Saya minum susu di pagi hari.'),
    ('빵', '명사', 'A1', '음식', 'roti', '빵', '저는 빵을 먹어요.', 'Saya makan roti.'),
    ('라면', '명사', 'A1', '음식', 'mi instan', '라면', '저는 라면을 자주 먹어요.', 'Saya sering makan mi instan.'),
    ('맛있다', '형용사', 'A1', '음식', 'enak', '맛있다', '김치가 맛있어요.', 'Kimchinya enak.'),
    ('맵다', '형용사', 'A1', '음식', 'pedas', '맵다', '이 음식은 매워요.', 'Makanan ini pedas.'),
    ('버스', '명사', 'A1', '교통', 'bus', '버스', '저는 버스를 타요.', 'Saya naik bus.'),
    ('지하철', '명사', 'A1', '교통', 'kereta bawah tanah', '지하철', '지하철로 학교에 가요.', 'Saya pergi ke sekolah naik kereta bawah tanah.'),
    ('타다', '동사', 'A1', '교통', 'naik (kendaraan)', '(탈것을) 타다', '저는 택시를 타요.', 'Saya naik taksi.'),
    ('병원', '명사', 'A1', '장소', 'rumah sakit', '병원', '내일 병원에 가요.', 'Besok saya pergi ke rumah sakit.'),
    ('은행', '명사', 'A1', '장소', 'bank', '은행', '은행이 어디예요?', 'Bank di mana?'),
    ('편의점', '명사', 'A1', '장소', 'minimarket', '편의점', '편의점에서 물을 사요.', 'Saya membeli air di minimarket.'),
    ('사다', '동사', 'A1', '쇼핑', 'membeli', '사다', '시장에서 과일을 사요.', 'Saya membeli buah di pasar.'),
    ('비싸다', '형용사', 'A1', '쇼핑', 'mahal', '비싸다', '이 가방은 비싸요.', 'Tas ini mahal.'),
    ('싸다', '형용사', 'A1', '쇼핑', 'murah', '(값이) 싸다', '시장 과일은 싸요.', 'Buah di pasar murah.'),
    ('어머니', '명사', 'A1', '가족·사람', 'ibu', '어머니', '어머니는 선생님이에요.', 'Ibu saya seorang guru.'),
    ('아버지', '명사', 'A1', '가족·사람', 'ayah', '아버지', '아버지는 회사에 다녀요.', 'Ayah saya bekerja di perusahaan.'),
    ('가족', '명사', 'A1', '가족·사람', 'keluarga', '가족', '우리 가족은 네 명이에요.', 'Keluarga kami ada empat orang.'),
    ('일어나다', '동사', 'A1', '시간·일상', 'bangun (tidur)', '(잠에서) 일어나다', '저는 일곱 시에 일어나요.', 'Saya bangun jam tujuh.'),
    ('자다', '동사', 'A1', '시간·일상', 'tidur', '자다', '저는 열한 시에 자요.', 'Saya tidur jam sebelas.'),
    ('주말', '명사', 'A1', '시간·일상', 'akhir pekan', '주말', '주말에 친구를 만나요.', 'Saya bertemu teman pada akhir pekan.'),
    ('날씨', '명사', 'A1', '날씨', 'cuaca', '날씨', '오늘 날씨가 좋아요.', 'Cuaca hari ini bagus.'),
    ('덥다', '형용사', 'A1', '날씨', 'panas (cuaca)', '(날씨가) 덥다', '오늘은 너무 더워요.', 'Hari ini panas sekali.'),
    ('춥다', '형용사', 'A1', '날씨', 'dingin (cuaca)', '(날씨가) 춥다', '겨울은 추워요.', 'Musim dingin itu dingin.'),
    ('비', '명사', 'A1', '날씨', 'hujan', '비', '지금 비가 와요.', 'Sekarang sedang hujan.'),
    ('행복하다', '형용사', 'A1', '감정', 'bahagia', '행복하다', '저는 지금 행복해요.', 'Saya bahagia sekarang.'),
    ('피곤하다', '형용사', 'A1', '감정', 'lelah / capek', '피곤하다', '오늘 너무 피곤해요.', 'Hari ini saya capek sekali.'),
    ('읽다', '동사', 'A1', '취미', 'membaca', '읽다', '저는 책을 읽어요.', 'Saya membaca buku.'),
    ('보다', '동사', 'A1', '취미', 'melihat / menonton', '보다', '주말에 영화를 봐요.', 'Saya menonton film pada akhir pekan.'),
    ('공부하다', '동사', 'A1', '학교·일', 'belajar', '공부하다', '저는 도서관에서 공부해요.', 'Saya belajar di perpustakaan.'),
    ('여행', '명사', 'A2', '여행', 'perjalanan / liburan', '여행', '다음 달에 부산으로 여행을 갈 거예요.', 'Bulan depan saya akan berlibur ke Busan.'),
    ('예약하다', '동사', 'A2', '여행', 'memesan (tempat)', '예약하다', '식당을 예약하고 싶어요.', 'Saya ingin memesan tempat di restoran.'),
    ('아프다', '형용사', 'A2', '건강', 'sakit', '아프다', '머리가 아파서 병원에 갔어요.', 'Kepala saya sakit, jadi saya pergi ke rumah sakit.'),
    ('배우다', '동사', 'A2', '학교·일', 'belajar (dari orang lain)', '배우다', '저는 한국어를 배우고 있어요.', 'Saya sedang belajar bahasa Korea.'),
    ('갈아타다', '동사', 'A2', '교통', 'berganti (kendaraan)', '갈아타다', '다음 역에서 갈아타세요.', 'Silakan berganti kereta di stasiun berikutnya.'),
    ('약', '명사', 'A2', '건강', 'obat', '약', '감기 때문에 약을 먹고 있어요.', 'Saya sedang minum obat karena flu.'),
]


# ─── DB ────────────────────────────────────────────────────
def _schema(con):
    con.execute('''CREATE TABLE IF NOT EXISTS vocab (
        id INTEGER PRIMARY KEY, korean TEXT UNIQUE NOT NULL, pos TEXT, level TEXT, topic TEXT,
        meaning_id TEXT, meaning_ko TEXT, example_ko TEXT, example_id TEXT,
        back_meaning_ko TEXT, back_example_ko TEXT, checks TEXT, status TEXT, source TEXT, created TEXT)''')
    con.execute('CREATE TABLE IF NOT EXISTS srs (word_id INTEGER PRIMARY KEY, box INTEGER, due TEXT, right INTEGER DEFAULT 0, wrong INTEGER DEFAULT 0, first_seen TEXT, last TEXT)')
    con.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    con.commit()


def _db():
    con = connection(); _schema(con)
    if con.execute('SELECT COUNT(*) FROM vocab').fetchone()[0] == 0:
        for s in SEED:
            item = dict(zip(['korean', 'pos', 'level', 'topic', 'meaning_id', 'meaning_ko', 'example_ko', 'example_id'], s))
            checks = rule_checks(item, item['level'])
            con.execute('INSERT OR IGNORE INTO vocab(korean,pos,level,topic,meaning_id,meaning_ko,example_ko,example_id,checks,status,source,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                        (*s, json.dumps(checks, ensure_ascii=False), 'seed', 'seed', now().isoformat()))
        con.commit()
    return con


def get_setting(key, default=''):
    con = _db(); row = con.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone(); con.close()
    return row['value'] if row else default


def set_setting(key, value):
    con = _db()
    con.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, str(value)))
    con.commit(); con.close()


def usable_statuses():
    """엄격 모드: 교사 승인(approved)과 기본 단어(seed)만. 기본: 자동 검증 통과(auto)도 포함."""
    return ('approved', 'seed') if get_setting('require_approval', '0') == '1' else ('approved', 'seed', 'auto')


# ─── 검증 규칙 (코드로, 투명하게) ─────────────────────────────
def _cho(ch):
    return (ord(ch) - 0xAC00) // 588 if '가' <= ch <= '힣' else None


def _jung(ch):
    return ((ord(ch) - 0xAC00) % 588) // 28 if '가' <= ch <= '힣' else None


# 활용하면서 모음이 바뀌는 경우: ㅗ→ㅘ(보→봐), ㅜ→ㅝ(주→줘), ㅣ→ㅕ(마시→마셔), ㅡ→ㅓ/ㅏ(쓰→써, 아프→아파), ㅚ→ㅙ(되→돼)
_JUNG_OK = {(8, 9), (13, 14), (20, 6), (18, 4), (18, 0), (11, 10)}


def _same_syllable_family(a, b):
    return _cho(a) == _cho(b) and (_jung(a) == _jung(b) or (_jung(a), _jung(b)) in _JUNG_OK)


def contains_word(korean, sentence):
    """예문에 그 단어가 들어 있나. 명사는 그대로 찾고, 용언은 어간으로 찾는다.
    불규칙(맵다→매워요, 보다→봐요)을 위해 어간 마지막 글자는 초성이 같고 모음이 같거나
    규칙적으로 바뀐 경우 통과시킨다. 모르다→몰라요 같은 경우는 놓친다(검토 대상으로 걸림)."""
    word = korean.strip()
    if word in sentence:
        return True
    if not word.endswith('다') or len(word) < 2:
        return False
    stem = word[:-2] if word.endswith('하다') and len(word) > 2 else word[:-1]
    if word.endswith('하다') and len(word) > 2:
        return stem in sentence
    if stem in sentence:
        return True
    prefix, last = stem[:-1], stem[-1]
    for i, ch in enumerate(sentence):
        if _cho(ch) is not None and _same_syllable_family(last, ch) and sentence[max(0, i - len(prefix)):i] == prefix:
            return True
    return False


def similarity(a, b):
    """한글 두 글자 묶음(bigram) 겹침 비율 0~1. 띄어쓰기·문장부호 무시."""
    def grams(s):
        s = re.sub(r'[^가-힣]', '', s or '')
        return {s[i:i + 2] for i in range(len(s) - 1)} or ({s} if s else set())
    A, B = grams(a), grams(b)
    return len(A & B) / len(A | B) if A and B else 0.0


def rule_checks(item, level, back=None):
    ex = item.get('example_ko', '')
    checks = {
        '한글 예문': not re.search(r'[A-Za-z]', ex) and bool(re.search(r'[가-힣]', ex)),
        '예문에 단어 포함': contains_word(item.get('korean', ''), ex),
        f"길이 {LEVELS[level]['max_eojeol']}어절 이하": len(ex.split()) <= LEVELS[level]['max_eojeol'],
        '인니어 칸 채움': bool(item.get('meaning_id')) and bool(item.get('example_id')),
    }
    if back is not None:
        bm, be = back.get('meaning_ko', ''), back.get('sentence_ko', '')
        gloss_parts = [p for p in re.split(r'[,/·()\s]+', item.get('meaning_ko', '')) if len(p) >= 1]
        checks['뜻 역번역 일치'] = (contains_word(item['korean'], bm) or any(p in bm for p in gloss_parts if len(p) >= 2)
                              or similarity(item.get('meaning_ko', ''), bm) >= 0.3)
        checks['예문 역번역 유사(≥0.3)'] = similarity(ex, be) >= 0.3
    return checks


# ─── 생성 ───────────────────────────────────────────────────
GEN_SYSTEM = '''You create Korean vocabulary cards for a native Indonesian speaker learning Korean.
Return ONLY a JSON object: {"items": [ ... ]}. Each item has:
- korean: the word in dictionary form (verbs/adjectives end in 다). No romanization.
- pos: one of 명사, 동사, 형용사, 부사, 표현
- meaning_id: short, natural Indonesian meaning (add a clarifying note in parentheses if needed)
- meaning_ko: short Korean gloss for a Korean teacher
- example_ko: ONE natural 해요체 sentence that uses the word, at most {max_eojeol} eojeol (space-separated chunks),
  using ONLY grammar allowed at this level: {grammar}
- example_id: a natural Indonesian translation of example_ko
Rules: high-frequency, useful for daily life in Korea, matching the level and topic. No proper nouns, no duplicates,
nothing from the "avoid" list. Avoid words whose only common use is sensitive or offensive.'''

BACK_SYSTEM = '''You are an independent translator. Translate each Indonesian text into natural Korean.
You are NOT told the original text; translate only what is written. Use 해요체 for sentences.
Return ONLY JSON: {"items": [{"i": <same i>, "meaning_ko": "...", "sentence_ko": "..."}]}'''


def back_translate(items):
    """인도네시아어만 보여주고 한국어로 되돌린다. 원래 한국어 단어·예문은 보내지 않는다."""
    payload = {'items': [{'i': i, 'meaning': it['meaning_id'], 'sentence': it['example_id']} for i, it in enumerate(items)]}
    data = chat_json(BACK_SYSTEM, payload, model=verify_model(), temperature=0.0)
    out = {}
    for row in data.get('items') or []:
        if isinstance(row, dict) and isinstance(row.get('i'), int):
            out[row['i']] = {'meaning_ko': str(row.get('meaning_ko', ''))[:120], 'sentence_ko': str(row.get('sentence_ko', ''))[:250]}
    return out


def generate(level, topic, n=8):
    """새 단어 n개 생성 → 역번역 → 규칙 검사 → 저장. 반환: {'added', 'flagged', 'skipped'}"""
    if not configured():
        raise RuntimeError('OPENAI_API_KEY가 없어 생성할 수 없습니다.')
    con = _db()
    existing = {r['korean'] for r in con.execute('SELECT korean FROM vocab')}
    same_level = [r['korean'] for r in con.execute('SELECT korean FROM vocab WHERE level=? ORDER BY id DESC LIMIT 400', (level,))]
    con.close()
    system = GEN_SYSTEM.replace('{max_eojeol}', str(LEVELS[level]['max_eojeol'])).replace('{grammar}', LEVELS[level]['grammar'])
    data = chat_json(system, {'level': LEVELS[level]['ko'], 'topic': f'{topic} ({TOPICS.get(topic, "")})',
                              'count': n, 'avoid': same_level}, temperature=0.8)
    items = []
    for raw in (data.get('items') or [])[:n + 4]:
        if not isinstance(raw, dict):
            continue
        it = {k: str(raw.get(k, '')).strip()[:250] for k in ['korean', 'pos', 'meaning_id', 'meaning_ko', 'example_ko', 'example_id']}
        it['korean'] = it['korean'][:30]
        if it['korean'] and it['korean'] not in existing and re.fullmatch(r'[가-힣 ]+', it['korean']):
            existing.add(it['korean']); items.append(it)
    if not items:
        return {'added': 0, 'flagged': 0, 'skipped': 0}
    try:
        back = back_translate(items)
    except Exception:
        back = {}
    added = flagged = 0
    con = _db()
    for i, it in enumerate(items):
        b = back.get(i, {'meaning_ko': '', 'sentence_ko': ''})
        checks = rule_checks(it, level, b)
        status = 'auto' if all(checks.values()) else 'flagged'
        cur = con.execute('INSERT OR IGNORE INTO vocab(korean,pos,level,topic,meaning_id,meaning_ko,example_ko,example_id,back_meaning_ko,back_example_ko,checks,status,source,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                          (it['korean'], it['pos'], level, topic, it['meaning_id'], it['meaning_ko'], it['example_ko'], it['example_id'],
                           b['meaning_ko'], b['sentence_ko'], json.dumps(checks, ensure_ascii=False), status, 'llm', now().isoformat()))
        if cur.rowcount:
            added += 1; flagged += status == 'flagged'
    con.commit(); con.close()
    return {'added': added, 'flagged': flagged, 'skipped': len(items) - added}


def generated_today():
    con = _db()
    c = con.execute("SELECT COUNT(*) FROM vocab WHERE source='llm' AND substr(created,1,10)=?", (now().date().isoformat(),)).fetchone()[0]
    con.close(); return c


def unseen_count(level):
    con = _db(); st = usable_statuses()
    c = con.execute(f"SELECT COUNT(*) FROM vocab v LEFT JOIN srs s ON s.word_id=v.id WHERE v.level=? AND s.word_id IS NULL AND v.status IN ({','.join('?' * len(st))})",
                    (level, *st)).fetchone()[0]
    con.close(); return c


def topup(level):
    """새 단어가 5개 미만이면 자동으로 채운다. 하루 생성 한도(daily_cap) 안에서만. 가장 적게 만든 주제부터."""
    if not configured() or unseen_count(level) >= 5:
        return None
    if generated_today() >= int(get_setting('daily_cap', '60')):
        return None
    con = _db()
    counts = {t: 0 for t in TOPICS}
    for r in con.execute('SELECT topic, COUNT(*) c FROM vocab WHERE level=? GROUP BY topic', (level,)):
        if r['topic'] in counts:
            counts[r['topic']] = r['c']
    con.close()
    topic = min(counts, key=lambda t: (counts[t], random.random()))
    return generate(level, topic, TOPUP_BATCH)


# ─── 간격 반복 + 문제 만들기 ──────────────────────────────────
def _words(con, level=None, extra='', params=()):
    st = usable_statuses()
    q = f"SELECT v.*, s.box, s.due, s.right, s.wrong FROM vocab v LEFT JOIN srs s ON s.word_id=v.id WHERE v.status IN ({','.join('?' * len(st))})"
    args = list(st)
    if level:
        q += ' AND v.level=?'; args.append(level)
    return [dict(r) for r in con.execute(q + extra, (*args, *params))]


def pick_word(level):
    """① 복습일이 된 단어(오래 기다린 것부터) → ② 오늘 새 단어 한도 안에서 새 단어 → ③ 없으면 None."""
    con = _db(); t = now().isoformat()
    due = _words(con, level, ' AND s.box IS NOT NULL AND s.due<=? ORDER BY s.due', (t,))
    if due:
        con.close(); return due[0]
    new_today = con.execute('SELECT COUNT(*) FROM srs WHERE substr(first_seen,1,10)=?', (now().date().isoformat(),)).fetchone()[0]
    if new_today < DAILY_NEW:
        new = _words(con, level, ' AND s.word_id IS NULL ORDER BY v.id')
        if new:
            con.close(); return new[0]
    con.close(); return None


def _kind(box):
    if box is None:
        return 'intro'  # 처음 보는 단어는 먼저 카드로 보여준다
    return 'meaning' if box <= 1 else 'reverse' if box == 2 else 'blocks' if box == 3 else 'write'
    # 🇰🇷 처음: 단어 카드 / 상자 0~1: 뜻 고르기 / 2: 단어 고르기 / 3: 블록으로 예문 만들기 / 4 이상: 예문 직접 쓰기


def next_question(level):
    w = pick_word(level)
    return make_question(w, _kind(w['box']), level) if w else None


def make_question(w, kind, level):
    con = _db(); pool = _words(con, level) or []
    if len(pool) < 4:
        pool = _words(con)
    con.close()
    others = [p for p in pool if p['id'] != w['id']]
    random.shuffle(others)
    q = {'qid': f"w{w['id']}_{random.randint(1000, 9999)}", 'level': level, 'word': w, 'kind': kind}
    if kind == 'meaning':
        opts = [w['meaning_id']] + [o['meaning_id'] for o in others if o['meaning_id'] != w['meaning_id']][:3]
        random.shuffle(opts); q.update(options=opts, answer=w['meaning_id'])
    elif kind == 'reverse':
        opts = [w['korean']] + [o['korean'] for o in others][:3]
        random.shuffle(opts); q.update(options=opts, answer=w['korean'])
    elif kind == 'blocks':
        targets = w['example_ko'].split()
        distract = [tok for o in others for tok in o['example_ko'].split() if tok not in targets][:2]
        q.update(exercise={'id': q['qid'], 'blocks': targets + distract, 'targets': targets})
    else:
        q.update(exercise={'id': q['qid'], 'topic': w['topic'], 'level': level,
                           'instruction': f"Tulis dalam bahasa Korea: {w['example_id']}",  # 🇰🇷 한국어로 쓰세요: (인니어 예문)
                           'meaning_ko': f"'{w['example_ko']}' 쓰기 (단어: {w['korean']})",
                           'reference': w['example_ko'], 'accepted': [],
                           'blocks': w['example_ko'].split(), 'targets': w['example_ko'].split(),
                           'extra': (w['example_ko'], w['example_id'], w['example_ko'])})
    return q


def record(word_id, correct):
    """맞으면 상자 +1, 틀리면 상자 1로. 다음 복습일 = 상자별 일수 뒤."""
    con = _db()
    row = con.execute('SELECT box FROM srs WHERE word_id=?', (word_id,)).fetchone()
    box = (row['box'] if row else 0)
    box = min(box + 1, len(BOX_DAYS) - 1) if correct else 1
    # 틀린 단어는 5분 뒤 다시 (바로 같은 단어가 연달아 나오지 않게, 다른 단어 사이에 끼워 넣음)
    due = (now() + (timedelta(days=BOX_DAYS[box]) if correct else timedelta(minutes=5))).isoformat()
    t = now().isoformat()
    con.execute('''INSERT INTO srs(word_id,box,due,right,wrong,first_seen,last) VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(word_id) DO UPDATE SET box=excluded.box, due=excluded.due,
                   right=srs.right+excluded.right, wrong=srs.wrong+excluded.wrong, last=excluded.last''',
                (word_id, box, due, int(correct), int(not correct), t, t))
    con.commit(); con.close()
    return box


def level_progress(level):
    con = _db(); ws = _words(con, level); con.close()
    total = len(ws); learned = sum(1 for w in ws if (w['box'] or 0) >= 3)
    ready = total >= 15 and learned / max(1, total) >= 0.8
    due = sum(1 for w in ws if w['box'] is not None and (w['due'] or '') <= now().isoformat())
    return {'total': total, 'learned': learned, 'due': due, 'unseen': sum(1 for w in ws if w['box'] is None), 'ready': ready}


def word_list(level=None, include_all=False):
    con = _db()
    if include_all:
        q = 'SELECT v.*, s.box, s.right, s.wrong FROM vocab v LEFT JOIN srs s ON s.word_id=v.id'
        rows = [dict(r) for r in con.execute(q + (' WHERE v.level=?' if level else '') + ' ORDER BY v.id DESC', ((level,) if level else ()))]
    else:
        rows = _words(con, level, ' ORDER BY v.id')
    con.close(); return rows


def review_queue(limit=30):
    """교사 검토: 걸린 것(flagged) 먼저, 그다음 자동 통과(auto)."""
    con = _db()
    rows = [dict(r) for r in con.execute("SELECT * FROM vocab WHERE status IN ('flagged','auto') ORDER BY status='auto', id DESC LIMIT ?", (limit,))]
    con.close(); return rows


def set_status(word_id, status):
    con = _db(); con.execute('UPDATE vocab SET status=? WHERE id=?', (status, word_id)); con.commit()
    row = con.execute('SELECT example_ko FROM vocab WHERE id=?', (word_id,)).fetchone(); con.close()
    return row['example_ko'] if row else ''
