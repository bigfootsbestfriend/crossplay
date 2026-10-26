"""Merge verified pass-2 batches into data/manual.json (2026-10-26). Entries with verify.result == skip are left out
and listed; the rest get audited/checked dates. Existing entries with the same title are replaced."""
import json, sys, glob, re
M = 'data/manual.json'
man = json.load(open(M))
games = man['games']
key = lambda t: re.sub('[^a-z0-9]', '', t.lower())
idx = {key(g['title']): i for i, g in enumerate(games)}
added, replaced, skipped = [], [], []
for f in sorted(glob.glob('research/batch/*-pass2.json')):
    for e in json.load(open(f)):
        v = e.pop('verify', {}) or {}
        if e.get('skip') or v.get('result') == 'skip':
            skipped.append((e['title'], v.get('what') or e.get('skip'))); continue
        e['checked'] = '2026-10-26'; e['audited'] = '2026-10-26'
        e.setdefault('igdb_id', None)
        k = key(e['title'])
        if k in idx:
            old = games[idx[k]]
            if old.get('igdb_id') and not e.get('igdb_id'): e['igdb_id'] = old['igdb_id']
            for keep in ('replaces', 'news'):
                if keep in old and keep not in e: e[keep] = old[keep]
            games[idx[k]] = e; replaced.append(e['title'])
        else:
            games.append(e); idx[k] = len(games) - 1; added.append(e['title'])
games.sort(key=lambda g: g['title'].lower())
s = json.dumps(man, indent=1, ensure_ascii=False) + '\n'
new = json.dumps([g for g in games if g['title'] in added + replaced], ensure_ascii=False)
assert '\u2014' not in new and '\u2013' not in new
if '--write' in sys.argv: open(M, 'w').write(s)
print('added', len(added), added); print('replaced', replaced); print('skipped', skipped)
