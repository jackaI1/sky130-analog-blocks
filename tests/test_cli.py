import pytest

from analog_blocks import cli

pytestmark = pytest.mark.sim


def test_quick_run_writes_summary_and_plots(tmp_path):
    code = cli.run(tmp_path, quick=True)
    assert code == 0
    assert (tmp_path / "summary.md").exists()
    assert (tmp_path / "summary.json").exists()
    for name in ("opamp_bode.png", "opamp_noise.png", "bandgap_vs_temp.png", "vco_tuning.png", "mc_offset.png"):
        assert (tmp_path / name).stat().st_size > 1000
    text = (tmp_path / "summary.md").read_text()
    assert "Checks against hand calculations" in text
    assert "Skills" not in text
