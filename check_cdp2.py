# -*- coding: utf-8 -*-
import json, urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:9222/json/version', timeout=4) as r:
        v = json.loads(r.read().decode())
    print('CDP UP:', v.get('Browser'))
    with urllib.request.urlopen('http://127.0.0.1:9222/json/list', timeout=4) as r:
        ts = json.loads(r.read().decode())
    print('targets:', len(ts))
    for t in ts[:10]:
        print(' -', t.get('type'), str(t.get('url'))[:80])
except Exception as e:
    print('CDP DOWN:', repr(e)[:80])
