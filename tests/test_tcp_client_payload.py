from test_client import PAMG_PHASES, build_telemetry_payload
import pytest


def test_benchmark_telemetry_supplies_documented_xy_inputs():
    payload = build_telemetry_payload(PAMG_PHASES[0])

    assert payload["x"] == pytest.approx(0.075)
    assert payload["y"] == pytest.approx(0.1)
    assert payload["valence"] == PAMG_PHASES[0]["valence"]
    assert payload["arousal"] == PAMG_PHASES[0]["arousal"]
