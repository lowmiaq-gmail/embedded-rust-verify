import hashlib,json,pathlib
m=json.loads(pathlib.Path('vendor/manifest.json').read_text())
for name,expected in m['files'].items():
 assert hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()==expected,name
print('Vendor file hashes PASS')
