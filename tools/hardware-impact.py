"""Emit an explicit hardware-evidence request, not a fabricated hardware pass."""
import subprocess,sys
files=subprocess.check_output(['git','diff','--name-only',sys.argv[1],sys.argv[2]]).decode().splitlines()
code=[p for p in files if not p.endswith('.md') and not p.startswith(('docs/','reports/'))]
print('Hardware evidence REQUIRED: '+', '.join(code) if code else 'No hardware-impacting changes')
