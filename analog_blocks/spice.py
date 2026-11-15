"""Run ngspice in batch mode and read the results back into Python.

Every netlist runs in its own temporary folder, which is deleted afterwards.
Scalar results come from ``print`` lines on stdout. Waveforms and sweeps
come from ``wrdata`` text files, which are loaded as numpy arrays.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

NGSPICE = "ngspice"
_PRINT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([-+]?\d[\d.]*(?:[eE][-+]?\d+)?)\s*$")


class SpiceError(RuntimeError):
    """ngspice failed, or a result the netlist should have produced is missing."""


@dataclass
class SpiceResult:
    values: dict[str, float] = field(default_factory=dict)
    tables: dict[str, np.ndarray] = field(default_factory=dict)

    def __getitem__(self, name: str) -> float:
        try:
            return self.values[name]
        except KeyError as exc:
            raise SpiceError(f"netlist did not print {name!r}") from exc


def ngspice_available() -> bool:
    return shutil.which(NGSPICE) is not None


def simulate(netlist: str, tables: tuple[str, ...] = (), timeout: float = 600.0) -> SpiceResult:
    """Run ``netlist`` and return the printed values and requested tables.

    ``tables`` lists the ``wrdata`` file names the netlist writes. Each file
    is parsed into a 2-D numpy array, one row per data point.
    """
    if not ngspice_available():
        raise SpiceError("ngspice is not on PATH; install it first (brew install ngspice)")
    workdir = Path(tempfile.mkdtemp(prefix="sky130-ngspice-"))
    try:
        cir = workdir / "netlist.cir"
        cir.write_text(netlist)
        proc = subprocess.run(
            [NGSPICE, "-b", str(cir)],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        stdout = proc.stdout
        result = SpiceResult()
        for line in stdout.splitlines():
            match = _PRINT_RE.match(line.strip())
            if match:
                result.values[match.group(1)] = float(match.group(2))
        for name in tables:
            path = workdir / name
            if not path.exists():
                tail = "\n".join(stdout.splitlines()[-15:])
                raise SpiceError(f"ngspice did not write {name}; last output:\n{tail}")
            result.tables[name] = np.loadtxt(path, ndmin=2)
        if proc.returncode != 0:
            raise SpiceError(f"ngspice exited with {proc.returncode}")
        return result
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
