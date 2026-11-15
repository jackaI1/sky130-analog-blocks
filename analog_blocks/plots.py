"""Save the result plots as PNG files. Keys that start with ``_`` hold the arrays."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from . import pdk  # noqa: E402


def _save(fig, out: Path, name: str) -> Path:
    path = out / name
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def opamp_bode(result: dict, out: Path) -> Path:
    bode = result["nominal"]["opamp"]["_bode"]
    freq, mag, phase = bode[:, 0], bode[:, 1], np.degrees(np.unwrap(bode[:, 2]))
    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(7, 6))
    ax1.semilogx(freq, mag, color="#1f5f8b")
    ax1.axhline(0, color="grey", lw=0.8, ls="--")
    ax1.set_ylabel("|gain| (dB)")
    ax1.set_title("Two-stage op-amp, open loop, tt 27 C, 1.8 V")
    ax2.semilogx(freq, phase, color="#b5532c")
    ax2.set_ylabel("phase (deg)")
    ax2.set_xlabel("frequency (Hz)")
    op = result["nominal"]["opamp"]
    ax2.axvline(op["ugf_mhz"] * 1e6, color="grey", lw=0.8, ls=":")
    ax2.text(op["ugf_mhz"] * 1e6, phase[0] - 20,
             f" UGF {op['ugf_mhz']:.1f} MHz\n PM {op['pm_deg']:.1f} deg", fontsize=8)
    return _save(fig, out, "opamp_bode.png")


def opamp_noise(result: dict, out: Path) -> Path:
    op = result["nominal"]["opamp"]
    freq, dens = op["_noise_freq"], op["_noise_density"]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.loglog(freq, dens * 1e9, color="#1f5f8b", label="simulated, input-referred")
    ax.axhline(op["thermal_floor_nv"], color="#b5532c", ls="--",
               label=f"hand thermal floor {op['thermal_floor_nv']:.1f} nV/rtHz")
    ax.set_xlabel("frequency (Hz)")
    ax.set_ylabel("noise (nV/rtHz)")
    ax.set_title("Op-amp input noise: 1/f rises below ~1 MHz")
    ax.legend(fontsize=8)
    return _save(fig, out, "opamp_noise.png")


def bandgap_vs_temp(result: dict, pvt_rows: list[dict], out: Path) -> Path:
    bg = result["nominal"]["bandgap"]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(bg["_temps"], bg["_vref"], color="#1f5f8b", label="simulated, tt, 1.8 V")
    ax.plot(bg["_temps"], bg["_vref_hand"], color="#b5532c", ls="--",
            label="hand: Vbe(sim) + (R2/R1) VT ln 8")
    colors = {"tt": "k", "ff": "#2e7d32", "ss": "#c62828", "sf": "#6a1b9a", "fs": "#00838f"}
    for corner in pdk.CORNERS:
        rows = [r for r in pvt_rows if r.get("corner") == corner and "bandgap_vref" in r and r["vdd"] == 1.8]
        if rows:
            ax.plot([r["temp"] for r in rows], [r["bandgap_vref"] for r in rows], "o",
                    color=colors[corner], ms=4, label=f"{corner} corner, 1.8 V")
    ax.set_xlabel("temperature (C)")
    ax.set_ylabel("Vref (V)")
    ax.set_title(f"Bandgap reference, drift {bg['drift_ppm_per_c']:.0f} ppm/C (tt)")
    ax.legend(fontsize=7, ncol=2)
    return _save(fig, out, "bandgap_vs_temp.png")


def vco_tuning(result: dict, out: Path) -> Path:
    rows = result["vco_tuning"]
    vctl = [r["vctl"] for r in rows]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(vctl, [r["freq_mhz"] for r in rows], "o-", color="#1f5f8b", label="simulated")
    ax.plot(vctl, [r["hand_mhz"] for r in rows], "s--", color="#b5532c", label="hand: I/(N C VDD)")
    ax.set_xlabel("control voltage Vctl (V)")
    ax.set_ylabel("frequency (MHz)")
    ax.set_title("Current-starved ring oscillator tuning")
    ax.legend(fontsize=8)
    return _save(fig, out, "vco_tuning.png")


def mc_offset(result: dict, out: Path) -> Path:
    mc = result["monte_carlo"]
    hand = result["nominal"]["offset"]["sigma_hand_mv"]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.hist(mc["offsets_mv"], bins=min(25, max(8, mc["n"] // 4)), color="#1f5f8b", alpha=0.8)
    ax.axvline(0, color="grey", lw=0.8)
    ax.set_xlabel("input-referred offset (mV)")
    ax.set_ylabel("count")
    ax.set_title(f"Monte Carlo mismatch, n={mc['n']}: sigma {mc['sigma_mv']:.2f} mV "
                 f"(hand {hand:.2f} mV)")
    return _save(fig, out, "mc_offset.png")


def make_all(result: dict, out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    pvt_rows = result.get("pvt", [])
    return [
        opamp_bode(result, out),
        opamp_noise(result, out),
        bandgap_vs_temp(result, pvt_rows, out),
        vco_tuning(result, out),
        mc_offset(result, out),
    ]
