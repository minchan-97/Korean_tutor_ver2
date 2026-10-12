"""학습 데이터 — 어휘 지도(NODES/EDGES)와 연습 문제(EXERCISES).

읽는 법 (민찬기 선생님용)
  · 인도네시아어 문자열 옆의  # 🇰🇷 ...  주석이 그 뜻이다.
  · 연습 문제의 'meaning_ko' 는 교사 확인 모드에서 화면에도 함께 뜬다.
  · 인도네시아어가 이상해 보이면 주석과 비교해서 어긋난 곳을 찾으면 된다.
"""

# 관계 이름·품사 이름 → 한국어 (교사 확인 모드에서 화면 번역에 쓰인다)
LABEL_KO = {
    'kata kerja': '동사', 'kata benda': '명사', 'tempat': '장소', 'waktu': '시간 표현',
    'bentuk lampau': '과거형', 'bentuk sopan': '해요체(공손형)', 'sinonim': '유의어',
    'honorifik': '높임말', 'partikel': '조사', 'kata sifat': '형용사',
    'objek': '목적어', 'berkaitan': '관련', 'konjugasi': '활용', 'lampau': '과거',
    'pola tata bahasa': '문법 패턴', 'tujuan': '목적지', 'partikel tujuan': '도착점 조사(에)',
    'partikel kegiatan': '활동 장소 조사(에서)', 'aktivitas': '활동', 'waktu lampau': '과거 시간',
    'waktu kini': '현재 시간', 'kebalikan': '반대말', 'tempat tinggal': '사는 곳',
}

# 단어: (인도네시아어 뜻, 품사)
NODES = {
    '먹다': ('makan', 'kata kerja'),                    # 🇰🇷 먹다 / 동사
    '밥': ('nasi / makanan', 'kata benda'),             # 🇰🇷 밥, 식사 / 명사
    '마시다': ('minum', 'kata kerja'),                  # 🇰🇷 마시다 / 동사
    '물': ('air', 'kata benda'),                        # 🇰🇷 물 / 명사
    '커피': ('kopi', 'kata benda'),                     # 🇰🇷 커피 / 명사
    '학교': ('sekolah', 'tempat'),                      # 🇰🇷 학교 / 장소
    '시장': ('pasar', 'tempat'),                        # 🇰🇷 시장 / 장소
    '집': ('rumah', 'tempat'),                          # 🇰🇷 집 / 장소
    '가다': ('pergi', 'kata kerja'),                    # 🇰🇷 가다 / 동사
    '공부하다': ('belajar', 'kata kerja'),              # 🇰🇷 공부하다 / 동사
    '살다': ('tinggal / hidup', 'kata kerja'),          # 🇰🇷 살다(거주하다) / 동사
    '어제': ('kemarin', 'waktu'),                       # 🇰🇷 어제 / 시간 표현
    '오늘': ('hari ini', 'waktu'),                      # 🇰🇷 오늘 / 시간 표현
    '내일': ('besok', 'waktu'),                         # 🇰🇷 내일 / 시간 표현
    '친구': ('teman', 'kata benda'),                    # 🇰🇷 친구 / 명사
    '만나다': ('bertemu', 'kata kerja'),                # 🇰🇷 만나다 / 동사
    '좋아하다': ('suka', 'kata kerja'),                 # 🇰🇷 좋아하다 / 동사
    '있다': ('ada / punya', 'kata kerja'),              # 🇰🇷 있다 / 동사(존재·소유)
    '없다': ('tidak ada / tidak punya', 'kata kerja'),  # 🇰🇷 없다 / 동사(부재·무소유)
    '먹었어요': ('makan (lampau)', 'bentuk lampau'),     # 🇰🇷 먹었어요 = 먹었다(과거) / 과거형
    '갔어요': ('pergi (lampau)', 'bentuk lampau'),       # 🇰🇷 갔어요 = 갔다(과거) / 과거형
    '먹어요': ('makan', 'bentuk sopan'),                 # 🇰🇷 먹어요 / 해요체
    '가요': ('pergi', 'bentuk sopan'),                   # 🇰🇷 가요 / 해요체
    '식사하다': ('bersantap', 'sinonim'),                # 🇰🇷 식사하다(격식 있는 '먹다') / 유의어
    '드시다': ('makan (hormat)', 'honorifik'),           # 🇰🇷 드시다(먹다의 높임) / 높임말
    '을/를': ('penanda objek', 'partikel'),              # 🇰🇷 목적격 조사 / 조사
    '에': ('ke / di (tujuan, tempat berada)', 'partikel'),  # 🇰🇷 ~에(도착점·존재 장소) / 조사
    '에서': ('di (tempat aktivitas)', 'partikel'),       # 🇰🇷 ~에서(활동이 일어나는 장소) / 조사
}

