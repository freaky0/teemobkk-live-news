# TeemoBKK Live News

공개 주소: https://freaky0.github.io/teemobkk-live-news/ (자세한 내용은 DEPLOY.md)

무료 RSS와 공개 API를 모아 60초마다 갱신하고, 수집한 기사를 SQLite에 누적해 검색할 수 있는 로컬 뉴스 대시보드입니다.

## 포함된 수집원

### 글로벌 매크로·크립토
- CoinDesk, Decrypt, Bitcoin Magazine RSS
- FinancialJuice 실시간 매크로 헤드라인 RSS (공개 피드, 제목 접두어 제거·유동성/금리 용어 분류 보정)
- CoinNess 속보 공개 API와 주식·지정학 속보 API (인증 없음, 각 30건, 중요 속보 가산점)
- SBHNews 한국 지정학·속보 (사이트맵 10분 캐시 + JSON-LD 제목·시각, 신규 페이지만 조회)
- 영란은행 뉴스 RSS, 연준 연설 RSS
- Google News 검색 RSS: 비트코인, ETF, 유동성, 금리·달러, 미국 정책·트럼프, 지정학, 파생상품, 온체인·기관, 스테이블코인, X 발언
- 미국 증권거래위원회와 연방준비제도 RSS

### 태국 소식
- 영문 매체: Bangkok Post(종합·경제), Khaosod English, Thai Enquirer, Prachatai English
- 태국어 매체: Thairath, Matichon
- Google News 검색 RSS: Thailand, Bangkok, 태국(한국어, 태국 관련 항목만 통과)
- 저품질·비태국 매체 제외 목록 적용

## 탭 구성
- `경제 소식`: BTC·거시 뉴스
- `경제 지표`: 경제지표 일정·연설·실적·대통령 일정 (탭을 눌렀을 때만 표시, 다시 누르면 접힌다)
- `태국 소식`: 교민 생활 중심 일반 뉴스 (비자·이민, 사고·재난 우선 표시)

태국 탭 분류는 `비자·이민`, `사고·재난`, `태국 생활`, `태국 경제`, `태국 정치·사회`, `태국 관광`, `태국 보건`이다.

## 화면 표시

**확인 수준 라벨** — 카드 앞머리에 신뢰 수준을 표시한다. 출처 칩이 이미 발행처를 말하므로, 신뢰도를 실제로 바꾸는 두 단계만 붙인다.

```
[공식]  공식 기관이 직접 발표한 문서 (하루 0.5% — 백악관·연준·SEC·영란은행)
[SNS]   소셜 게시물·텔레그램 채널 (하루 10.6%) — 언론 보도가 아니며 원문 확인이 필요함
```

`breaking`(37%)과 `aggregated`(41%)에는 라벨을 붙이지 않는다. 그러면 카드 다섯 장 중 네 장에 배지가 달려 아무 뜻이 없어진다. 외부 사이트가 쓰는 `(카더라)` 같은 표시는 여기서 만들지 않는다 — 그쪽 편집자가 붙이는 주석이고, 수집되는 원문에는 그런 표시가 0건이다.

**지금 뜨는 키워드** — 피드 위에 최근 창에서 자주 나온 낱말과 건수를 띄우고, 누르면 그 말로 검색한다. 브라우저에서 계산하므로 서버·API 변경이 없다.

```
계산     페이지가 이미 받은 제목에서 (로컬은 창을 300건까지 따로 요청)
구절     제목에 붙어 있는 두 낱말("clarity act", "asian games")은 한 덩어리로 표시
제외     발행처 이름·일반어·월 이름, 그리고 이 대시보드의 주제어(bitcoin·btc 등)
정렬     트렌드는 별도 줄이며 뉴스 목록의 최신순 정렬은 건드리지 않는다
```

## 저장과 조회
- 기사는 `news.db`(SQLite)에 누적 저장한다. 링크가 같으면 자동으로 중복이 걸러진다.
- 화면 기본 조회 기간은 24시간이며 1·6·12·24시간으로 바꿀 수 있다.
- 검색은 제목과 요약을 대상으로 하고, 분류·출처·공식 여부·중요도·기간을 함께 지정할 수 있다.
- 조회는 한 번에 300건까지 보내고 남은 건은 `더 보기`로 이어서 불러온다.
- 보관 기간은 90일이며 그보다 오래된 기사는 주기적으로 제거한다.
- API가 요청마다 DB를 조회하므로 기사가 늘어도 전체를 메모리에 들고 있지 않는다.
- 서버를 재시작해도 보관된 기사에서 즉시 복원한다.

## 성능
- 수집은 스레드 풀로 병렬 실행(RSS 10, Google News 4, SBHNews 페이지 6)
- 전체 1회 수집 주기 약 8초 (기본 갱신 간격 60초)

## 실행

```bash
cd "C:/AI/Work_Folders/News_Macros/live_news_dashboard"
python live_news_dashboard.py
```

브라우저에서 다음 주소를 엽니다.

```text
http://127.0.0.1:8765
```

갱신 간격을 바꾸려면:

```bash
python live_news_dashboard.py --interval 30 --port 8765
```

## 윈도우 배치 실행

```bat
@echo off
cd /d "C:\AI\Work_Folders\News_Macros\live_news_dashboard"
python live_news_dashboard.py --interval 30
```

