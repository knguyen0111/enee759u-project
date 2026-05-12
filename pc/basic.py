import subprocess
import os
import sys
import csv
import shutil
import xml.etree.ElementTree as ET

# ==============================================================================
# CONFIG — Windows-native paths (D:\...) work everywhere including Git Bash
# ==============================================================================
VITIS_BIN   = r"D:\AMDDesignTools\2025.2\Vitis\bin"
# On Windows, Vitis ships .bat launchers; resolve_binary() handles this.
VITIS_RUN   = os.path.join(VITIS_BIN, "vitis-run")
VPP         = os.path.join(VITIS_BIN, "v++")
PART        = "xczu5ev-fbvb900-2-i"
TOP         = "fir"
WORK_DIR    = "basic"
SRC         = os.path.join(WORK_DIR, "fir.cpp")
CONFIG_FILE = os.path.join(WORK_DIR, "hls_config.cfg")

# Testbench filename — your environment check showed this is tb_fir.cpp
TB_FILE     = "tb_fir.cpp"   # change to "fir_tb.cpp" if needed

# single test point — relaxed clock for smoke test
CLOCK_NS    = 5.0
LABEL       = "no_pragma"
PIPELINE    = False
UNROLL      = 1
ARRAY_PART  = False

RESULTS_DIR = "results"
RESULTS_CSV = os.path.join(RESULTS_DIR, "basic_result.csv")
LOG_FILE    = os.path.join(RESULTS_DIR, "basic_run.log")
# ==============================================================================


def resolve_binary(preferred):
    """
    Find the actual executable for a Vitis tool on Windows.
    Tries preferred path bare, then with .bat/.exe extensions,
    then falls back to shutil.which() on PATH.
    Returns the resolved path string, or None if not found.
    """
    base = os.path.splitext(preferred)[0]   # strip any extension
    name = os.path.basename(base)

    # Ordered list of candidates: exact path first, then Windows suffixes
    candidates = [preferred]
    for suffix in (".bat", ".exe", ".cmd"):
        candidates.append(base + suffix)

    for candidate in candidates:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate

    # Fall back to PATH search
    for suffix in ("", ".bat", ".exe", ".cmd"):
        found = shutil.which(name + suffix)
        if found:
            return found

    return None


def check_environment():
    """
    Verify binaries and shared files exist.
    Returns (vitis_run_path, vpp_path) or (None, None) on failure.
    """
    print("\n--- Environment Check ---")

    ok = True
    resolved = {}
    for label, preferred in [("vitis-run", VITIS_RUN), ("v++", VPP)]:
        path = resolve_binary(preferred)
        if path:
            print(f"  {label:>12}: {path}  [OK]")
            resolved[label] = path
        else:
            print(f"  {label:>12}: NOT FOUND")
            print(f"               Searched: {preferred}(.bat/.exe/.cmd)")
            print(f"               Also searched PATH for: {os.path.basename(os.path.splitext(preferred)[0])}")
            print(f"               Run:  dir \"{VITIS_BIN}\"  to see what's there")
            ok = False

    print("\n  Vitis-related PATH entries:")
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if any(k in entry for k in ("Vitis", "Vivado", "AMD", "Xilinx")):
            print(f"    {entry}")

    print("\n  Key environment variables:")
    for var in ("XILINX_VITIS", "XILINX_HLS"):
        print(f"    {var} = {os.environ.get(var, '<not set>')}")

    print("\n  Shared source files:")
    for path in [TB_FILE, "taps_init.h", "io/input.mem", "io/output_15.mem"]:
        exists = os.path.isfile(path)
        print(f"    {'OK' if exists else 'MISSING':>7}  {path}")
        if not exists:
            ok = False

    print("-------------------------\n")

    if not ok:
        return None, None
    return resolved.get("vitis-run"), resolved.get("v++")