# 단어 관계: (단어A, 단어B, 관계)
EDGES = [
    ('먹다', '밥', 'objek'),                # 🇰🇷 목적어
    ('먹다', '마시다', 'berkaitan'),        # 🇰🇷 관련
    ('마시다', '물', 'objek'),              # 🇰🇷 목적어
    ('마시다', '커피', 'objek'),            # 🇰🇷 목적어
    ('먹다', '먹어요', 'konjugasi'),        # 🇰🇷 활용
    ('먹다', '먹었어요', 'lampau'),         # 🇰🇷 과거
    ('먹다', '식사하다', 'sinonim'),        # 🇰🇷 유의어
    ('먹다', '드시다', 'honorifik'),        # 🇰🇷 높임말
    ('먹다', '을/를', 'pola tata bahasa'),  # 🇰🇷 문법 패턴
    ('가다', '학교', 'tujuan'),             # 🇰🇷 목적지
    ('가다', '시장', 'tujuan'),             # 🇰🇷 목적지
    ('가다', '가요', 'konjugasi'),          # 🇰🇷 활용
    ('가다', '갔어요', 'lampau'),           # 🇰🇷 과거
    ('가다', '에', 'pola tata bahasa'),     # 🇰🇷 문법 패턴
    ('학교', '에', 'partikel tujuan'),      # 🇰🇷 도착점 조사(에)
    ('학교', '에서', 'partikel kegiatan'),  # 🇰🇷 활동 장소 조사(에서)
    ('학교', '공부하다', 'aktivitas'),      # 🇰🇷 활동
    ('집', '공부하다', 'aktivitas'),        # 🇰🇷 활동
    ('살다', '집', 'tempat tinggal'),       # 🇰🇷 사는 곳
    ('어제', '갔어요', 'waktu lampau'),     # 🇰🇷 과거 시간
    ('어제', '먹었어요', 'waktu lampau'),   # 🇰🇷 과거 시간
    ('친구', '만나다', 'objek'),            # 🇰🇷 목적어
    ('오늘', '가요', 'waktu kini'),         # 🇰🇷 현재 시간
    ('내일', '가다', 'waktu'),              # 🇰🇷 시간 표현
    ('좋아하다', '커피', 'objek'),          # 🇰🇷 목적어
    ('있다', '없다', 'kebalikan'),          # 🇰🇷 반대말
]

# 주제(숙달도 집계 단위): 한국어 키 → 인도네시아어 표시명
TOPICS = {
    '먹다·마시다': 'makan & minum',               # 🇰🇷 먹다·마시다
    '과거형': 'bentuk lampau',                    # 🇰🇷 과거형
    '장소 조사(에/에서)': 'partikel tempat 에/에서',  # 🇰🇷 장소 조사
    '자기소개·이에요': 'perkenalan & 이에요/예요',   # 🇰🇷 자기소개·이에요/예요
    '있다·없다': 'ada / tidak ada',               # 🇰🇷 있다·없다
    '좋아하다': 'suka',                           # 🇰🇷 좋아하다
    '생활 표현': 'ungkapan sehari-hari',          # 🇰🇷 생활 표현(길 묻기·가격·부탁)
    '부정(안)': 'kalimat negatif (안)',           # 🇰🇷 부정문(안)
    '희망·미래': 'keinginan & masa depan',        # 🇰🇷 희망(-고 싶다)·미래(-ㄹ 거예요)
    '시간·숫자': 'jam & angka',                   # 🇰🇷 시간·숫자
    '연결(-고)': 'menyambung kalimat (-고)',      # 🇰🇷 문장 잇기(-고)
}

