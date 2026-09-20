"""Replace fixed sleeps in the page tests with condition waits.

A fixed wait assumes the host answers within that time. A deployed page under a proxy, or a host
that was just restarted, answers slower - and the test then reports a page failure that is really
a timing failure. Waiting for the condition, with a cap, removes that whole class of false result.
"""
import io

HELPER = """const waitFor = async (fn, ms = 25000, step = 300) => {
  const until = Date.now() + ms;
  while (Date.now() < until) { if (fn()) return true; await sleep(step); }
  return false;
};
"""

EDITS = {
    "t30.js": [
        ("await sleep(9000);\n",
         "// the deployed page answers through a proxy: wait for the render, not for a clock\n"
         "await waitFor(() => d.querySelectorAll('#filters-global button[data-cat]').length > 0\n"
         "  && d.querySelectorAll('#feed .card').length > 0);\n"),
        ("  const pill = d.querySelector('#filters-global button[data-cat=\"\uc720\ub3d9\uc131\u00b7\uae08\ub9ac]');\n",
         None),  # placeholder, replaced below if present
        ("pill.click();\n    await sleep(6000);\n",
         "pill.click();\n    await waitFor(() => { const c = cards(); return c.length > 0 && c.length !== base; });\n"),
    ],
    "t22.js": [
        ("await sleep(9000);\n",
         "await waitFor(() => cards() > 0);\n"),
        ("more().click();\n  await sleep(7000);\n",
         "const before = cards();\n  more().click();\n  await waitFor(() => cards() > before);\n"),
    ],
}

for name, edits in EDITS.items():
    text = io.open(name, encoding="utf-8").read()
    for old, new in edits:
        if new is None:
            continue
        if old not in text:
            print("  %-8s MISS: %s" % (name, old.strip()[:44]))
            continue
        text = text.replace(old, new, 1)
    if "const waitFor" not in text:
        anchor = "const sleep = (ms) => new Promise((r) => setTimeout(r, ms));\n"
        if anchor not in text:
            raise SystemExit("no sleep helper in " + name)
        text = text.replace(anchor, anchor + HELPER, 1)
    io.open(name, "w", encoding="utf-8", newline="").write(text)
    left = text.count("await sleep(")
    print("  %-8s updated · 남은 고정 대기 %d" % (name, left))
