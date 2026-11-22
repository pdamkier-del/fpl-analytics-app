"""Apply integration assets to the generated B app, after the existing B build."""
import argparse
import re
from hashlib import sha256
from pathlib import Path

ASSETS = Path(__file__).resolve().parent
CLIENTS = ('classic-manager.js', 'weekly-app.js', 'manager-state.js', 'manager-online.js')
STORE = 'FplManagerStore'
KEY = "'fpl-manager-state-v1'"


def rewrite_manager(text):
    text = text.replace(f"JSON.parse(localStorage.getItem({KEY})||'null')", f'{STORE}.read()')
    text = text.replace(f'JSON.parse(localStorage.getItem({KEY}))', f'{STORE}.read()')
    text = text.replace(f'localStorage.getItem({KEY})', f'{STORE}.read()')
    text = re.sub(
        r"localStorage\.setItem\('fpl-manager-state-v1',JSON\.stringify\(([^()]+)\)\)",
        rf'{STORE}.save(\1)', text,
    )
    text = text.replace(f'localStorage.setItem({KEY},json)', f'{STORE}.save(raw)')
    text = text.replace('JSON.parse(stored)', 'stored')
    text = text.replace(f"[{KEY},", f"[{STORE}.key,")
    return text


def bind_plan(text):
    text = text.replace(
        "saved.manager_state_sha256===await hash(state)",
        "FplModelContractV1.validatePlanIdentity(forecast,await hash(FplManagerStore.read()),saved).ok",
    )
    text = text.replace(
        'if(!FplLatestSnapshot.enabled&&latest.forecast_sha256!==forecast.forecast_sha256)',
        'if(latest.forecast_sha256!==forecast.forecast_sha256)',
    )
    anchor = "d.plan.manager_state_sha256!==await hash(state)"
    if text.count(anchor) != 1 or 'FplModelContractV1.validatePlanIdentity' not in text:
        raise ValueError('Manager plan binding anchors changed')
    return text.replace(
        anchor,
        "!FplModelContractV1.validatePlanIdentity(forecast,await hash(FplManagerStore.read()),d.plan).ok",
    )


def rewrite_adapter(text):
    anchor = 'if(i.desktop_probabilities&&(publicStats||i.chain_version))'
    if text.count(anchor) != 1:
        raise ValueError('Forecast adapter anchor changed')
    text = text.replace(anchor, '''const official=d.documents['current-players.json'];
  official.live_window = null;
  if (Date.now() < Date.parse(f.origin_deadline) && window.FplTeamNews) {
    try {
      const latest = await FplTeamNews.load(nativeFetch, Date.now(), {allowStale:true});
      official.live_window = {
        gw: latest.next_gw, deadline: latest.deadline, observed_at: latest.observed_at,
        catalogue_matches: FplModelContractV1.validateOfficialCompatibility(f, {
          next_gw: latest.next_gw,
          players: latest.players.map(p=>({id:p.id,team:p.team,position:p.position,price:p.price_tenths/10}))
        }).ok
      };
    } catch {
      // The sealed forecast remains available as historical information.
    }
  }
  if(i.desktop_probabilities&&(publicStats||i.chain_version)&&Date.now()<Date.parse(f.origin_deadline))''')
    export = 'history:historyData,probabilities:probabilityData,publicStats'
    if text.count(export) != 1:
        raise ValueError('Probability adapter export changed')
    return text.replace(export, '''history:historyData,probabilities:async()=>{
   const selected=await data();
   const status=FplForecastWindow.check(selected.forecast,selected.documents['current-players.json']);
   if(!status.usable)throw Error(status.reason);
   return probabilityData();
  },publicStats''')


def write_asset(directory, name, text):
    content = text.encode()
    (directory / name).write_bytes(content)
    return f'{name}?asset={sha256(content).hexdigest()[:16]}'


def apply(app):
    store = write_asset(app, 'manager-store-v1.js', (ASSETS / 'manager-store-v1.js').read_text())
    contract = write_asset(app, 'model-contract-v1.js', (ASSETS / 'contract-v1.js').read_text())
    script_urls = {}
    for name in CLIENTS:
        path = app / name
        original = path.read_text()
        changed = rewrite_manager(original)
        if name in {'weekly-app.js', 'classic-manager.js'}:
            changed = bind_plan(changed)
        if original == changed or f'localStorage.setItem({KEY}' in changed:
            raise ValueError(f'Manager storage anchors changed in {path}')
        script_urls[name] = write_asset(app, name, changed)

    path = app / 'forecast-window.js'
    script_urls[path.name] = write_asset(
        app, path.name, path.read_text() + (ASSETS / 'forecast-gate.js').read_text(),
    )

    worker = (ASSETS / 'preview-sw.js').read_text()
    offline = (ASSETS / 'preview-offline.html').read_text()
    (app / 'preview-offline.html').write_text(offline)
    (app / 'preview-sw.js').write_text(worker.replace('__SHELL_REVISION__', sha256(offline.encode()).hexdigest()[:16]))
    registration = write_asset(app, 'preview-install.js', (ASSETS / 'preview-install.js').read_text())

    adapter = app.parent / 'existing-app-adapter.js'
    adapter_url = '../' + write_asset(app.parent, 'stable-existing-app-adapter.js', rewrite_adapter(adapter.read_text()))
    script_urls['../existing-app-adapter.js'] = adapter_url
    nav = app / 'nav.js'
    if nav.exists():
        script_urls[nav.name] = write_asset(
            app, nav.name, nav.read_text().replace("navigator.serviceWorker.register('./sw.js')", "navigator.serviceWorker.ready"),
        )
    archive = write_asset(app, 'historical-forecast.js', (ASSETS / 'historical-forecast.js').read_text())

    for page in app.glob('*.html'):
        html = rewrite_manager(page.read_text())
        if worker_registration := re.search(r'navigator\.serviceWorker\.register\([\'"]\./sw\.js[\'"]\)', html):
            html = html[:worker_registration.start()] + "navigator.serviceWorker.ready" + html[worker_registration.end():]
        for name, url in script_urls.items():
            html = re.sub(rf'(src=["\']){re.escape(name)}(?:\?[^"\']*)?(?=["\'])', rf'\g<1>{url}', html)
        html = html.replace(
            '<head>',
            f'<head><script src="{store}"></script><script src="{contract}"></script>'
            f'<script defer src="{registration}"></script><script defer src="{archive}"></script>', 1,
        )
        page.write_text(html)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('generated_app', type=Path)
    apply(parser.parse_args().generated_app)
