"""Approved public/admin visual language. Thai landing retains its own theme."""

LIGHT_TOKENS = ('color-scheme:light;--bg:#f5f5f4;--surface:#faf9f7;--surface2:#eee4dd;'
                '--panel:#faf9f7;--panel2:#eee4dd;--bg2:#eee4dd;--text:#282626;'
                '--muted:#67605f;--dim:#67605f;--line:#d3ccc6;--line2:#bfb3aa;'
                '--accent:#a34230;--accent-dim:rgba(163,66,48,.10);--on-accent:#faf9f7;'
                '--down:#a52c28;--warn:#805318;--error:#a52c28;--official:#286440;'
                '--radius:0px;--r:0px;--r-card:0px;--r-ctl:0px;'
                '--sans:"Wanted Sans",system-ui,sans-serif;--serif:var(--sans)')
DARK_TOKENS = ('color-scheme:dark;--bg:#142332;--surface:#1b2e40;--surface2:#263e55;'
               '--panel:#1b2e40;--panel2:#263e55;--bg2:#263e55;--text:#edf3f8;'
               '--muted:#b3c5d5;--dim:#b3c5d5;--line:#3a5167;--line2:#526b82;'
               '--accent:#94bfea;--accent-dim:rgba(148,191,234,.12);--on-accent:#142332;'
               '--down:#ffaaa3;--warn:#ebc68c;--error:#ffaaa3;--official:#9ed8b3;'
               '--radius:0px;--r:0px;--r-card:0px;--r-ctl:0px;'
               '--sans:"Wanted Sans",system-ui,sans-serif;--serif:var(--sans)')

DESIGN_CSS = '''
@font-face{font-family:"Wanted Sans";src:url("/assets/fonts/WantedSansVariable.woff2") format("woff2");font-weight:100 900;font-display:swap}
''' + '\n'.join((
    'html:root,html:root body.public,html:root body.local{' + LIGHT_TOKENS + '}',
    'html:root[data-theme="light"],html:root[data-theme="light"] body.public,html:root[data-theme="light"] body.local{' + LIGHT_TOKENS + '}',
    'html:root[data-theme="dark"],html:root[data-theme="dark"] body.public,html:root[data-theme="dark"] body.local{' + DARK_TOKENS + '}',
)) + '''
body{font-family:var(--sans);background:var(--bg);color:var(--text)}
body.public,body.local{font-family:var(--sans)}
body.public .title,body.local .title,body.public h1,body.local h1,
body.public .brand,body.local .brand{font-family:var(--sans)}
.top,.bar{background:var(--bg);backdrop-filter:none}
.brand,.footer-row .fbrand{font-family:var(--sans);letter-spacing:-.04em}
.brand .cursor{display:none}
.button.primary{color:var(--on-accent)}
.button.primary:hover{color:var(--on-accent)}
.table-wrap,.tablewrap,table,.card,.box,.page-posts,.indicator,.chart-open,.cal,.cal-grid,.cal-day{border-radius:0}
th,td,.cal-t,.cal-v{font-variant-numeric:tabular-nums}
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;animation:none!important;transition:none!important}}
'''
