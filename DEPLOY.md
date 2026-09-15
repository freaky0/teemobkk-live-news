# TeemoBKK Live News - 클라우드 배포

내 PC를 켜두지 않아도 공개 페이지가 24시간 돌아가게 만드는 방법이다.

## 지금 배포된 상태

- 공개 주소: https://freaky0.github.io/teemobkk-live-news/
- 저장소: https://github.com/freaky0/teemobkk-live-news
- 수집: `collect` 워크플로가 15분마다 자동 실행되고 결과를 커밋한다.
- 확인: 저장소의 Actions 탭에서 실행 기록을 볼 수 있다.

수동으로 다시 돌리려면 저장소의 Actions - collect - Run workflow를 누른다.

## 신 구조 (수정본)

GitHub의 예약 실행은 "최선 노력"이라 새 저장소에서 45분 넘게 한 번도 발화하지 않았다. 그래서 갱신을 깨우는 역할만 Cloudflare Worker로 옮겼다.

```
Cloudflare Worker (크론 5분, CPU 1ms)
        |  GitHub API로 workflow_dispatch
        v
GitHub Actions (수집, 실제 CPU 사용)
        |  docs/*.json 커밋
        v
GitHub Pages (공개 페이지가 그 JSON을 읽음)
```

- Worker는 수집하지 않는다. 무료 플랜은 호출당 CPU 10ms, 서브리퀘스트 50개라 피드 40개를 파싱할 수 없다.
- 수집 로직은 계속 파이썬 한 벌이고, 로컬 대시보드와 같은 코드를 쓴다.
- 저장소에도 크론이 남아 있다(`*/30`). Worker가 멈춰도 최소 30분마다 갱신된다.

## Worker 정보

| 항목 | 값 |
| --- | --- |
| 이름 | `teemobkk-live-news-trigger` |
| 주소 | https://teemobkk-live-news-trigger.teemobkk-live-news.workers.dev |
| 크론 | `*/5 * * * *` |
| 시크릿 | `GH_TOKEN` (해당 저장소만, Actions 쓰기 권한) |
| 코드 | `worker/src/index.js`, `worker/wrangler.toml` |

토큰을 바꾸려면: `cd worker && npx wrangler secret put GH_TOKEN`
배포하려면: `cd worker && npx wrangler deploy`
로그를 보려면: `cd worker && npx wrangler tail`

## 구조

- 수집: GitHub Actions가 15분마다 `deploy/collect_public.py`를 실행한다.
- 저장: 결과 JSON을 저장소에 커밋한다. 별도 서버도, 데이터베이스도 필요 없다.
- 화면: GitHub Pages가 `docs/` 폴더를 그대로 서비스한다.

## 나오는 파일

| 파일 | 내용 |
| --- | --- |
| `docs/index.html` | 공개 페이지. 서버 없이 JSON만 읽어 화면을 그린다. |
| `docs/index.json` | 기준 시각, 보관 기간, 건수 요약 |
| `docs/global.json` | 글로벌 매크로·크립토 (보관 24시간) |
| `docs/thai.json` | 태국 소식 (보관 24시간) |

지역별로 파일을 나눈 이유는 방문자가 여는 탭의 자료만 받게 하기 위해서다.

## 켜는 순서

1. 저장소를 공개(public)로 만든다. 공개 저장소는 Actions 실행 시간이 무제한이라 15분 주기를 무료로 돌릴 수 있다.
2. 저장소에 코드를 올린다.
3. Settings - Pages 에서 Source를 `Deploy from a branch`, Branch를 `main`, 폴더를 `/docs` 로 지정한다.
4. Actions 탭에서 `collect` 워크플로를 한 번 수동 실행한다(`Run workflow`). 첫 자료가 커밋된다.
5. 몇 분 뒤 `https://<계정>.github.io/<저장소>/` 로 접속해 확인한다.

이후에는 15분마다 자동으로 갱신된다.

## 알아둘 점

- 공개 저장소이므로 수집 코드와 소스 목록이 누구나 볼 수 있다. 비밀번호나 API 키는 코드에 없다.
- 검색 노출을 막으려고 페이지에 `noindex`를 넣어 두었다. 주소를 아는 사람만 본다.
- 예약 실행은 저장소에 60일간 변화가 없으면 꺼진다. 이 봇이 15분마다 자료를 커밋하므로 계속 살아 있다.
- FinancialJuice 피드는 같은 IP에서 자주 부르면 429로 막힌다. 한 주기에 한 번만 부르므로 대체로 정상이다.
- 보관 기간은 `deploy/collect_public.py`의 `KEEP_HOURS`, 지역당 상한은 `MAX_PER_REGION`에서 바꾼다.

## 로컬에서 미리 보기

```bash
python deploy/collect_public.py
python -m http.server 8899 --directory docs
```
`http://127.0.0.1:8899` 를 열면 배포본과 같은 화면이 나온다.

## 다른 호스팅을 쓸 경우

`docs/` 폴더는 정적 파일이라 Cloudflare Pages나 Netlify에도 그대로 올릴 수 있다. 다만 그쪽에는 주기 실행 기능이 없으므로 수집은 계속 GitHub Actions에 맡기고 화면만 옮기는 형태가 된다.
