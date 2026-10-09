import json, urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:9222/json/version', timeout=4) as r:
        info = json.loads(r.read().decode())
    print('CDP ALREADY UP:', info.get('Browser'))
except Exception as e:
    print('CDP NOT RUNNING:', repr(e)[:100])
