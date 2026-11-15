"""Two-stage Miller-compensated op-amp in Sky130 transistors.

Topology (NMOS input pair, PMOS mirror load, PMOS common-source second
stage, NMOS current-source load, Miller capacitor ``CC`` across stage 2):

    inn -> M1 -> n1 (diode-connected PMOS M3 mirrors it to M4)
    inp -> M2 -> n2 (stage-1 output, shared with M4's drain)
    n2  -> M6 (PMOS common source) -> out, load M7 (NMOS mirror of the bias)
    bias: 20 uA into diode-connected M8, mirrored into tail M5 and load M7

The subckt is also the error amplifier inside the bandgap reference.
Every bench is generated as netlist text and run through ``simulate``,
so each number comes from ngspice.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import pdk
from .spice import simulate

VDD_NOM = 1.8
VCM = 0.9
IBIAS = 20e-6
CC = 1e-12
CLOAD = 1e-12

# Device sizes in micrometres (W, L). The netlist uses scale=1e-6.
SIZES = {
    "M1": (10, 0.5),
    "M2": (10, 0.5),
    "M3": (10, 0.5),
    "M4": (10, 0.5),
    "M5": (5, 0.5),
    "M6": (40, 0.5),
    "M7": (20, 0.5),
    "M8": (5, 0.5),
}
# Devices whose random Vth mismatch sets the input offset (see montecarlo.py).
MISMATCH_DEVICES = ("M1", "M2", "M3", "M4")

# Each gate sees an ideal offset source, so a Vth mismatch can be injected.
# M1 takes inn (inverting input). M2 takes inp (its drain is the stage-1 output n2).
_OTA_SUBCKT = f"""
.subckt ota2s inp inn out vdd vss PARAMS: dvm1=0 dvm2=0 dvm3=0 dvm4=0 dvm6=0 dvm7=0
Vdm1 inn g1 DC {{dvm1}}
Vdm2 inp g2 DC {{dvm2}}
Vdm3 n1 g3 DC {{dvm3}}
Vdm4 n1 g4 DC {{dvm4}}
Vdm6 n2 g6 DC {{dvm6}}
Vdm7 nb g7 DC {{dvm7}}
Ibias vdd nb DC {IBIAS}
XM8 nb nb vss vss {pdk.NFET} W={SIZES['M8'][0]} L={SIZES['M8'][1]} nf=1 m=1
XM5 nt nb vss vss {pdk.NFET} W={SIZES['M5'][0]} L={SIZES['M5'][1]} nf=1 m=1
XM1 n1 g1 nt vss {pdk.NFET} W={SIZES['M1'][0]} L={SIZES['M1'][1]} nf=1 m=1
XM2 n2 g2 nt vss {pdk.NFET} W={SIZES['M2'][0]} L={SIZES['M2'][1]} nf=1 m=1
XM3 n1 g3 vdd vdd {pdk.PFET} W={SIZES['M3'][0]} L={SIZES['M3'][1]} nf=1 m=1
XM4 n2 g4 vdd vdd {pdk.PFET} W={SIZES['M4'][0]} L={SIZES['M4'][1]} nf=1 m=1
XM6 out g6 vdd vdd {pdk.PFET} W={SIZES['M6'][0]} L={SIZES['M6'][1]} nf=1 m=1
XM7 out g7 vss vss {pdk.NFET} W={SIZES['M7'][0]} L={SIZES['M7'][1]} nf=1 m=1
CC_MILLER n2 out {CC}
.ends ota2s
"""

# Operating-point quantities printed by every bench: name -> (device, model, parameter)
_OP_DEVICES = {
    "gm1": ("xm1", pdk.NFET, "gm"), "gds1": ("xm1", pdk.NFET, "gds"),
    "gm2": ("xm2", pdk.NFET, "gm"), "gds2": ("xm2", pdk.NFET, "gds"),
    "gm3": ("xm3", pdk.PFET, "gm"), "gds3": ("xm3", pdk.PFET, "gds"),
    "gds4": ("xm4", pdk.PFET, "gds"),
    "gm6": ("xm6", pdk.PFET, "gm"), "gds6": ("xm6", pdk.PFET, "gds"),
    "gds7": ("xm7", pdk.NFET, "gds"),
    "id1": ("xm1", pdk.NFET, "id"), "id6": ("xm6", pdk.PFET, "id"),
}


def subckt_text() -> str:
    """SPICE text for the ``ota2s`` subcircuit."""
    return _OTA_SUBCKT


def _op_prints() -> str:
    lines = []
    for name, (dev, model, param) in _OP_DEVICES.items():
        lines.append(f"let {name} = @m.x1.{dev}.m{model}[{param}]")
        lines.append(f"print {name}")
    return "\n".join(lines)


def bench(corner: str = "tt", temp: float = 27.0, vdd: float = VDD_NOM,
          dvth: dict[str, float] | None = None, analysis: str = "ac") -> str:
    """Open-loop bench netlist.

    An inductor in the feedback path is a short at DC, so the loop is closed
    for the bias point (unity gain, output at VCM). At AC and noise
    frequencies the inductor is open and the loop is broken for measurement.
    ``dvth`` gives Vth offsets (V) per device name, for Monte Carlo runs.
    """
    dvth = dvth or {}
    params = " ".join(f"dvm{i}={dvth.get(f'M{i}', 0.0)}" for i in (1, 2, 3, 4, 6, 7))
    if analysis == "op":
        body = "op\nlet vout = v(out)\nprint vout\n" + _op_prints()
    elif analysis == "ac":
        body = "op\n" + _op_prints() + "\nac dec 20 1 1e9\nwrdata ac.txt vdb(out) vp(out)"
    elif analysis == "noise":
        body = ("op\n" + _op_prints()
                + "\nnoise v(out) Vinp dec 10 1 1e8\nsetplot noise1\nwrdata noise.txt inoise_spectrum")
    else:
        raise ValueError(f"unknown analysis {analysis!r}")
    return (
        "* two-stage op-amp testbench\n"
        ".option scale=1e-6\n"
        f".temp {temp}\n"
        + pdk.library_text(corner)
        + _OTA_SUBCKT
        + f"""
