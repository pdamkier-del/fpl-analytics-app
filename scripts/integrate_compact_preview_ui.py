"""Retain the live compact B app when rebuilding its verified data assets."""
from subprocess import check_output


LIVE_UI = '60dc3ff91c2ce3ca402d5bf4b27fe5438d7d7c33'
FILES = (
    'advanced.html', 'catalog-data.js', 'classic-catalog.js', 'clubs-classic.html',
    'compact-navigation.css', 'compact-navigation.js', 'compact-team.js',
    'fixtures-classic.html', 'manager-import.js', 'manager-state.html',
    'my-team-classic.html', 'overview.html', 'player.html', 'players-classic.html',
    'transfer-auto-manager.js', 'transfers-classic.html',
)


def inject(out, repository):
    for name in FILES:
        asset = check_output(['git', 'show', f'{LIVE_UI}:app/mm-preview/app/{name}'], cwd=repository)
        path = out / name
        if name == 'compact-team.js':
            js = asset.decode()
            js = js.replace("'<a href=\"manager-state.html\">Importér eller redigér hold</a></header>'",
                            "'<div><a href=\"#team\">Opstilling og bænk</a> · <a href=\"manager-state.html\">Importér eller redigér hold</a></div></header>'")
            js = js.replace("closest('th').querySelector('a')", "closest('.fpl-pitch-player').querySelector('a')")
            asset = js.encode()
        if name == 'compact-navigation.css':
            css = asset.decode().replace(
                'body.fpl-team-dashboard #weekly-main { display: none !important; }',
                'body.fpl-team-dashboard #weekly-main > :not(#dashboard-team-news):not(#weekly-review-summary) { display: none !important; }',
            )
            asset = css.encode()
        if name == 'transfer-auto-manager.js':
            js = asset.decode()
            js = '\n'.join(line for line in js.split('\n') if 'const DEFAULT_ENTRY_ID =' not in line)
            js = js.replace("localStorage.getItem('fpl-transfer-entry-id') || DEFAULT_ENTRY_ID);", "localStorage.getItem('fpl-transfer-entry-id'));\n    if (!entryId && !force) return;")
            js = js.replace('Beregner transferforslag med TS v3', 'Beregner transferforslag med TS v3 og TS v4.1')
            asset = js.encode()
        path.write_bytes(asset)
