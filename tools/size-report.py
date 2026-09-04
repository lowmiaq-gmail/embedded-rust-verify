#!/usr/bin/env python3
"""ELF section accounting; static/reserved RAM is not measured peak RAM."""
import json,subprocess,hashlib,pathlib
out={"status":"BUILD_ONLY","stack_reserved_bytes":16384,"stack_peak_bytes":None,"heap_peak_bytes":None,"binaries":{}}
for variant in ('raw','safe'):
 p=pathlib.Path('reports/local')/(variant+'.elf')
 text=subprocess.check_output(['arm-none-eabi-size','-A',str(p)],text=True)
 p.with_suffix('.size.txt').write_text(text)
 sections={}
 for line in text.splitlines():
  fields=line.split()
  if len(fields)==3 and fields[0].startswith('.'):
   sections[fields[0]]=int(fields[1])
 # Cortex-m-rt linker has .vector_table/.text/.rodata/.data with load images in Flash.
 flash=sum(sections.get(k,0) for k in ['.vector_table','.text','.rodata','.data','.ARM.exidx','.ARM.extab'])
 static=sections.get('.data',0)+sections.get('.bss',0)+sections.get('.uninit',0)
 out['binaries'][variant]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'sections':sections,'flash_section_bytes':flash,'ram_static_bytes':static,'ram_reserved_total_bytes':static+16384}
pathlib.Path('reports/local/size.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
