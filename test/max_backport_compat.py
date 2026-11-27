"""Keep the shared test floor while adapting its startup stub to Crew 0.13.1."""

import pytest


@pytest.fixture(autouse=True, scope="session")
def _no_engine_install_at_gateway_start():
    from importlib.metadata import version

    from kiro_crew.agent_sdk import kas_bundle

    assert version("kirocrew") == "0.13.1+max.4"
    assert not hasattr(kas_bundle, "ensure_engine_at_startup")
    yield
