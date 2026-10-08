#!/usr/bin/env python3
"""Sample an existing evaluation process tree, without changing CPU policies."""
import argparse,json,time,pathlib,os
import psutil
ap=argparse.ArgumentParser();ap.add_argument('pid',type=int);ap.add_argument('output');a=ap.parse_args()
rows=[];start=time.monotonic()
while psutil.pid_exists(a.pid):
    try:
        root=psutil.Process(a.pid)
        if root.status()==psutil.STATUS_ZOMBIE:break
        procs=[root]+root.children(recursive=True);rss=cpu=0;alive=0
        for p in procs:
            try:
                rss+=p.memory_info().rss;t=p.cpu_times();cpu+=t.user+t.system;alive+=1
            except psutil.Error:pass
        rows.append({'elapsed_s':time.monotonic()-start,'tree_rss_bytes':rss,'live_process_cpu_s':cpu,'processes':alive,'cgroup_memory_current':int(pathlib.Path('/sys/fs/cgroup/memory.current').read_text())})
        pathlib.Path(a.output).write_text(json.dumps({'note':'Sampling began partway through grid evaluation. RSS sums may double-count shared pages; live CPU excludes reaped processes. Cgroup includes unrelated environment processes. Not a whole-run maximum guarantee.','sample_period_s':1,'samples':rows},indent=2))
        time.sleep(1)
    except psutil.Error:break
