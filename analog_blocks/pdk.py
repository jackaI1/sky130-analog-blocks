"""Find the SkyWater Sky130 SPICE models and build the library includes.

The models come from the public PDK repository
google/skywater-pdk-libs-sky130_fd_pr. ``scripts/fetch_pdk.sh`` downloads
only the device folders this project uses. The location is read from the
``SKY130_PDK_ROOT`` environment variable, with a default under ~/.cache.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

CORNERS = ("tt", "ff", "ss", "sf", "fs")
PDK_ENV_VAR = "SKY130_PDK_ROOT"
DEFAULT_PDK_ROOT = Path.home() / ".cache" / "sky130-analog-blocks" / "pdk-src"

# Pinned revision of google/skywater-pdk-libs-sky130_fd_pr used for all results.
PDK_COMMIT = "f62031a1be9aefe902d6d54cddd6f59b57627436"

NFET = "sky130_fd_pr__nfet_01v8"
PFET = "sky130_fd_pr__pfet_01v8"
PNP = "sky130_fd_pr__pnp_05v5_W3p40L3p40"


def pdk_root() -> Path:
    """Return the PDK checkout directory (the one that contains ``cells/``)."""
    return Path(os.environ.get(PDK_ENV_VAR, DEFAULT_PDK_ROOT)).expanduser()


def _required_files(root: Path, corner: str) -> list[Path]:
    cells = root / "cells"
    return [
        cells / "nfet_01v8" / f"sky130_fd_pr__nfet_01v8__{corner}.corner.spice",
        cells / "pfet_01v8" / f"sky130_fd_pr__pfet_01v8__{corner}.corner.spice",
        cells / "nfet_01v8" / "sky130_fd_pr__nfet_01v8__mismatch.corner.spice",
        cells / "pfet_01v8" / "sky130_fd_pr__pfet_01v8__mismatch.corner.spice",
        cells / "pnp_05v5" / f"{PNP}.model.spice",
        root / "models" / "parameters" / "invariant.spice",
        root / "models" / "parameters" / "lod.spice",
        root / "models" / "corners" / corner / "nonfet.spice",
    ]


def is_available(root: Path | None = None, corner: str = "tt") -> bool:
    """True when every model file this project needs is on disk."""
    root = root or pdk_root()
    return all(path.is_file() for path in _required_files(root, corner))


_INCLUDE_RE = re.compile(r'^\s*\.include\s+"?([^"\s]+)"?\s*$', re.IGNORECASE)


def _inline(path: Path, depth: int = 0) -> str:
    """Return the text of ``path`` with its own ``.include`` lines inlined.

    The PDK's corner files include their binned model files by a path
    relative to themselves. ngspice resolves includes against the working
    directory, so the includes are inlined here instead.
    """
    if depth > 8:
        raise RecursionError(f"include depth exceeded at {path}")
    out: list[str] = [f"* ---- begin {path.name}"]
    for line in path.read_text().splitlines():
        match = _INCLUDE_RE.match(line)
        if match:
            target = (path.parent / match.group(1)).resolve()
            out.append(_inline(target, depth + 1))
        else:
            out.append(line)
    out.append(f"* ---- end {path.name}")
    return "\n".join(out) + "\n"


def library_text(corner: str = "tt", mismatch: bool = True, root: Path | None = None) -> str:
    """Return the SPICE model text for one process corner, with includes inlined.

    ``mismatch`` also loads the PDK's mismatch-coefficient files, which
    define the Vth-mismatch coefficients used by ``montecarlo.py``.
    """
    if corner not in CORNERS:
        raise ValueError(f"unknown corner {corner!r}; use one of {CORNERS}")
    root = root or pdk_root()
    files = _required_files(root, corner)
    if not mismatch:
        files = [f for f in files if "mismatch" not in f.name]
    return "".join(_inline(path.resolve()) for path in files)


def mismatch_coefficient_mV_um(root: Path | None = None) -> float:
    """Pelgrom-style Vth mismatch coefficient A_VT of the NMOS, in mV*um.

    The PDK writes sigma(Vth) = A_VT / sqrt(W * L) with W and L in um.
    The value is read from the PDK file instead of being typed in here.
    """
    root = root or pdk_root()
    path = root / "cells" / "nfet_01v8" / "sky130_fd_pr__nfet_01v8__mismatch.corner.spice"
    pattern = re.compile(rf"{NFET}__vth0_slope1\s*=\s*([-+0-9.eE]+)")
    match = pattern.search(path.read_text())
    if match is None:
        raise ValueError(f"vth0_slope1 not found in {path}")
    return float(match.group(1)) * 1e3
