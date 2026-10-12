"""몰랑이 원본 ThoughtStructure(NM)로 '다음 학습 전략'을 고르고, Markov 자석 낱말을 계산하는 어댑터.
출처를 모르는 옛 pkl은 읽지 않는다 — 이 학습자는 깨끗한 상태에서 시작한다.
"""
import json
import random
from collections import defaultdict
from molang_core.thought_structure import ThoughtStructure, JudgmentNode
from molang_core import markov_mass
from engine import connection

DIAGNOSES = ['tense', 'particle', 'word_order', 'vocabulary', 'expression', 'spelling', 'none']
STRATEGIES = {
    'hint': 'Petunjuk bertahap',   # 🇰🇷 단계별 힌트
    'blocks': 'Blok kata',         # 🇰🇷 낱말 블록 맞추기
    'example': 'Contoh tambahan',  # 🇰🇷 추가 예문 보기
    'retry': 'Coba lagi',          # 🇰🇷 다시 써 보기
}


def _schema(con):
    con.execute("CREATE TABLE IF NOT EXISTS nm_state (id INTEGER PRIMARY KEY CHECK(id=1), transitions TEXT NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS nm_audit (id INTEGER PRIMARY KEY, exercise TEXT, diagnosis TEXT, path TEXT, probabilities TEXT, feedback REAL, created TEXT DEFAULT CURRENT_TIMESTAMP)")
    con.execute("CREATE TABLE IF NOT EXISTS word_docs (id INTEGER PRIMARY KEY, text TEXT NOT NULL, source TEXT NOT NULL, approved INTEGER NOT NULL DEFAULT 0)")
    con.commit()


def new_tree():
    t = ThoughtStructure(learning_rate=0.1, continuity=0.8)
    t.add_node(JudgmentNode('root', 'Pilih strategi pengajaran'), is_root=True)  # 🇰🇷 가르칠 전략 고르기
    for d in DIAGNOSES:
        t.add_node(JudgmentNode(d, 'Kesulitan: ' + d))  # 🇰🇷 어려움: (진단명)
        t.add_branch('root', d, 1.0)
        for s in STRATEGIES:
            leaf = f'{d}:{s}'
            t.add_node(JudgmentNode(leaf, STRATEGIES[s], directive=s, is_terminal=True))
            t.add_branch(d, leaf, 1.0)
    # 수정: 원본 add_branch는 하나 추가할 때마다 정규화한다. 그래서 1.0을 네 번 넣으면
    # 0.125 / 0.125 / 0.25 / 0.5 가 되어, 마지막에 넣은 'retry'가 처음부터 50%였다.
    # 원본 모듈은 건드리지 않고, 여기서 시작 확률을 진짜 균등으로 다시 맞춘다.
    for frm, targets in t.transitions.items():
        for to in targets:
            targets[to] = 1.0 / len(targets)
    return t


def _load(con):
    t = new_tree()
    row = con.execute('SELECT transitions FROM nm_state WHERE id=1').fetchone()
    if row:
        saved = json.loads(row[0])
        for frm, targets in saved.items():
            if frm in t.transitions:
                for to, p in targets.items():
                    if to in t.transitions[frm]:
                        t.transitions[frm][to] = float(p)
                t._normalize(frm)
    return t


def choose(diagnosis, exercise_id):
    """진단(diagnosis)은 채점기가 정하고, 그 아래 전략 선택은 NM 전이확률로 한다(LLM이 고르지 않음)."""
    if diagnosis not in DIAGNOSES:
        diagnosis = 'expression'
    con = connection(); _schema(con); t = _load(con); con.close()

    def chooser(node, candidates, candidate_nodes, probs, context):
        if node.id == 'root':
            return diagnosis
        return random.choices(candidates, weights=probs, k=1)[0]
    rec = t.traverse(choose_fn=chooser, context=f'{exercise_id}:{diagnosis}')
    return rec.path[-1].split(':')[-1], rec


