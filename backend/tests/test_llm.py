"""LLM layer: PII guard (acceptance criterion: no student names in any LLM request) and the
budget-capped client (availability, budget, cost, invalid JSON)."""

import json
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.config import Settings
from app.exceptions import BudgetExceededError
from app.llm.client import LLMClient, LLMResponseError, LLMUnavailable, month_spend
from app.llm.privacy import PIIViolationError, assert_no_pii, forbidden_terms
from app.models import AgentRun, AgentRunKind, AgentRunStatus, School


class FakeCompletions:
    def __init__(self, content: str, prompt_tokens: int = 1000, completion_tokens: int = 500):
        self.content = content
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))],
            usage=SimpleNamespace(
                prompt_tokens=self.prompt_tokens, completion_tokens=self.completion_tokens
            ),
        )


def fake_sdk(completions: FakeCompletions) -> SimpleNamespace:
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def cfg(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "LLM_ENABLED": True,
        "OPENAI_API_KEY": "sk-test",
        "LLM_MONTHLY_BUDGET_USD": 15.0,
        "LLM_INPUT_PRICE_PER_MTOK": 0.15,
        "LLM_OUTPUT_PRICE_PER_MTOK": 0.60,
        "LLM_MAX_OUTPUT_TOKENS": 1000,
    }
    base.update(overrides)
    return Settings(**base)


@pytest.fixture()
def school(db: Session) -> School:
    s = School(name="LLM School", code="LLM01")
    db.add(s)
    db.flush()
    return s


# --- privacy -------------------------------------------------------------------------------


def test_forbidden_terms_cleans_values() -> None:
    terms = forbidden_terms(["  Asha   Rao ", None, "X"], ["GPS1001", ""])
    assert terms == {"Asha Rao", "GPS1001"}


def test_assert_no_pii_detects_names_and_admission_numbers_anywhere() -> None:
    forbidden = {"Asha Rao", "GPS1001"}
    assert_no_pii({"students": [{"pseudo_id": "S-0001", "marks": "20"}]}, forbidden)
    with pytest.raises(PIIViolationError):
        assert_no_pii({"deep": [{"note": "asha   RAO did well"}]}, forbidden)
    with pytest.raises(PIIViolationError):
        assert_no_pii([{"role": "user", "content": "id GPS1001"}], forbidden)
    # not glued to other word characters
    assert_no_pii("Asha Raoul and GPS10011", forbidden)


def test_assert_no_pii_error_does_not_echo_the_value() -> None:
    with pytest.raises(PIIViolationError) as info:
        assert_no_pii("Asha Rao", {"Asha Rao"})
    assert "Asha" not in str(info.value)


# --- client --------------------------------------------------------------------------------


def test_client_unavailable_when_disabled_or_no_key(db: Session, school: School) -> None:
    for config in (cfg(LLM_ENABLED=False), cfg(OPENAI_API_KEY="")):
        client = LLMClient(db, school.id, config=config, sdk_client=fake_sdk(FakeCompletions("{}")))
        with pytest.raises(LLMUnavailable):
            client.complete_json(system="s", user="u")


def test_client_computes_cost_from_usage(db: Session, school: School) -> None:
    completions = FakeCompletions(json.dumps({"ok": True}), 1_000_000, 1_000_000)
    client = LLMClient(
        db, school.id, config=cfg(LLM_MAX_OUTPUT_TOKENS=10), sdk_client=fake_sdk(completions)
    )
    result = client.complete_json(
        system="s", user="u", json_schema={"type": "object"}, schema_name="x"
    )
    assert result.content == {"ok": True}
    assert result.usage.total_tokens == 2_000_000
    assert result.usage.cost_usd == Decimal("0.750000")
    assert client.spent == Decimal("0.750000")
    sent = completions.calls[0]
    assert sent["response_format"]["type"] == "json_schema"
    assert sent["response_format"]["json_schema"]["strict"] is True
    assert sent["model"] == "gpt-4o-mini"


def test_client_blocks_pii_before_sending(db: Session, school: School) -> None:
    completions = FakeCompletions("{}")
    client = LLMClient(db, school.id, config=cfg(), sdk_client=fake_sdk(completions))
    with pytest.raises(PIIViolationError):
        client.complete_json(system="s", user="Asha Rao", forbidden_terms={"Asha Rao"})
    assert completions.calls == []


def test_client_enforces_monthly_budget(db: Session, school: School) -> None:
    db.add(
        AgentRun(
            school_id=school.id,
            kind=AgentRunKind.full_analysis,
            status=AgentRunStatus.done,
            cost_usd=Decimal("0.9999"),
        )
    )
    db.flush()
    assert month_spend(db, school.id) == Decimal("0.9999")
    completions = FakeCompletions("{}")
    client = LLMClient(
        db, school.id, config=cfg(LLM_MONTHLY_BUDGET_USD=1.0), sdk_client=fake_sdk(completions)
    )
    with pytest.raises(BudgetExceededError):
        client.complete_json(system="s" * 4000, user="u")
    assert completions.calls == []


def test_client_invalid_json_reports_usage(db: Session, school: School) -> None:
    client = LLMClient(
        db, school.id, config=cfg(), sdk_client=fake_sdk(FakeCompletions("not json"))
    )
    with pytest.raises(LLMResponseError) as info:
        client.complete_json(system="s", user="u")
    assert info.value.usage is not None and info.value.usage.total_tokens == 1500


def test_client_wraps_sdk_errors(db: Session, school: School) -> None:
    class Boom:
        def create(self, **_: Any) -> None:
            raise TimeoutError("slow")

    client = LLMClient(
        db,
        school.id,
        config=cfg(),
        sdk_client=SimpleNamespace(chat=SimpleNamespace(completions=Boom())),
    )
    with pytest.raises(LLMUnavailable):
        client.complete_json(system="s", user="u")