### 백그라운드(분리) 실행 — 권장

`start_dashboard_bg.bat` 은 서버를 **분리된 프로세스**로 띄우고, 포트가 실제로 응답하면 바로 돌아온다. 창이 남지 않고 실행한 쪽(탐색기·cmd·Hermes 세션)이 끝나도 서버는 계속 돈다.

```bat
start_dashboard_bg.bat          :: 기동. 포트를 잡고 있는 이전 프로세스는 정리한다
start_dashboard_bg.bat open     :: 기동 후 브라우저까지 열기
```

```
동작     이전 리스너 종료 → 분리 기동 → 포트 LISTENING 확인 → 그 뒤에 성공 반환
실패 시   포트가 안 열리면 로그 마지막 12줄을 출력하고 exit 1
출력     local.log · local.log.err (로거가 stderr로 쓰므로 내용은 .err에 있다)
         직전 실행분은 *.prev로 보존 — 숨은 창은 다른 흔적을 남기지 않는다
```

분리 기동 자체는 `run_dashboard_bg.py` 가 맡는다. `Start-Process -WindowStyle Hidden` 으로 띄우면 자식이 호출자의 콘솔을 물려받아, 실행한 쪽이 **서버가 끝날 때까지** 기다린다(실측: 서버는 정상인데 에이전트 도구 호출이 5분 대기). `DETACHED_PROCESS` 로 콘솔을 아예 주지 않으면 즉시 반환한다(실측 1.7초).

## 설계 원칙

- API 키 없이 실행
- 수집 실패한 개별 출처가 있어도 다른 출처는 계속 수집
- 기본 조회는 최근 24시간이며, 발행 시각이 확인된 기사만 저장한다
- 펨코톤 자동 변환 기능은 현재 비활성화
- 기사 카드에는 중요도와 비트코인 연결고리만 표시
- 유동성·금리, 미국 정책·트럼프, 지정학, ETF·수급, 파생상품·청산, 온체인·기관, 스테이블코인, X 발언, 주식·원자재, 채굴 분류 제공
- 제목 유사도 기준 중복 제거
- BTC·ETH·핵심·유동성·미국 정책·트럼프·지정학·ETF·파생상품·온체인·스테이블코인·X 발언·주식·원자재·채굴 필터 제공
- X 발언은 현재 Google News 검색을 통한 간접 수집이며, 공식 X API 직접 연동은 별도 작업
- 저장: `news.db` (SQLite, WAL)
- 조회 API: `http://127.0.0.1:8765/api/news`
  - 파라미터: `region`, `category`, `source`, `source_type`, `priority`, `q`, `hours`, `limit`, `offset`
  - 예: `/api/news?region=태국&hours=24&q=비자&limit=100`
- 상태 API: `http://127.0.0.1:8765/api/status`
- 보관 현황 API: `http://127.0.0.1:8765/api/stats`

## 공개(다른 사람도 보기)

관리용 인스턴스와 공개용 인스턴스를 분리해서 띄운다. 공개용은 읽기 전용이고 내부 정보를 내보내지 않는다.

```bash
# 관리용 (전체 기능, 이 PC 전용)
python live_news_dashboard.py --interval 60 --port 8765

# 공개용 (읽기 전용)
python live_news_dashboard.py --public --interval 300 --port 8766
```

### 공개용에서 빠지는 것
- 수집 상태 패널, 보관 현황, 갱신 간격 설정
- `비트코인 연결고리`·`생활 연결` 해석 문구
- 카운터(총·표시·보관)
- API 응답에서 `sources`, `archive`, `archived_total`, `fresh_article_count`, `inserted_article_count` 제거
- `POST /api/settings` 403, `GET /api/stats` 404

공개용에 남는 것은 출처·제목·요약·시각·분류·원문 링크, 그리고 검색·기간·분류 필터와 더 보기다.

### 같은 네트워크(LAN)에서 보기
```bash
python live_news_dashboard.py --public --interval 300 --port 8766 --host 0.0.0.0
```
같은 와이파이에 있는 사람은 `http://192.168.1.13:8766` 로 접속한다. 윈도우 방화벽에서 최초 1회 허용해야 한다.

### 인터넷에 공개하기 (공유기 설정 변경 없음)
Cloudflare Tunnel을 쓰면 포트를 열지 않고도 https 주소로 공개할 수 있다.

```bash
winget install --id Cloudflare.cloudflared
cloudflared tunnel --url http://127.0.0.1:8766
```
실행하면 `https://<임시주소>.trycloudflare.com` 형태의 주소가 나온다. 그 주소를 공유하면 된다.

- 임시 주소는 재시작마다 바뀐다. 고정 주소가 필요하면 Cloudflare 계정과 도메인으로 이름 있는 터널을 만든다.
- 반드시 공개용 포트(8766)로 연결한다. 관리용 8765를 연결하면 설정 변경까지 열린다.
- 임시 터널 주소를 아는 사람은 누구나 볼 수 있다. 민감한 내용이 아니라 뉴스 목록이라 이 정도가 적절하다.
- 검색 노출을 막으려면 `index.html`의 `<head>`에 `<meta name="robots" content="noindex">`를 넣는다.

뉴스는 자동 매매 신호가 아닙니다. 중요한 사건은 원문과 공식 발표를 교차 확인해야 합니다.