def update(exercise_id, diagnosis, rec, feedback):
    """학습자가 '도움이 됐다/안 됐다'를 눌렀을 때만 호출된다 (+1 / -1)."""
    con = connection(); _schema(con); t = _load(con)
    t.learn(rec, max(-1., min(1., float(feedback))))
    con.execute('INSERT INTO nm_state(id,transitions) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET transitions=excluded.transitions',
                (json.dumps(t.transitions, ensure_ascii=False),))
    con.execute('INSERT INTO nm_audit(exercise,diagnosis,path,probabilities,feedback) VALUES(?,?,?,?,?)',
                (exercise_id, diagnosis, json.dumps(rec.path, ensure_ascii=False), json.dumps(rec.at_probs, ensure_ascii=False), feedback))
    con.commit(); con.close()


def reset_policy():
    """저장된 NM 전략 확률을 지운다 (감사 기록은 남긴다). 이전 버전의 치우친 시작값을 없앨 때 쓴다."""
    con = connection(); _schema(con)
    con.execute('DELETE FROM nm_state'); con.commit(); con.close()


def policy():
    con = connection(); _schema(con); t = _load(con); con.close()
    return [{'진단': d, '전략': s, '확률': round(t.transitions[d][f'{d}:{s}'], 4)} for d in DIAGNOSES for s in STRATEGIES]


def audit():
    con = connection(); _schema(con)
    rows = con.execute('SELECT * FROM nm_audit ORDER BY id DESC LIMIT 30').fetchall(); con.close()
    return [dict(r) for r in rows]


def add_document(text, source='learner', approved=False):
    text = text.strip()[:500]
    if not text:
        return
    con = connection(); _schema(con)
    # 같은 승인 문장을 두 번 넣지 않는다 (중복되면 Markov 빈도가 부풀려진다)
    if approved and con.execute('SELECT 1 FROM word_docs WHERE text=? AND approved=1', (text,)).fetchone():
        con.close(); return
    con.execute('INSERT INTO word_docs(text,source,approved) VALUES(?,?,?)', (text, source, int(approved)))
    con.commit(); con.close()


def approved_documents(limit=200):
    con = connection(); _schema(con)
    rows = [dict(r) for r in con.execute('SELECT id,text,source FROM word_docs WHERE approved=1 ORDER BY id DESC LIMIT ?', (limit,))]
    con.close(); return rows


def _stem(word):
    """사전형 → 어간 (아주 단순한 규칙). '먹다'→'먹', '공부하다'→'공부', '을/를' 같은 조사 노드는 None.
    형태소 분석기가 아니다. '가다'의 '가'는 '가방'에도 걸릴 수 있어서, 화면에 실제로 잡힌 형태를 함께 보여준다."""
    if '/' in word or len(word) == 1 and word in {'에', '을', '를', '이', '가'}:
        return None
    if word.endswith('하다') and len(word) > 2:
        return word[:-2]
    if word.endswith('다') and len(word) >= 2:
        return word[:-1]
    return word


def magnet_neighbors(word):
    """수정: 예전에는 '먹다'(사전형)로 찾았는데 말뭉치에는 '먹어요/먹었어요'만 있어서 늘 빈 결과였다.
    이제 어간으로 시작하는 실제 형태들을 모아 그 다음에 오는 낱말을 합산한다.
    반환: (다음 낱말 목록, 잡힌 형태 목록)"""
    docs = approved_documents(500)
    stem = _stem(word)
    if not docs or not stem:
        return [], []
    mk = markov_mass.count(docs)
    forms = sorted(w for w in mk['seen'] if w.startswith(stem))
    merged = defaultdict(float)
    for f in forms:
        for b, p in markov_mass.next_of(mk, f, k=8):
            if b not in forms:
                merged[b] += p
    total = sum(merged.values()) or 1.0
    out = sorted(((b, round(p / total, 3)) for b, p in merged.items()), key=lambda x: -x[1])[:8]
    return out, forms
