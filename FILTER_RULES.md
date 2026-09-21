# 거르는 규칙 (필터)

운영자가 손으로 숨긴 기사에서 **되풀이되는 문구**를 뽑아, 앞으로 들어올 같은 모양의 기사를 자동으로
빼는 기능. 배포 페이지는 그대로 두고 운영자 화면에서만 만진다.

## 쓰는 법

`https://teemobkk.io/admin` 오른쪽 사이드바 → **거르는 규칙**

```
1. [숨긴 기사에서 규칙 뽑기]  숨긴 기사 29건에서 후보를 뽑아 올린다. 후보는 꺼진 채로 온다.
2. 각 줄을 보고 스위치를 켠다. 켜면 지금 창에 있는 기사까지 함께 걸린다.
3. [잡은 기사]에서 오탐이 보이면 [살리기] — 그 기사만 규칙을 통과한다.
4. ✕ 로 규칙을 지우면 그 규칙이 잡았던 기사가 전부 돌아온다.
```

직접 넣으려면 아래 입력칸에 문구를 넣고 [추가]. 제목이나 요약에 그 문구가 있는 기사가 등록 뒤
화면에서 빠진다.

## 동작

```
등록    기사는 평소대로 등록된다. 규칙은 등록 직후 같은 트랜잭션에서 걸린다.
표시    걸린 기사는 hidden_links와 똑같이 모든 읽기 경로에서 빠진다 -
        피드·건수·알약·랜딩·태국 섹션·검색. 화면마다 어긋날 수 없다.
검토    걸린 기사는 filter_hits에 남는다. 무엇이 걸렸는지 목록으로 보고 되돌릴 수 있다.
되돌림  규칙을 끄거나 지우면 그 규칙이 잡은 기사가 전부 돌아온다. 조용한 삭제가 없다.
살리기  규칙은 그대로 두고 특정 기사만 통과시킬 수 있다 (filter_keeps).
AI 채점 P6 채점은 걸린 기사를 건너뛴다 - 걸릴 기사에 토큰을 쓰지 않는다.
```

## 규칙을 뽑는 기준 (실측으로 정한 선)

```
뽑는다    되풀이되는 제목 앞머리. 실측: "bloomberg news now" 는 숨김 5건을 전부 덮었고
          남은 기사에 걸린 9건은 같은 다이제스트였다(오탐 0).
          숨김에만 잘 나오는 낱말도 뽑되, 숨김 2건 이상 + 그 낱말이 나온 기사의 절반 이상이
          숨김이어야 한다.
안 뽑는다 주제가 다른 기사(실측 72%). 스포츠·요리·문화는 낱말 목록이 끝이 없고, 반대로
          '시장 낱말이 있어야 통과'를 걸면 실측 80%가 잘못 걸린다(미 소매판매 같은 핵심까지).
          그쪽은 기사별 관련도 채점의 몫이다.
```

라틴 낱말은 **낱말 첫 자리**에만 걸린다 — `casino`가 `fascinating` 안에서 걸리면 규칙을 켤 수 없다.
한국어는 조사가 붙으므로 부분 문자열로 본다(`에어드롭`이 `에어드롭이`를 잡는다).

## 검사

```bash
python tests/test_filter_rules.py     # 20건: 필터·되돌림·살리기·매칭·학습
node   tests/t40.js http://127.0.0.1:8765/   # 19건: 패널 배선
python tools/probe_filter_rules.py    # 운영 실측: 익명 차단·등록 뒤 거르기·되돌림·후보 뽑기
python tools/analyze_hidden.py news.db           # 숨김이 어디에 몰렸는지
python tools/analyze_hidden_phrases.py news.db   # 되풀이되는 구절과 타격량
python tools/analyze_relevance.py news.db        # 관련도 게이트의 오탐률
```

## 코어에 붙은 곳 (되돌릴 때 참고)

```
표      filter_rules · filter_hits · filter_keeps (settings 옆)
함수    _rule_regex · filter_rules · _record_filter_hits · rescan_filters · add/set/delete_filter_rule
        keep_caught · caught_links · learn_filter_rules
등록    insert_articles 안, INSERT 뒤 _record_filter_hits 한 줄
읽기    query_articles 의 where 에 한 줄 (hidden_links 옆)
어드민  /api/status 에 filter_rules · GET /api/filters · POST /api/filter
화면    page_build.py 사이드바 상자 + 운영자 구간 JS (RULES_UI 표시: 거르는 규칙)
학습    filter_learn.py (문자열 계산만 - 토큰 0)
```

규칙을 통째로 되돌리려면 `DELETE FROM filter_rules` 한 줄이면 된다. 걸린 기사는 즉시 돌아오고,
기사 표는 손대지 않으므로 잃는 것이 없다.
