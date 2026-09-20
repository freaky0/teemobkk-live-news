"""The two regions the category multi-select has to be threaded through."""
import io
import re

t = io.open("C:/AI/Work_Folders/News_Macros/live_news_dashboard/page_build.py", encoding="utf-8").read()

print("════ renderPills ════")
i = t.index("function renderPills(){")
print(re.sub(r"\n", "\n  ", t[i:i + 1100]))

print()
print("════ L755 근처 (V.filter 를 '전체' 로 되돌리는 곳) ════")
lines = t.split("\n")
print(re.sub(r"\n", "\n  ", "\n".join(lines[748:762])))

print()
print("════ 시험 파일의 V.filter 의존 ════")
import os
d = "C:/Users/freak/AppData/Local/Temp/pagetest/"
for f in sorted(os.listdir(d)):
    if f.endswith(".js"):
        s = io.open(d + f, encoding="utf-8", errors="replace").read()
        hits = [x for x in ("V.filter", "\.active", "V.terms") if x in s]
        if hits:
            print("  %-10s %s" % (f, ", ".join(hits)))
