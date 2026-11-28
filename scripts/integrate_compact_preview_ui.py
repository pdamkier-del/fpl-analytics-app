"""Retain the live compact B app when rebuilding its verified data assets."""
from subprocess import check_output


LIVE_UI = '60dc3ff91c2ce3ca402d5bf4b27fe5438d7d7c33'
FILES = (
    '../stable-existing-app-adapter.js', 'advanced.html', 'catalog-data.js',
    'classic-catalog.js', 'classic-manager.js', 'clubs-classic.html',
    'compact-navigation.css', 'compact-navigation.js', 'compact-team.js',
    'fixtures-classic.html', 'forecast-refresh.js', 'forecast-window.js',
    'historical-forecast.js', 'manager-import.js', 'manager-state.html',
    'manager-store-v1.js', 'model-contract-v1.js', 'my-team-classic.html',
    'overview.html', 'player.html', 'players-classic.html', 'preview-install.js',
    'transfer-auto-manager.js', 'transfers-classic.html',
)


def inject(out, repository):
    for name in FILES:
        path = out / name
        source = path.resolve().relative_to(out.parent.resolve()).as_posix()
        asset = check_output(['git', 'show', f'{LIVE_UI}:app/mm-preview/{source}'], cwd=repository)
        if name == 'classic-manager.js':
            asset = asset.replace(b'async function compute(){', b'async function compute({replaceExisting=false}={}){')
            asset = asset.replace(b'if(plan)return false;return true;', b'if(plan&&!replaceExisting)return false;return true;')
        if name == 'compact-team.js':
            js = asset.decode()
            js = js.replace("'<a href=\"manager-state.html\">Importér eller redigér hold</a></header>'",
                            "'<div><a href=\"#team\">Opstilling og bænk</a> · <a href=\"manager-state.html\">Importér eller redigér hold</a></div></header>'")
            js = js.replace("closest('th').querySelector('a')", "closest('.fpl-pitch-player').querySelector('a')")
            asset = js.encode()
        if name == 'compact-navigation.css':
            css = asset.decode().replace(
                'body.fpl-team-dashboard #weekly-main { display: none !important; }',
                'body.fpl-team-dashboard #weekly-main > '
                ':not(#weekly-review-summary, #planner-context, #latest-snapshot-info) { display: none !important; }',
            )
            asset = css.encode()
        if name == 'transfer-auto-manager.js':
            js = asset.decode()
            js = '\n'.join(line for line in js.split('\n') if 'const DEFAULT_ENTRY_ID =' not in line)
            js = js.replace("localStorage.getItem('fpl-transfer-entry-id') || DEFAULT_ENTRY_ID);", "localStorage.getItem('fpl-transfer-entry-id'));\n    if (!entryId && !force) return;")
            js = js.replace('Beregner transferforslag med TS v3', 'Beregner transferforslag med TS v3 og TS v4.1')
            asset = js.encode()
        if name == 'transfers-classic.html':
            asset = asset.replace(b'body.fpl-compact-ui #transfer-result-data { display:none!important; }\n', b'')
        if name == 'overview.html':
            asset = asset.replace(b'integration/stable-live-app-20261122', b'main')
        path.write_bytes(asset)
