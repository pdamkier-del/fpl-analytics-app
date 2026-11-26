"""Apply presentation-only navigation to the normal Pages entry points."""
from pathlib import Path
import sys
import re
from importlib import import_module

overlay = import_module('preview-overlay')
root = Path(sys.argv[1])
output = Path(sys.argv[2])
output.mkdir(parents=True, exist_ok=True)
routes = (('my-team-classic.html', 'Mit hold'), *overlay.TOP_LINKS[1:])
assets = {}
for name in ('compact-navigation.css', 'compact-navigation.js'):
    assets[name] = overlay.write_asset(output, name, (overlay.ASSETS / name).read_text())

for page, _ in routes[:-1]:
    html = (root / page).read_text()
    if page == 'my-team-classic.html':
        html = re.sub(r'(<main\b[^>]*>)', r'\1<p><a class="button" href="mm-preview/app/overview.html#forecast-refresh-status">Opdater data og prognoser</a></p>', html, count=1)
    (output / page).write_text(overlay.compact_navigation(
        html, page, assets['compact-navigation.css'], assets['compact-navigation.js'], routes,
    ))

advanced = ''.join(
    f'<li><a href="mm-preview/app/{path}">{label}</a></li>'
    for path, label in overlay.ADVANCED_LINKS
)
html = ('<!doctype html><html lang="da"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Avanceret · FPL Analytics</title><link rel="stylesheet" href="classic-common.css">'
        '</head><body><main class="panel fpl-advanced-page"><h1>Avanceret</h1>'
        f'<ul>{advanced}</ul></main></body></html>')
(output / 'advanced.html').write_text(overlay.compact_navigation(
    html, 'advanced.html', assets['compact-navigation.css'], assets['compact-navigation.js'], routes,
))
