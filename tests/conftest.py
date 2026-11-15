"""Shared test setup.

Simulator tests carry the ``sim`` marker. They skip when ngspice or the Sky130
models are missing. With ANALOG_BLOCKS_REQUIRE_SIM=1 (set in CI) a missing
tool stops the whole run instead, so CI cannot pass without simulating.
"""

import os

import pytest

from analog_blocks import pdk
from analog_blocks.spice import ngspice_available

REQUIRE_ENV = "ANALOG_BLOCKS_REQUIRE_SIM"


def _sim_ready() -> bool:
    return ngspice_available() and pdk.is_available()


def pytest_sessionstart(session):
    if os.environ.get(REQUIRE_ENV) == "1" and not _sim_ready():
        pytest.exit("ngspice or the Sky130 PDK is missing, and ANALOG_BLOCKS_REQUIRE_SIM=1", returncode=2)


def pytest_collection_modifyitems(config, items):
    if _sim_ready():
        return
    skip = pytest.mark.skip(reason="needs ngspice and the Sky130 PDK (run scripts/fetch_pdk.sh)")
    for item in items:
        if "sim" in item.keywords:
            item.add_marker(skip)
