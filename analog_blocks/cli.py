"""Command line: ``python -m analog_blocks run`` simulates everything and writes results/."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import pdk, plots, suite
from .checks import all_checks, hand_drift_ppm
from .spice import ngspice_available


def _jsonable(obj):
    """Drop array-valued keys (the ``_`` prefix) and convert numpy scalars."""
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items() if not str(k).startswith("_")}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "item"):
        return obj.item()
    if isinstance(obj, float) and obj != obj:
        return None
    return obj


def write_summary(result: dict, out: Path) -> None:
    nom = result["nominal"]
    (out / "summary.json").write_text(json.dumps(_jsonable(result), indent=2) + "\n")
    checks = all_checks(result)
    lines = [
        "# Simulation summary",
        "",
        f"PDK: SkyWater Sky130, pinned to {pdk.PDK_COMMIT[:12]}. Simulator: ngspice.",
        "All numbers are from ngspice runs. Hand values use the simulated bias point.",
        "",
        "## Checks against hand calculations",
        "",
        "| check | simulated | hand / target | rule | result |",
        "|---|---|---|---|---|",
        *[c.row() for c in checks],
        "",
        f"{sum(c.passed for c in checks)} of {len(checks)} checks pass.",
        "",
        f"Bandgap drift: the hand formula with the simulated Vbe gives "
        f"{hand_drift_ppm(nom['bandgap']['_vref_hand'], nom['bandgap']['_temps']):.0f} ppm/C; "
        f"the simulation gives {nom['bandgap']['drift_ppm_per_c']:.0f} ppm/C. The gap comes from the "
        "output mirror leg sitting at a different drain voltage, which the hand formula ignores.",
        "",
        "## Monte Carlo offset",
        "",
        f"n = {result['monte_carlo']['n']} samples, sigma = {result['monte_carlo']['sigma_mv']:.2f} mV, "
        f"mean = {result['monte_carlo']['mean_mv']:.2f} mV.",
        "",
        "## Ring oscillator tuning",
        "",
        "| Vctl (V) | simulated (MHz) | hand (MHz) | starve current (uA) |",
        "|---|---|---|---|",
        *[f"| {r['vctl']:.2f} | {r['freq_mhz']:.1f} | {r['hand_mhz']:.0f} | {r['starve_ua']:.0f} |"
          for r in result["vco_tuning"]],
        "",
    ]
    pvt_rows = result.get("pvt", [])
    if pvt_rows:
        lines += [
            "## PVT sweep",
            "",
            "| corner | VDD (V) | T (C) | op-amp gain (dB) | UGF (MHz) | PM (deg) | Vref (V) | "
            "comparator | delay (ps) | VCO (MHz) |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in pvt_rows:
            if "error" in r:
                lines.append(f"| {r['corner']} | {r['vdd']} | {r['temp']:g} | error: {r['error']} |||||||")
                continue
            lines.append(
                f"| {r['corner']} | {r['vdd']} | {r['temp']:g} | {r['opamp_gain_db']:.1f} | "
                f"{r['opamp_ugf_mhz']:.1f} | {r['opamp_pm_deg']:.1f} | {r['bandgap_vref']:.4f} | "
                f"{'ok' if r['cmp_correct'] else 'WRONG'} | {r['cmp_delay_ps']:.0f} | {r['vco_freq_mhz']:.0f} |"
            )
        lines.append("")
    (out / "summary.md").write_text("\n".join(lines) + "\n")


def run(out: Path, quick: bool) -> int:
    if not ngspice_available():
        print("ngspice is not on PATH. Install it first (brew install ngspice, or apt-get install ngspice).",
              file=sys.stderr)
        return 2
    if not pdk.is_available():
        print(f"Sky130 models not found under {pdk.pdk_root()}. Run scripts/fetch_pdk.sh first.",
              file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)

    def progress(msg: str) -> None:
        print(msg, flush=True)

    result = suite.run_suite(quick=quick, progress=progress)
    write_summary(result, out)
    plots.make_all(result, out)
    checks = all_checks(result)
    failed = [c for c in checks if not c.passed]
    print(f"{len(checks) - len(failed)}/{len(checks)} checks pass; results in {out}")
    for c in failed:
        print(f"FAIL: {c.name}: simulated {c.measured:.4g}, expected {c.expected:.4g} ({c.rule})")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="analog_blocks", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="simulate all blocks and write results")
    run_p.add_argument("--out", type=Path, default=Path("results"), help="output folder")
    run_p.add_argument("--quick", action="store_true", help="skip the PVT sweep and use fewer MC samples")
    args = parser.parse_args(argv)
    if args.cmd == "run":
        return run(args.out, args.quick)
    return 2