def make_fir(pipeline, unroll, array_partition):
    pipeline_pragma  = "    #pragma HLS PIPELINE II=1" if pipeline else ""
    partition_pragma = """\
    #pragma HLS ARRAY_PARTITION variable=shift complete
    #pragma HLS ARRAY_PARTITION variable=h complete""" if array_partition else ""
    unroll_pragma    = f"        #pragma HLS UNROLL factor={unroll}" if unroll > 1 else ""

    return f"""\
#include "ap_int.h"
#include "../taps_init.h"
#define NTAPS 64

void fir(ap_int<16> sample_in, ap_int<16> &sample_out) {{
{pipeline_pragma}

    static ap_int<16> shift[NTAPS];

{partition_pragma}

    ap_int<40> acc = 0;

    for (int i = NTAPS-1; i > 0; --i) {{
        shift[i] = shift[i-1];
    }}
    shift[0] = sample_in;

    for (int i = 0; i < NTAPS; ++i) {{
{unroll_pragma}
        acc += (ap_int<32>)h[i] * (ap_int<32>)shift[i];
    }}

    sample_out = (ap_int<16>)((acc + 0x4000) >> 15);
}}
"""


def make_config(clock_ns):
    """
    Paths in hls_config.cfg are relative to the config file location (basic/).
    Forward slashes work on Windows in Vitis config files.
    """
    return f"""\
part={PART}

[hls]
flow_target=vivado
package.output.format=ip_catalog
package.output.syn=false
clock={clock_ns}ns
syn.top={TOP}
syn.file=./fir.cpp
tb.file=../{TB_FILE}
tb.file=../io/input.mem
tb.file=../io/output_15.mem
"""


def _run(cmd, step_name, log_fh):
    """
    Run a subprocess, print full output, write to log.
    On Windows, always wraps with 'cmd.exe /c' so Vitis .bat launchers work.
    WinError 193 means a .bat was passed directly to CreateProcess — fixed here.
    Returns (returncode, combined_output_str).
    """
    cmd = [str(c) for c in cmd]
    print(f"\n  [{step_name}] Command: {' '.join(cmd)}")
    log_fh.write(f"\n{'='*60}\n[{step_name}] {' '.join(cmd)}\n{'='*60}\n")

    env = os.environ.copy()

    # On Windows, always wrap in cmd.exe /c.
    # Vitis ships .bat launchers; passing them directly to subprocess causes
    # WinError 193 (%1 is not a valid Win32 application) regardless of whether
    # resolve_binary() returned the name with or without the .bat extension.
    if os.name == "nt":
        launcher = ["cmd.exe", "/c"] + cmd
    else:
        launcher = cmd

    try:
        result = subprocess.run(
            launcher,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,   # merge so output is in order
            text=True,
            env=env,
        )
    except FileNotFoundError as e:
        msg = (
            f"\n  ERROR: Could not launch '{launcher[0]}'\n"
            f"  {e}\n"
            f"  Ensure Vitis is installed at {VITIS_BIN}\n"
        )
        print(msg)
        log_fh.write(msg)
        return -1, str(e)

    # Full output — no truncation
    print(result.stdout)
    log_fh.write(result.stdout)
    return result.returncode, result.stdout


def run_csim(vitis_run, log_fh):
    print(f"\n  [csim] Running C simulation...")
    cmd = [
        vitis_run, "--mode", "hls", "--csim",
        "--config", CONFIG_FILE,
        "--work_dir", WORK_DIR,
    ]
    rc, out = _run(cmd, "csim", log_fh)

    if rc == -1:
        print("  FAILED — binary not launched (see above)")
        return False
    if rc != 0:
        print(f"  FAILED — vitis-run exited with code {rc}")
        return False
    if "FAIL" in out:
        print("  WARNING: csim output contains FAIL")
        return False
    if "PASS" in out:
        print("  csim: PASS")
    else:
        print("  WARNING: csim returned 0 but no PASS found — continuing anyway")
    return True


def run_synthesis(vpp, log_fh):
    print(f"  [synth] Running C synthesis...")
    cmd = [
        vpp, "-c", "--mode", "hls",
        "--config", CONFIG_FILE,
        "--work_dir", WORK_DIR,
    ]
    rc, _ = _run(cmd, "synth", log_fh)

    if rc == -1:
        print("  FAILED — binary not launched (see above)")
        return False
    if rc != 0:
        print(f"  FAILED — v++ exited with code {rc}")
        return False
    return True


def find_report():
    target = f"{TOP}_csynth.xml"
    for dirpath, _dirnames, files in os.walk(WORK_DIR):
        for f in files:
            if f == target:
                found = os.path.join(dirpath, f)
                print(f"  Found report: {found}")
                return found

    print(f"  ERROR: {target} not found under {WORK_DIR}/")
    print(f"  Full file tree under {WORK_DIR}/:")
    for dirpath, _dirnames, files in os.walk(WORK_DIR):
        for f in files:
            print(f"    {os.path.join(dirpath, f)}")
    return None


