"""Isolated public B entrypoint cost; no audit observer or parameter changes."""
import argparse,copy,json,resource,time,tracemalloc
from pathlib import Path
from precision_audit.dataset import load
from test_separated_goal_head import decode
from fpl_v1_1_model.experimental_physical_timeline import PhysicalKernel,physical_sampler
from fpl_v1_1_model.b_event_simulator import conserved_events
from pm_preview_distributions import simulate_with_distributions

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--draws',type=int,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    r=load(a.inputs)[0];inp=decode(copy.deepcopy(r['input']));base=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;start=time.perf_counter();kernel=PhysicalKernel(inp,r['dist']);kt=time.perf_counter()-start
    # RSS is measured without tracemalloc: allocator instrumentation changes runtime.
    start=time.perf_counter()
    with conserved_events(),physical_sampler(kernel):result=simulate_with_distributions(inp,n=a.draws,seed=20261101,include_samples=True)
    row=dict(draws=a.draws,fixture_uuid=r['fixture_uuid'],kernel_seconds=kt,simulation_seconds=time.perf_counter()-start,process_peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,loaded_inputs_peak_RSS_KiB=base,json_payload_bytes=len(json.dumps(result).encode()),scope='Fresh process; original B aggregate+distribution+TS samples; includes all ten loaded source fixtures; one control fixture; warm filesystem; CPU contended with audit jobs')
    a.out.write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row))
if __name__=='__main__':main()
