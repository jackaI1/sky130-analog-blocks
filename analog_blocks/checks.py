"""Pass/fail checks: simulated numbers against hand calculations.

The same list is printed in ``summary.md`` and asserted by the tests, so the
report and the tests cannot disagree.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Check:
    name: str
    measured: float
    expected: float
    passed: bool
    rule: str

    def row(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"| {self.name} | {self.measured:.4g} | {self.expected:.4g} | {self.rule} | {status} |"


def _abs(name: str, measured: float, expected: float, tol: float, unit: str) -> Check:
    return Check(name, measured, expected, abs(measured - expected) <= tol,
                 f"within +/-{tol:g} {unit}")


def _rel(name: str, measured: float, expected: float, tol: float) -> Check:
    return Check(name, measured, expected, abs(measured - expected) <= tol * abs(expected),
                 f"within +/-{tol * 100:.0f}%")


def nominal_checks(result: dict) -> list[Check]:
    nom = result["nominal"]
    op, bg, cmp_, vco, offset = nom["opamp"], nom["bandgap"], nom["comparator"], nom["vco"], nom["offset"]
    mc = result["monte_carlo"]
    return [
        _abs("op-amp DC gain (dB)", op["dc_gain_db"], op["dc_gain_hand_db"], 1.0, "dB"),
        _rel("op-amp unity-gain freq (MHz)", op["ugf_mhz"], op["gbw_hand_mhz"], 0.15),
        _abs("op-amp phase margin (deg)", op["pm_deg"], op["pm_hand_deg"], 8.0, "deg"),
        _abs("bandgap Vref at 27 C (V)", bg["vref_27c"], _at(bg["_temps"], bg["_vref_hand"], 27.0), 0.03, "V"),
        Check("bandgap drift, -40 to 125 C (ppm/C)", bg["drift_ppm_per_c"], 100.0,
              bg["drift_ppm_per_c"] <= 100.0, "spec: <= 100 ppm/C (hand estimate is in summary.md)"),
        _rel("op-amp offset sigma, Monte Carlo (mV)", mc["sigma_mv"], offset["sigma_hand_mv"], 0.35),
        Check("op-amp noise 1 MHz above thermal floor (nV/rtHz)", op["noise_nv_1m"], op["thermal_floor_nv"],
              op["noise_nv_1m"] >= op["thermal_floor_nv"], "simulated >= hand floor (flicker adds)"),
        Check("comparator decides +10 mV high and -10 mV low", float(cmp_["decide_plus_10mv_high"]),
              1.0, cmp_["decide_plus_10mv_high"] and not cmp_["decide_minus_10mv_high"], "both polarities correct"),
        Check("comparator delay (ps)", cmp_["delay_ps"], 0.0, cmp_["delay_ps"] < 1000.0, "< 1000 ps"),
        Check("VCO sim/hand frequency ratio", vco["freq_mhz"] / vco["hand_freq_mhz"], 1.0,
              0.1 <= vco["freq_mhz"] / vco["hand_freq_mhz"] <= 0.5,
              "0.1-0.5 (hand is optimistic, see design.md)"),
    ]


def pvt_checks(result: dict) -> list[Check]:
    rows = result.get("pvt", [])
    if not rows:
        return []
    errors = [r for r in rows if "error" in r]
    return [
        Check("PVT points simulated without error", float(len(rows) - len(errors)), float(len(rows)),
              not errors, "all corners, supplies and temperatures"),
        Check("comparator correct at every PVT point", float(sum(r.get("cmp_correct", False) for r in rows)),
              float(len(rows)), all(r.get("cmp_correct", False) for r in rows), "all points"),
        Check("bandgap Vref min across PVT (V)", min(r["bandgap_vref"] for r in rows if "bandgap_vref" in r),
              1.15, all(1.15 <= r["bandgap_vref"] <= 1.27 for r in rows if "bandgap_vref" in r),
              "between 1.15 and 1.27 V"),
        Check("op-amp phase margin min across PVT (deg)",
              min(r["opamp_pm_deg"] for r in rows if "opamp_pm_deg" in r), 45.0,
              min(r["opamp_pm_deg"] for r in rows if "opamp_pm_deg" in r) >= 45.0, ">= 45 deg"),
    ]


def all_checks(result: dict) -> list[Check]:
    return nominal_checks(result) + pvt_checks(result)


def _at(temps: list[float], values: list[float], t: float) -> float:
    for temp, value in zip(temps, values):
        if abs(temp - t) < 1e-9:
            return value
    raise ValueError(f"no point at {t} C")


def hand_drift_ppm(values: list[float], temps: list[float]) -> float:
    """Drift of the hand formula's Vref(T), same box method as the simulation."""
    span = max(temps) - min(temps)
    mean = sum(values) / len(values)
    return (max(values) - min(values)) / span / mean * 1e6