VDD vdd 0 {vdd}
Vinp inp 0 DC {VCM} AC 1
X1 inp inn out vdd 0 ota2s {params}
Lfb out inn 1e6
Cfb inn 0 1e6
CL out 0 {CLOAD}
.control
{body}
.endc
.end
"""
    )


@dataclass
class OpampResult:
    corner: str
    vdd: float
    temp: float
    dc_gain_db: float
    ugf_hz: float
    phase_margin_deg: float
    gm1: float
    gds1: float
    gm2: float
    gds2: float
    gm3: float
    gds3: float
    gds4: float
    gm6: float
    gds6: float
    gds7: float
    id1: float
    id6: float
    bode: np.ndarray | None = None  # columns: freq (Hz), |gain| (dB), phase (rad)

    @property
    def dc_gain(self) -> float:
        return 10 ** (self.dc_gain_db / 20)


def ugf_and_pm(freq: np.ndarray, mag_db: np.ndarray, phase_rad: np.ndarray) -> tuple[float, float]:
    """Unity-gain frequency (Hz) and phase margin (deg) from an AC sweep.

    Interpolates on a log-frequency axis. The phase is unwrapped first, so
    the margin stays correct below -180 degrees.
    """
    unwrapped = np.degrees(np.unwrap(phase_rad))
    crossings = np.where(np.diff(np.sign(mag_db)) != 0)[0]
    if crossings.size == 0:
        raise ValueError("gain never crosses 0 dB inside the sweep")
    i = crossings[0]
    logf = np.log10(freq)
    frac = mag_db[i] / (mag_db[i] - mag_db[i + 1])
    log_ugf = logf[i] + frac * (logf[i + 1] - logf[i])
    phase_at_ugf = unwrapped[i] + frac * (unwrapped[i + 1] - unwrapped[i])
    return 10 ** log_ugf, 180.0 + phase_at_ugf


def characterize(corner: str = "tt", vdd: float = VDD_NOM, temp: float = 27.0) -> OpampResult:
    """Run the AC bench and return gain, UGF, phase margin and bias values."""
    res = simulate(bench(corner, temp, vdd, analysis="ac"), tables=("ac.txt",))
    table = res.tables["ac.txt"]  # wrdata columns: freq, vdb(out), freq, vp(out)
    freq, mag_db, phase = table[:, 0], table[:, 1], table[:, 3]
    ugf, pm = ugf_and_pm(freq, mag_db, phase)
    return OpampResult(
        corner=corner,
        vdd=vdd,
        temp=temp,
        dc_gain_db=float(mag_db[0]),
        ugf_hz=float(ugf),
        phase_margin_deg=float(pm),
        gm1=res["gm1"], gds1=res["gds1"], gm2=res["gm2"], gds2=res["gds2"],
        gm3=res["gm3"], gds3=res["gds3"], gds4=res["gds4"],
        gm6=res["gm6"], gds6=res["gds6"], gds7=res["gds7"],
        id1=res["id1"], id6=res["id6"],
        bode=np.column_stack([freq, mag_db, phase]),
    )


@dataclass
class NoiseResult:
    freq: np.ndarray
    density: np.ndarray  # input-referred, V/sqrt(Hz)

    def at(self, f: float) -> float:
        return float(np.interp(np.log10(f), np.log10(self.freq), self.density))

    def integrated_rms(self, f_lo: float, f_hi: float) -> float:
        mask = (self.freq >= f_lo) & (self.freq <= f_hi)
        return float(np.sqrt(np.trapezoid(self.density[mask] ** 2, self.freq[mask])))


def input_noise(corner: str = "tt", temp: float = 27.0) -> tuple[NoiseResult, dict[str, float]]:
    """Input-referred noise over 10 Hz to 100 MHz, plus the operating point."""
    res = simulate(bench(corner, temp, analysis="noise"), tables=("noise.txt",))
    table = res.tables["noise.txt"]  # columns: freq, inoise_spectrum
    op = {name: res[name] for name in _OP_DEVICES}
    return NoiseResult(freq=table[:, 0], density=table[:, 1]), op


def offset_sample(dvth: dict[str, float], corner: str = "tt", temp: float = 27.0) -> float:
    """Input-referred offset (V) for one set of Vth mismatches.

    The bench holds unity gain at DC through the feedback inductor, so the
    output sits at VCM plus the input-referred offset.
    """
    res = simulate(bench(corner, temp, dvth=dvth, analysis="op"))
    return res["vout"] - VCM
