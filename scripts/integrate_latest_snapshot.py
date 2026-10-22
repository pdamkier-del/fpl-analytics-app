"""Explicit latest-verified-data policy in B copies; production is unchanged."""
def inject(out):
    for name in ['classic-manager.js','weekly-app.js']:
        path=out/name;text=path.read_text()
        old="||(requireCutoff&&Date.parse(raw.observed_at)>Date.parse(forecast.data_asof))"
        if text.count(old)!=1:raise ValueError('Manager cutoff anchor changed: '+name)
        text=text.replace(old,'')
        text=text.replace("if(report.runtime!=='original_locked_python'", "if(report.supports_B_snapshot_policy!==true)throw Error('Funktionen med seneste prognose afventer en opdatering af beregningstjenesten.');if(report.runtime!=='original_locked_python'")
        text=text.replace('body:{state,forecast_cutoff:',"body:{forecast_policy:FplLatestSnapshot.policy,state,forecast_cutoff:")
        text=text.replace('if(latest.forecast_sha256!==forecast.forecast_sha256)', 'if(!FplLatestSnapshot.enabled&&latest.forecast_sha256!==forecast.forecast_sha256)')
        if name=='classic-manager.js':
            text=text.replace('async function load(){', 'async function load(){if(busy&&forecast)return snapshot();')
            text=text.replace("function waitingReason(){", "function waitingReason(){if(FplLatestSnapshot.enabled)return FplLatestSnapshot.reason(state,forecast,official);")
        else:
            text=text.replace('async function load(){', 'async function load(){if(busy&&forecast)return;')
        path.write_text(text)
    path=out/'forecast-window.js';path.write_text(path.read_text()+'\nFplLatestSnapshot.installWindow();\n')
    # These are B-only assets, shared by the generated copies.
    base=out.parent
    for name,call in [('dashboard-team-news.js','installNews'),('planner-experience.js','installPlanner')]:
        path=base/name;text=path.read_text()
        if name=='planner-experience.js':
            for state in ['c.state?.observed_at','c.state.observed_at']:
                old='Date.parse('+state+')>Date.parse(c.forecast.data_asof)'
                new='(!root.FplLatestSnapshot?.enabled&&'+old+')'
                if new not in text:text=text.replace(old,new)
        # Idempotent when rebuilding an already integrated local tree.
        suffix='\nif(typeof FplLatestSnapshot!==\'undefined\')FplLatestSnapshot.'+call+'();\n'
        if suffix not in text:text+=suffix
        path.write_text(text)
    for path in out.glob('*.html'):
        text=path.read_text().replace('<head>','<head><script src="../latest-snapshot.js"></script>',1)
        path.write_text(text)
