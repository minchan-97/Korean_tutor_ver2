"""Approved-corpus dynamic graph, using original Molang semantic_map, word_gravity and markov_mass.
Co-occurrence is NOT a validated linguistic relation. No learner answers or LLM suggestions auto-approved.
"""
import sqlite3
from collections import Counter
from engine import connection
from molang_core import semantic_map as S, word_gravity as G, markov_mass as M

def init():
    con=connection()
    con.execute('CREATE TABLE IF NOT EXISTS magnet_candidates (id INTEGER PRIMARY KEY, korean TEXT NOT NULL, indonesian TEXT NOT NULL, source TEXT NOT NULL, status TEXT NOT NULL DEFAULT "pending", created TEXT DEFAULT CURRENT_TIMESTAMP)')
    con.commit();con.close()

def propose(items, source='llm'):
    init(); con=connection(); count=0
    for item in items[:12]:
        ko=str(item.get('korean','')).strip()[:70]; idn=str(item.get('indonesian','')).strip()[:150]
        if not ko or not idn: continue
        existing=con.execute('SELECT 1 FROM magnet_candidates WHERE korean=? AND indonesian=? AND status IN ("pending","approved")',(ko,idn)).fetchone()
        if existing: continue
        con.execute('INSERT INTO magnet_candidates(korean,indonesian,source,status) VALUES(?,?,?,"pending")',(ko,idn,source));count+=1
    con.commit();con.close();return count

def candidates(status='pending'):
    init();con=connection();rows=[dict(x) for x in con.execute('SELECT * FROM magnet_candidates WHERE status=? ORDER BY id DESC LIMIT 100',(status,))];con.close();return rows

def review(candidate_id,approve):
    init();con=connection();row=con.execute('SELECT korean FROM magnet_candidates WHERE id=? AND status="pending"',(candidate_id,)).fetchone()
    if row:
        con.execute('UPDATE magnet_candidates SET status=? WHERE id=?',('approved' if approve else 'rejected',candidate_id))
    con.commit();con.close();return bool(row)

def documents():
    con=connection()
    con.execute('CREATE TABLE IF NOT EXISTS word_docs (id INTEGER PRIMARY KEY, text TEXT NOT NULL, source TEXT NOT NULL, approved INTEGER NOT NULL DEFAULT 0)')
    rows=[dict(x) for x in con.execute('SELECT text,source FROM word_docs WHERE approved=1 ORDER BY id DESC LIMIT 1200')]
    con.close();return rows

def build():
    docs=documents()
    texts=[x['text'] for x in docs]
    gmap=S.build(texts)
    # Original semantic_map suppresses any token occurring in >25% of docs.
    # In a tiny single-learner corpus this removes virtually every token.
    # For <=20 docs, retain its original tokenizer but use a small-corpus
    # co-occurrence fallback; provenance remains "co-occurrence", not grammar.
    if len(docs) <= 20 and texts:
        token_docs=[list(dict.fromkeys(S._words(t)))[:14] for t in texts]
        freq=Counter(w for row in token_docs for w in row)
        pairs=Counter()
        for row in token_docs:
            for i,a in enumerate(row):
                for b in row[i+1:]:
                    if a!=b:pairs[tuple(sorted((a,b)))]+=1
        gmap={'freq':dict(freq),'edges':{pair:round(c/(freq[pair[0]]*freq[pair[1]])**.5,3) for pair,c in pairs.items() if c>=2},'docs':len(texts)}
    cls=S.clusters(gmap)
    mk=M.count(docs)
    mk_mass=M.masses(mk)
    # original mass formula; Markov mass blended using original blend function
    base=G.masses(gmap)
    mass=M.blend(base,mk_mass,0.35)
    return {'docs':len(docs),'map':gmap,'clusters':cls,'markov':mk,'mass':mass}

def explore(word, state=None, limit=10):
    state=state or build(); g=state['map']; mass=state['mass']; cls=state['clusters']
    direct=S.neighbors(g,word,k=limit)
    gravity=sorted([(neighbor,G.pull(g,mass,word,neighbor)) for neighbor,_ in direct],key=lambda x:-x[1])
    return {'word':word,'cooccurrence':direct,'gravity':gravity,'sequences':M.next_of(state['markov'],word,k=limit),'branch':G.home_branch(g,mass,cls,word),'mass':mass.get(word,0.0)}
