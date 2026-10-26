"""Add the review to copied B pages using the existing desktop shell."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def inject(out):
    out=Path(out);template=(out/'overview.html').read_text()
    prefix=template[:template.index('<main id="weekly-main">')]
    prefix=prefix.replace('class="active"','').replace('Local squad preserved<br>Loading update status…','Sæsonens modelopfølgning')
    page=prefix+'<main id="weekly-main"><div id="weekly-review-root" class="weekly-review"><p role="status">Henter sæsonens modelrapport …</p></div></main></div></div><script defer src="../weekly-review.js"></script></body></html>'
    (out/'weekly-review.html').write_text(page.replace('<title>FPL Analytics · Din ugentlige plan</title>','<title>Ugens modelrapport · FPL Analytics</title>'))
    for path in out.glob('*.html'):
        s=path.read_text();anchor='<span>Model Explorer</span></a>'
        if anchor in s:s=s.replace(anchor,anchor+'<a href="weekly-review.html"><span>Ugens modelrapport</span></a>')
        elif 'weekly-review.html'not in s:s=s.replace('</body>','<p><a href="weekly-review.html">Ugens modelrapport →</a></p></body>')
        if 'season-team-comparison.js'not in s:s=s.replace('</head>','<script defer src="../season-team-comparison.js"></script></head>')
        if 'weekly-review.js'not in s:s=s.replace('</head>','<script defer src="../weekly-review.js"></script></head>')
        s=s.replace('</head>','<link rel="stylesheet" href="../weekly-review.css"></head>')
        if path.name=='weekly-review.html':s=s.replace('<a href="weekly-review.html">','<a class="active" href="weekly-review.html">')
        path.write_text(s)