def parse_report():
    path = find_report()
    if path is None:
        return None

    tree = ET.parse(path)
    root = tree.getroot()

    perf = root.find("PerformanceEstimates")
    lat  = perf.find("SummaryOfOverallLatency")
    clk  = perf.find("SummaryOfTimingAnalysis/EstimatedClockPeriod")
    area = root.find("AreaEstimates/Resources")

    timing_ok = True
    violations = perf.find("SummaryOfViolations")
    if violations is not None:
        vtype = violations.find("ViolationType")
        if vtype is not None and vtype.text and vtype.text.strip() != "-":
            timing_ok = False

    ii_elem = lat.find("PipelineInitiationInterval")
    ii = int(ii_elem.text) if ii_elem is not None and ii_elem.text else -1

    return {
        "dsp"        : int(area.find("DSP").text),
        "lut"        : int(area.find("LUT").text),
        "ff"         : int(area.find("FF").text),
        "bram"       : int(area.find("BRAM_18K").text),
        "latency"    : int(lat.find("Worst-caseLatency").text),
        "ii"         : ii,
        "achieved_ns": float(clk.text),
        "timing_ok"  : timing_ok,
    }


def main():
    print(f"\n{'='*60}")
    print(f"  basic.py — HLS smoke test")
    print(f"  clock={CLOCK_NS}ns | config={LABEL} | unroll={UNROLL}")
    print(f"  cwd={os.getcwd()}  python={sys.executable}")
    print(f"{'='*60}")

    os.makedirs(WORK_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    print(f"\n  Directories ready: {WORK_DIR}/  {RESULTS_DIR}/")

    with open(LOG_FILE, "w") as log_fh:
        log_fh.write(f"basic.py run log\ncwd: {os.getcwd()}\n")

        vitis_run, vpp = check_environment()
        if vitis_run is None or vpp is None:
            print("  ABORT — fix the missing items listed above.")
            return

        # write fir.cpp
        with open(SRC, "w") as f:
            f.write(make_fir(PIPELINE, UNROLL, ARRAY_PART))
        print(f"  Wrote {SRC}")
        with open(SRC) as f:
            content = f.read()
        print("\n--- fir.cpp ---\n" + content + "---------------")
        log_fh.write(f"\n--- fir.cpp ---\n{content}\n")

        # write hls_config.cfg
        with open(CONFIG_FILE, "w") as f:
            f.write(make_config(CLOCK_NS))
        print(f"  Wrote {CONFIG_FILE}")
        with open(CONFIG_FILE) as f:
            content = f.read()
        print("\n--- hls_config.cfg ---\n" + content + "----------------------")
        log_fh.write(f"\n--- hls_config.cfg ---\n{content}\n")

        # csim
        if not run_csim(vitis_run, log_fh):
            print(f"\n  FAILED at csim. Full log: {LOG_FILE}")
            return

        # synthesis
        if not run_synthesis(vpp, log_fh):
            print(f"\n  FAILED at synthesis. Full log: {LOG_FILE}")
            return

        # parse report
        metrics = parse_report()
        if metrics is None:
            print(f"\n  FAILED — report not found. Full log: {LOG_FILE}")
            return

        print("\n--- Synthesis Results ---")
        for k, v in metrics.items():
            print(f"  {k:>12}: {v}")
        print("-------------------------")

        row = {"clock_ns": CLOCK_NS, "config": LABEL, "pipeline": PIPELINE,
               "unroll": UNROLL, "array_partition": ARRAY_PART, **metrics}
        fieldnames = ["clock_ns", "config", "pipeline", "unroll", "array_partition",
                      "dsp", "lut", "ff", "bram", "latency", "ii", "achieved_ns", "timing_ok"]
        with open(RESULTS_CSV, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(row)

        print(f"\n  Result saved to {RESULTS_CSV}")
        print(f"  Full log:        {LOG_FILE}")
        print(f"\n  DSP={metrics['dsp']} LUT={metrics['lut']} FF={metrics['ff']} "
              f"BRAM={metrics['bram']} Latency={metrics['latency']} "
              f"II={metrics['ii']} Achieved={metrics['achieved_ns']}ns "
              f"Timing={'OK' if metrics['timing_ok'] else 'VIOLATED'}")
        print("\n  Smoke test complete.")


if __name__ == "__main__":
    main()
