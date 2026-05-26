from pathlib import Path

import yaml

from expertview.evidence.models import Incident

_REPO_ROOT = Path(__file__).resolve().parents[2]
_INCIDENT_PATH = _REPO_ROOT / "data" / "incidents" / "cnc_out_of_tolerance.yaml"


def test_cnc_out_of_tolerance_yaml_validates_against_incident_schema() -> None:
    raw_incident = yaml.safe_load(_INCIDENT_PATH.read_text(encoding="utf-8"))

    incident = Incident.model_validate(raw_incident)

    assert incident.id == "cnc-out-of-tolerance-2026-05-24-shift-3"
    assert incident.observed_at.isoformat() == "2026-05-24T22:40:00-05:00"
    assert incident.observed_at.hour == 22
    assert "cnc-line-2" in incident.affected_assets
    assert "cnc-line-2-cnc-04" in incident.affected_assets
    assert "spindle-04" in incident.affected_assets
    assert "hydraulic-cylinder-hc-l2-17" in incident.affected_assets
    assert any("out-of-tolerance" in symptom.lower() for symptom in incident.symptoms)
