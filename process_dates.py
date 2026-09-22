import json
from datetime import datetime

# Read base_data.json
with open('model/base_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Build fixture lookup: {(gw, home, away): kickoff_date}
fixture_dates = {}
for fix in data.get('fixtures', []):
    gw = fix.get('gw')
    home = fix.get('home')
    away = fix.get('away')
    kickoff_utc = fix.get('kickoff_utc')
    
    if kickoff_utc:
        try:
            dt = datetime.fromisoformat(kickoff_utc.replace('Z', '+00:00'))
            # Format as "26 Sep"
            date_str = dt.strftime('%d %b').lstrip('0')
            fixture_dates[(gw, home, away)] = date_str
        except:
            pass

# Print sample
print("Sample fixture dates extracted:")
for i, (key, date) in enumerate(list(fixture_dates.items())[:5]):
    gw, home, away = key
    print(f"  GW{gw} · {date} · {home} vs {away}")
    
print(f"\nTotal fixtures with dates: {len(fixture_dates)}")