# 연습 문제
#   instruction : 학습자가 보는 인도네시아어 지시문
#   meaning_ko  : 지시문의 한국어 뜻 (교사용)
#   reference   : 기준 정답
#   accepted    : 데모 모드(API 키 없음)에서도 정답으로 인정할 다른 표현
#   blocks      : 블록 맞추기용 낱말(오답 블록 포함, 화면에서는 섞여서 나온다)
#   targets     : 블록 맞추기 정답 순서
#   extra       : 추가 예문 (한국어, 인도네시아어 뜻, 한국어 뜻)
EXERCISES = [
    {'id': 'ex1', 'level': 'A1', 'topic': '먹다·마시다',
     'instruction': 'Tulis dalam bahasa Korea: Saya makan nasi. (gaya sopan)',
     'meaning_ko': "'저는 밥을 먹어요'를 해요체로 쓰기",
     'reference': '저는 밥을 먹어요.', 'accepted': ['밥을 먹어요.', '저는 밥 먹어요.', '밥 먹어요.'],
     'blocks': ['저는', '밥을', '먹어요', '먹었어요', '학교에'], 'targets': ['저는', '밥을', '먹어요'],
     'extra': ('저는 빵을 먹어요.', 'Saya makan roti.', '저는 빵을 먹어요.')},
    {'id': 'ex2', 'level': 'A1', 'topic': '먹다·마시다',
     'instruction': 'Tulis dalam bahasa Korea: Saya minum air.',
     'meaning_ko': "'저는 물을 마셔요' 쓰기",
     'reference': '저는 물을 마셔요.', 'accepted': ['물을 마셔요.', '물 마셔요.', '저는 물 마셔요.'],
     'blocks': ['저는', '물을', '마셔요', '먹어요', '물에'], 'targets': ['저는', '물을', '마셔요'],
     'extra': ('저는 커피를 마셔요.', 'Saya minum kopi.', '저는 커피를 마셔요.')},
    {'id': 'ex3', 'level': 'A1', 'topic': '과거형',
     'instruction': 'Tulis dalam bahasa Korea: Kemarin saya makan nasi.',
     'meaning_ko': "'어제 저는 밥을 먹었어요' 쓰기 (과거형)",
     'reference': '저는 어제 밥을 먹었어요.', 'accepted': ['어제 밥을 먹었어요.', '어제 저는 밥을 먹었어요.', '저는 어제 밥 먹었어요.', '어제 밥 먹었어요.'],
     'blocks': ['저는', '어제', '밥을', '먹었어요', '먹어요'], 'targets': ['저는', '어제', '밥을', '먹었어요'],
     'extra': ('저는 어제 김치를 먹었어요.', 'Kemarin saya makan kimchi.', '저는 어제 김치를 먹었어요.')},
    {'id': 'ex4', 'level': 'A1', 'topic': '과거형',
     'instruction': 'Tulis dalam bahasa Korea: Kemarin saya pergi ke sekolah.',
     'meaning_ko': "'어제 저는 학교에 갔어요' 쓰기 (과거형)",
     'reference': '저는 어제 학교에 갔어요.', 'accepted': ['어제 학교에 갔어요.', '어제 저는 학교에 갔어요.'],
     'blocks': ['저는', '어제', '학교에', '갔어요', '가요', '학교에서'], 'targets': ['저는', '어제', '학교에', '갔어요'],
     'extra': ('저는 어제 시장에 갔어요.', 'Kemarin saya pergi ke pasar.', '저는 어제 시장에 갔어요.')},
    {'id': 'ex5', 'level': 'A1', 'topic': '장소 조사(에/에서)',
     'instruction': 'Tulis dalam bahasa Korea: Saya belajar di sekolah.',
     'meaning_ko': "'저는 학교에서 공부해요' 쓰기 (활동 장소 = 에서)",
     'reference': '저는 학교에서 공부해요.', 'accepted': ['학교에서 공부해요.'],
     'blocks': ['저는', '학교에서', '학교에', '공부해요', '가요'], 'targets': ['저는', '학교에서', '공부해요'],
     'extra': ('저는 집에서 공부해요.', 'Saya belajar di rumah.', '저는 집에서 공부해요.')},
    {'id': 'ex6', 'level': 'A1', 'topic': '장소 조사(에/에서)',
     'instruction': 'Tulis dalam bahasa Korea: Saya tinggal di Seoul.',
     'meaning_ko': "'저는 서울에 살아요' 쓰기 (에/에서 둘 다 가능)",
     'reference': '저는 서울에 살아요.', 'accepted': ['서울에 살아요.', '저는 서울에서 살아요.', '서울에서 살아요.'],
     'blocks': ['저는', '서울에', '살아요', '사요', '서울을'], 'targets': ['저는', '서울에', '살아요'],
     'extra': ('저는 부산에 살아요.', 'Saya tinggal di Busan.', '저는 부산에 살아요.')},
    {'id': 'ex7', 'level': 'A1', 'topic': '자기소개·이에요',
     'instruction': 'Tulis dalam bahasa Korea: Saya orang Indonesia.',
     'meaning_ko': "'저는 인도네시아 사람이에요' 쓰기",
     'reference': '저는 인도네시아 사람이에요.', 'accepted': ['인도네시아 사람이에요.'],
     'blocks': ['저는', '인도네시아', '사람이에요', '사람예요', '사람을'], 'targets': ['저는', '인도네시아', '사람이에요'],
     'extra': ('저는 한국 사람이에요.', 'Saya orang Korea.', '저는 한국 사람이에요.')},
    {'id': 'ex8', 'level': 'A1', 'topic': '자기소개·이에요',
     'instruction': 'Tulis dalam bahasa Korea: Ini buku.',
     'meaning_ko': "'이것은 책이에요' 쓰기",
     'reference': '이것은 책이에요.', 'accepted': ['이거 책이에요.', '이건 책이에요.', '이것은 책입니다.'],
     'blocks': ['이것은', '책이에요', '책예요', '책을'], 'targets': ['이것은', '책이에요'],
     'extra': ('이것은 가방이에요.', 'Ini tas.', '이것은 가방이에요.')},
    {'id': 'ex9', 'level': 'A1', 'topic': '있다·없다',
     'instruction': 'Tulis dalam bahasa Korea: Saya punya adik.',
     'meaning_ko': "'저는 동생이 있어요' 쓰기 (소유 = 이/가 있다)",
     'reference': '저는 동생이 있어요.', 'accepted': ['동생이 있어요.', '저는 동생이 한 명 있어요.', '동생이 한 명 있어요.'],
     'blocks': ['저는', '동생이', '동생을', '있어요', '없어요'], 'targets': ['저는', '동생이', '있어요'],
     'extra': ('저는 고양이가 있어요.', 'Saya punya kucing.', '저는 고양이가 있어요.')},
    {'id': 'ex10', 'level': 'A1', 'topic': '있다·없다',
     'instruction': 'Tulis dalam bahasa Korea: Saya tidak punya waktu.',
     'meaning_ko': "'저는 시간이 없어요' 쓰기",
     'reference': '저는 시간이 없어요.', 'accepted': ['시간이 없어요.', '시간 없어요.'],
     'blocks': ['저는', '시간이', '시간을', '없어요', '안 있어요'], 'targets': ['저는', '시간이', '없어요'],
     'extra': ('저는 돈이 없어요.', 'Saya tidak punya uang.', '저는 돈이 없어요.')},
    {'id': 'ex11', 'level': 'A1', 'topic': '좋아하다',
     'instruction': 'Tulis dalam bahasa Korea: Saya suka kopi.',
     'meaning_ko': "'저는 커피를 좋아해요' 쓰기",
     'reference': '저는 커피를 좋아해요.', 'accepted': ['커피를 좋아해요.', '저는 커피가 좋아요.', '커피가 좋아요.', '커피 좋아해요.'],
     'blocks': ['저는', '커피를', '커피가', '좋아해요', '좋아요해요'], 'targets': ['저는', '커피를', '좋아해요'],
     'extra': ('저는 김치를 좋아해요.', 'Saya suka kimchi.', '저는 김치를 좋아해요.')},
    {'id': 'ex12', 'level': 'A1', 'topic': '생활 표현',
     'instruction': 'Tulis dalam bahasa Korea: Toilet di mana?',
     'meaning_ko': "'화장실이 어디예요?' 쓰기 (길 묻기)",
     'reference': '화장실이 어디예요?', 'accepted': ['화장실 어디예요?', '화장실은 어디예요?', '화장실이 어디에 있어요?', '화장실이 어디 있어요?'],
     'blocks': ['화장실이', '화장실을', '어디예요?', '어디에요?'], 'targets': ['화장실이', '어디예요?'],
     'extra': ('지하철역이 어디예요?', 'Stasiun kereta bawah tanah di mana?', '지하철역이 어디예요?')},
    {'id': 'ex13', 'level': 'A1', 'topic': '생활 표현',
     'instruction': 'Tulis dalam bahasa Korea: Ini berapa harganya?',
     'meaning_ko': "'이거 얼마예요?' 쓰기 (가격 묻기)",
     'reference': '이거 얼마예요?', 'accepted': ['이것은 얼마예요?', '이건 얼마예요?', '이거 얼마에요?'],
     'blocks': ['이거', '얼마예요?', '몇 개예요?', '어디예요?'], 'targets': ['이거', '얼마예요?'],
     'extra': ('사과는 얼마예요?', 'Apel berapa harganya?', '사과는 얼마예요?')},
    {'id': 'ex14', 'level': 'A2', 'topic': '생활 표현',
     'instruction': 'Tulis dalam bahasa Korea: Tolong bicara pelan-pelan.',
     'meaning_ko': "'천천히 말해 주세요' 쓰기 (부탁)",
     'reference': '천천히 말해 주세요.', 'accepted': ['천천히 말씀해 주세요.', '좀 천천히 말해 주세요.', '천천히 말해주세요.'],
     'blocks': ['천천히', '빨리', '말해 주세요', '말해요'], 'targets': ['천천히', '말해 주세요'],
     'extra': ('다시 말해 주세요.', 'Tolong ulangi sekali lagi.', '다시 말해 주세요.')},
    {'id': 'ex15', 'level': 'A1', 'topic': '부정(안)',
     'instruction': 'Tulis dalam bahasa Korea: Saya tidak makan daging babi.',
     'meaning_ko': "'저는 돼지고기를 안 먹어요' 쓰기 (부정문)",
     'reference': '저는 돼지고기를 안 먹어요.', 'accepted': ['돼지고기를 안 먹어요.', '저는 돼지고기를 먹지 않아요.', '돼지고기를 먹지 않아요.', '돼지고기 안 먹어요.'],
     'blocks': ['저는', '돼지고기를', '안', '먹어요', '없어요'], 'targets': ['저는', '돼지고기를', '안', '먹어요'],
     'extra': ('저는 술을 안 마셔요.', 'Saya tidak minum alkohol.', '저는 술을 안 마셔요.')},
    {'id': 'ex16', 'level': 'A2', 'topic': '희망·미래',
     'instruction': 'Tulis dalam bahasa Korea: Saya ingin pergi ke Korea.',
     'meaning_ko': "'저는 한국에 가고 싶어요' 쓰기 (-고 싶다)",
     'reference': '저는 한국에 가고 싶어요.', 'accepted': ['한국에 가고 싶어요.'],
     'blocks': ['저는', '한국에', '한국을', '가고 싶어요', '가요'], 'targets': ['저는', '한국에', '가고 싶어요'],
     'extra': ('저는 비빔밥을 먹고 싶어요.', 'Saya ingin makan bibimbap.', '저는 비빔밥을 먹고 싶어요.')},
    {'id': 'ex17', 'level': 'A2', 'topic': '희망·미래',
     'instruction': 'Tulis dalam bahasa Korea: Besok saya akan pergi ke pasar.',
     'meaning_ko': "'저는 내일 시장에 갈 거예요' 쓰기 (미래 -ㄹ 거예요)",
     'reference': '저는 내일 시장에 갈 거예요.', 'accepted': ['내일 시장에 갈 거예요.', '내일 저는 시장에 갈 거예요.', '저는 내일 시장에 가요.', '내일 시장에 가요.'],
     'blocks': ['저는', '내일', '시장에', '갈 거예요', '갔어요'], 'targets': ['저는', '내일', '시장에', '갈 거예요'],
     'extra': ('저는 내일 친구를 만날 거예요.', 'Besok saya akan bertemu teman.', '저는 내일 친구를 만날 거예요.')},
    {'id': 'ex18', 'level': 'A1', 'topic': '과거형',
     'instruction': 'Tulis dalam bahasa Korea: Kemarin saya bertemu teman.',
     'meaning_ko': "'저는 어제 친구를 만났어요' 쓰기 (과거형)",
     'reference': '저는 어제 친구를 만났어요.', 'accepted': ['어제 친구를 만났어요.', '어제 저는 친구를 만났어요.', '저는 어제 친구 만났어요.'],
     'blocks': ['저는', '어제', '친구를', '만났어요', '만나요'], 'targets': ['저는', '어제', '친구를', '만났어요'],
     'extra': ('저는 오늘 친구를 만나요.', 'Hari ini saya bertemu teman.', '저는 오늘 친구를 만나요.')},
    {'id': 'ex19', 'level': 'A2', 'topic': '시간·숫자',
     'instruction': 'Tulis dalam bahasa Korea: Sekarang jam tiga.',
     'meaning_ko': "'지금 세 시예요' 쓰기 (시각은 고유어 수사: 세 시 O / 삼 시 X)",
     'reference': '지금 세 시예요.', 'accepted': ['지금 3시예요.', '세 시예요.', '지금 세시예요.', '3시예요.'],
     'blocks': ['지금', '세 시예요', '삼 시예요', '세 시에'], 'targets': ['지금', '세 시예요'],
     'extra': ('지금 열 시예요.', 'Sekarang jam sepuluh.', '지금 열 시예요.')},
    {'id': 'ex20', 'level': 'A2', 'topic': '연결(-고)',
     'instruction': 'Tulis dalam bahasa Korea: Saya makan nasi dan minum air.',
     'meaning_ko': "'저는 밥을 먹고 물을 마셔요' 쓰기 (-고로 두 동작 잇기)",
     'reference': '저는 밥을 먹고 물을 마셔요.', 'accepted': ['밥을 먹고 물을 마셔요.', '저는 밥 먹고 물 마셔요.'],
     'blocks': ['저는', '밥을', '먹고', '먹어요', '물을', '마셔요'], 'targets': ['저는', '밥을', '먹고', '물을', '마셔요'],
     'extra': ('저는 샤워하고 자요.', 'Saya mandi lalu tidur.', '저는 샤워하고 자요.')},
]

# 데이터 무결성 검사: 정답 블록이 블록 목록 안에 다 들어 있는지 (앱 시작 시 자동 확인)
for _e in EXERCISES:
    assert all(t in _e['blocks'] for t in _e['targets']), f"{_e['id']}: targets 중 blocks에 없는 낱말"
    assert _e['topic'] in TOPICS, f"{_e['id']}: TOPICS에 없는 주제"
assert len({e['id'] for e in EXERCISES}) == len(EXERCISES), 'id 중복'
