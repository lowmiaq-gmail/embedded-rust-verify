#!/usr/bin/env python3
"""ELF section accounting; static/reserved RAM is not measured peak RAM."""
import json,subprocess,hashlib,pathlib
flash_sections=['.vector_table','.text','.rodata','.data','.ARM.exidx','.ARM.extab']
static_sections=['.data','.bss','.uninit']
required_sections={'.vector_table','.text','.rodata','.data','.bss','.uninit'}
out={
 "status":"BUILD_ONLY",
 "flash_accounting_sections":flash_sections,
 "static_ram_accounting_sections":static_sections,
 "stack_reserved_bytes":16384,
 "stack_peak_bytes":None,
 "stack_peak_reason":"No reliable physical-board high-water observation has been collected.",
 "heap_peak_bytes":None,
 "heap_policy":"No global allocator or heap region is configured in the no_std firmware or linker script.",
 "working_ram_peak_bytes":None,
 "working_ram_peak_reason":"Static RAM and reserved stack are not a measured workload peak.",
 "application_budget_status":"NOT_EVALUATED",
 "binaries":{}
}
for variant in ('raw','safe'):
 p=pathlib.Path('reports/local')/(variant+'.elf')
 text=subprocess.check_output(['arm-none-eabi-size','-A',str(p)],text=True)
 p.with_suffix('.size.txt').write_text(text)
 sections={}
 for line in text.splitlines():
  fields=line.split()
  if len(fields)==3 and fields[0].startswith('.'):
   if fields[0] in sections:raise SystemExit(f'Duplicate ELF section name: {fields[0]}')
   sections[fields[0]]=int(fields[1])
 missing=required_sections-sections.keys()
 if missing:raise SystemExit('Missing expected ELF sections: '+', '.join(sorted(missing)))
 # Cortex-m-rt linker has .vector_table/.text/.rodata/.data with load images in Flash.
 flash=sum(sections.get(k,0) for k in flash_sections)
 static=sum(sections.get(k,0) for k in static_sections)
 nm=subprocess.check_output(['arm-none-eabi-nm','-u',str(p)],text=True)
 heap_symbols=[line for line in nm.splitlines() if any(name in line for name in ('__rust_alloc','malloc','calloc','realloc','free'))]
 if heap_symbols:raise SystemExit(f'Unexpected heap/allocation symbols in {p}: {heap_symbols}')
 out['binaries'][variant]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'sections':sections,'flash_section_bytes':flash,'ram_static_bytes':static,'ram_reserved_total_bytes':static+16384,'heap_symbols':heap_symbols}
pathlib.Path('reports/local/size.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
