#!/usr/bin/env python3
"""Headless Dashboard v2 model benchmark; never connects to a PLC."""

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.dashboard_model import (  # noqa: E402
    dashboard_statistics, filter_dashboard_population,
    sort_dashboard_population,
)
from core.tag_model import TagDefinition  # noqa: E402
from core.tag_runtime import RuntimeTagCache  # noqa: E402


def measured(callback):
    started=time.perf_counter(); result=callback()
    return result,(time.perf_counter()-started)*1000


def benchmark(count):
    tags=[TagDefinition(f"Tag{i:05d}",("BOOL","INT","REAL")[i%3],"Input",f"A{i}",i%2==0,i%3==0,i%5==0,True,f"Comment {i}") for i in range(count)]
    runtime=RuntimeTagCache(); runtime.sync(tags)
    for index,tag in enumerate(tags): runtime.update(tag.name,index if tag.data_type!="BOOL" else bool(index%2))
    population,populate_ms=measured(lambda:list(tags))
    filtered,search_ms=measured(lambda:filter_dashboard_population(population,"comment 49",{"features":["simulation"]},runtime))
    _,filter_ms=measured(lambda:filter_dashboard_population(population,filters={"statuses":["GOOD"],"types":["BOOL","REAL"]},runtime=runtime))
    _,sort_ms=measured(lambda:sort_dashboard_population(population,"value",True,runtime))
    runtime.update(tags[count//2].name,-1)
    _,update_batch_ms=measured(lambda:dashboard_statistics(population,runtime))
    return {"tags":count,"population_ms":round(populate_ms,3),"search_ms":round(search_ms,3),"filter_ms":round(filter_ms,3),"sort_ms":round(sort_ms,3),"update_statistics_ms":round(update_batch_ms,3),"narrow_result":len(filtered)}


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--counts",type=int,nargs="+",default=[50,1000,5000]); parser.add_argument("--output")
    args=parser.parse_args(); results=[benchmark(count) for count in args.counts]
    payload=json.dumps(results,indent=2)
    if args.output: Path(args.output).write_text(payload+"\n",encoding="utf-8")
    print(payload)


if __name__=="__main__": main()
