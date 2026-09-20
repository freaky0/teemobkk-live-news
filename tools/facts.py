"""Where each fact lives: every V.filter use, the rule that flattens the .on background, and the
pill row markup the keyword row should mirror."""
import io
import re

t = io.open("C:/AI/Work_Folders/News_Macros/live_news_dashboard/page_build.py", encoding="utf-8").read()

print("════ V.filter 사용처 ════")
for m in re.finditer(r"[^\n]*V\.filter[^\n]*", t):
    print("  L%-5d %s" % (t[:m.start()].count("\n") + 1, m.group(0).strip()[:120]))

print()
print("════ .tbtn / .pill 관련 CSS 규칙 전부 ════")
for m in re.finditer(r"[^\n]*\.(?:tbtn|pill|trend)[^\n]*\{[^}]*\}", t):
    print("  %s" % m.group(0).strip()[:170])

print()
print("════ 분류 알약 줄 마크업 ════")
i = t.find("filters-global")
print("  %s" % t[max(0, i - 260):i + 200].replace("\n", " ⏎ ")[:420])
