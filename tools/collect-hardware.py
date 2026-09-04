#!/usr/bin/env python3
"""Parse real semihosting logs; never synthesize timing observations."""
import argparse,json,pathlib,re,statistics,hashlib
p=argparse.ArgumentParser();p.add_argument('--raw',required=True);p.add_argument('--safe',required=True);p.add_argument('--board-serial',required=True);p.add_argument('--clock-hz',required=True,type=int);p.add_argument('--host-report',default='reports/local/host.json');p.add_argument('--out',default='reports/local/hardware.json');a=p.parse_args()
r={'schema':1,'board':'NUCLEO-F401RE','board_serial':a.board_serial,'clock_hz':a.clock_hz,'scope':'initialization plus eight blocks of 64 samples, 31 taps; raw C path includes checked Rust dispatch','runs':{}}
for mode in ['raw','safe']:
 text=pathlib.Path(getattr(a,mode)).read_text();rows=[]
 for m in re.finditer(r'FIR,(\d+),(\d+),(\d+),([0-9a-f]{16})',text):
  n,cycles,overhead,digest=m.groups();rows.append({'run':int(n),'cycles':int(cycles),'timer_overhead':int(overhead),'digest':digest})
 if [x['run'] for x in rows]!=list(range(21)): raise SystemExit('Need warm-up run 0 and exactly 20 retained samples')
 if any(x['cycles']<=0 for x in rows):raise SystemExit('Cycle counter did not advance')
 r['runs'][mode]={'samples':rows,'median_cycles_excluding_warmup':statistics.median(x['cycles'] for x in rows[1:]),'log_sha256':hashlib.sha256(text.encode()).hexdigest()}
r['functional_digest_match']=len({x['digest'] for v in r['runs'].values() for x in v['samples']})==1
host=json.loads(pathlib.Path(a.host_report).read_text())
expected=host['hardware_corpus']
r['independent_reference_crosscheck']=expected['reference_pass'] and all(x['digest']==expected['expected_digest'] for v in r['runs'].values() for x in v['samples'])
r['functional_digest_match'] &= r['independent_reference_crosscheck']
r['status']='PASS' if r['functional_digest_match'] else 'FAIL'
pathlib.Path(a.out).write_text(json.dumps(r,indent=2)+'\n')
if r['status']!='PASS':raise SystemExit(1)
