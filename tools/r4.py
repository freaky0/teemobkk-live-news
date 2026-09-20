"""수정 대상: 내가 넣은 패널 블록, 수집 상태 행, 알약의 소스 목록."""
import io
import re

t = io.open("C:/AI/Work_Folders/News_Macros/live_news_dashboard/page_build.py",
            encoding="utf-8").read()

print("════ 1) 내가 넣은 '소스 공개' 상자 마크업 ════")
i = t.find('id="srcpanel"')
print(repr(t[max(0, i - 200):i + 120]))
print()
print("════ 2) 수집 상태 상자 + renderSources ════")
i = t.find('id="sources"')
print(repr(t[max(0, i - 120):i + 120]))
i = t.find("function renderSources(){")
print(repr(t[i:i + 430]))
print()
print("════ 3) 알약의 소스 목록 ════")
i = t.find("const srcs=")
print(repr(t[max(0, i - 160):i + 200]))
print()
print("════ 4) 내 패널 JS 블록의 시작과 끝 ════")
i = t.find("// --- which sources the deployed pages show")
j = t.find("// <<< operator-only", i)
print("  시작 %d · 끝 %d · 길이 %d자" % (i, j, j - i))
print(repr(t[i:i + 200]))
print("  ...")
print(repr(t[max(0, j - 200):j + 60]))
