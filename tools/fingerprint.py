"""Evidence identity excludes prose/reports, includes build inputs and workflow policy."""
import hashlib,pathlib,subprocess
paths=subprocess.check_output(['git','ls-files','-z']).decode().split('\0')
h=hashlib.sha256()
for name in sorted(paths):
 if not name or name.startswith(('reports/','docs/')) or name.endswith('.md'):continue
 p=pathlib.Path(name)
 if p.is_file():h.update(name.encode()+b'\0'+p.read_bytes()+b'\0')
print(h.hexdigest())
