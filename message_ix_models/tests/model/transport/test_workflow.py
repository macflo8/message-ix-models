import pytest

from message_ix_models.model.transport.workflow import generate


@pytest.mark.parametrize(
    "base_scenario",
    (
        "auto",
        pytest.param(
            "bare",
            marks=pytest.mark.skip(reason="Slow; generates copies of the bare RES"),
        ),
    ),
)
def test_generate(test_context, base_scenario) -> None:
    # Workflow is generated
    wf = generate(test_context, base_scenario=base_scenario)

    # Workflow contains some expected steps
    assert "EDITS-HA reported" in wf
    assert "LED-SSP1 reported" in wf
