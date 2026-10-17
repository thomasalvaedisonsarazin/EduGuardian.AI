"""OpenAI chat-completions client with hard cost controls.

Guarantees for every call made through :class:`LLMClient`:

a. The LLM must be enabled (``LLM_ENABLED``) and an API key configured, else
   :class:`LLMUnavailable` is raised so callers fall back to deterministic templates.
b. Monthly budget: the school's spend this calendar month (sum of ``AgentRun.cost_usd``) plus
   what this client already spent plus the *estimated* cost of the call must stay within
   ``LLM_MONTHLY_BUDGET_USD``, else :class:`~app.exceptions.BudgetExceededError`.
c. Cost is computed from the token usage the API reports with the per-million-token prices in
   ``LLM_INPUT_PRICE_PER_MTOK`` / ``LLM_OUTPUT_PRICE_PER_MTOK``.
d. Requests time out after ``LLM_TIMEOUT_SECONDS`` and are retried ``LLM_MAX_RETRIES`` time(s).
e. The full request is checked by :func:`app.llm.privacy.assert_no_pii` before it is sent.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.exceptions import BudgetExceededError
from app.llm.privacy import assert_no_pii
from app.models import AgentRun

logger = logging.getLogger(__name__)

__all__ = [
    "JsonLLM",
    "LLMClient",
    "LLMResponseError",
    "LLMResult",
    "LLMUnavailable",
    "LLMUsage",
    "estimate_tokens",
    "month_spend",
]

MILLION = Decimal(1_000_000)
COST_PLACES = Decimal("0.000001")


class LLMUnavailable(RuntimeError):  # noqa: N818 - name is part of the module contract
    """LLM disabled, not configured, or the API call failed (callers fall back)."""


class LLMResponseError(RuntimeError):
    """The API answered (and was billed) but the content is not valid JSON."""

    def __init__(self, message: str, usage: LLMUsage | None = None) -> None:
        super().__init__(message)
        self.usage = usage


@dataclass(frozen=True)
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: Decimal = Decimal(0)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class LLMResult:
    content: dict[str, Any]
    usage: LLMUsage
    model: str
    raw_text: str = field(default="", repr=False)


class JsonLLM(Protocol):
    """What the agents need from an LLM: one JSON-in/JSON-out call (easy to fake in tests)."""

    model: str

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "response",
        forbidden_terms: Iterable[str] = (),
        max_output_tokens: int | None = None,
    ) -> LLMResult: ...


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 characters per token) used for the pre-call budget check."""
    return max(1, len(text) // 4 + 1)


def month_spend(db: Session, school_id: int, now: datetime | None = None) -> Decimal:
    """Sum of ``AgentRun.cost_usd`` for the school in the current calendar month (UTC)."""
    now = now or datetime.now(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = db.scalar(
        select(func.coalesce(func.sum(AgentRun.cost_usd), 0)).where(
            AgentRun.school_id == school_id, AgentRun.created_at >= start
        )
    )
    return Decimal(str(total or 0))


class LLMClient:
    """Budget-capped OpenAI client for one school (one instance per agent run)."""

    def __init__(
        self,
        db: Session,
        school_id: int,
        *,
        config: Settings | None = None,
        sdk_client: Any | None = None,
    ) -> None:
        self.db = db
        self.school_id = school_id
        self.config = config or settings
        self.model = self.config.OPENAI_MODEL
        self._sdk = sdk_client
        self.spent = Decimal(0)  # spent by this client (not yet persisted on the run)
        self.calls = 0

    # -- cost helpers -------------------------------------------------------------------
    def cost_for(self, prompt_tokens: int, completion_tokens: int) -> Decimal:
        price_in = Decimal(str(self.config.LLM_INPUT_PRICE_PER_MTOK))
        price_out = Decimal(str(self.config.LLM_OUTPUT_PRICE_PER_MTOK))
        cost = Decimal(prompt_tokens) * price_in + Decimal(completion_tokens) * price_out
        cost = cost / MILLION
        return cost.quantize(COST_PLACES, rounding=ROUND_HALF_UP)

    def remaining_budget(self) -> Decimal:
        budget = Decimal(str(self.config.LLM_MONTHLY_BUDGET_USD))
        return budget - month_spend(self.db, self.school_id) - self.spent

    def _check_available(self) -> None:
        if not self.config.LLM_ENABLED:
            raise LLMUnavailable("LLM is disabled (LLM_ENABLED=false)")
        if not self.config.OPENAI_API_KEY:
            raise LLMUnavailable("OPENAI_API_KEY is not configured")

    def _check_budget(self, estimated: Decimal) -> None:
        remaining = self.remaining_budget()
        if estimated > remaining:
            logger.warning(
                "LLM budget exceeded for school=%s: estimated=%s remaining=%s",
                self.school_id,
                estimated,
                remaining,
            )
            raise BudgetExceededError(
                f"Monthly LLM budget of ${self.config.LLM_MONTHLY_BUDGET_USD:.2f} would be "
                "exceeded; using deterministic templates instead"
            )

    def _sdk_client(self) -> Any:
        if self._sdk is None:
            from openai import OpenAI  # imported lazily: tests never need the real SDK

            self._sdk = OpenAI(
                api_key=self.config.OPENAI_API_KEY,
                timeout=self.config.LLM_TIMEOUT_SECONDS,
                max_retries=self.config.LLM_MAX_RETRIES,
            )
        return self._sdk

    # -- the call -------------------------------------------------------------------------
    def complete_json(
        self,
        *,
        system: str,
        user: str,
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "response",
        forbidden_terms: Iterable[str] = (),
        max_output_tokens: int | None = None,
    ) -> LLMResult:
        self._check_available()
        max_out = max_output_tokens or self.config.LLM_MAX_OUTPUT_TOKENS
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        assert_no_pii(messages, forbidden_terms)
        estimated = self.cost_for(estimate_tokens(system + user), max_out)
        self._check_budget(estimated)

        response_format: dict[str, Any]
        if json_schema is not None:
            response_format = {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": json_schema, "strict": True},
            }
        else:
            response_format = {"type": "json_object"}

        try:
            completion = self._sdk_client().chat.completions.create(
                model=self.model,
                messages=messages,
                response_format=response_format,
                temperature=0.2,
                max_completion_tokens=max_out,
            )
        except Exception as exc:  # network, auth, rate limit, timeout (after retries)
            logger.warning("LLM call failed (%s): %s", type(exc).__name__, exc)
            raise LLMUnavailable(f"LLM request failed: {type(exc).__name__}") from exc

        usage_obj = getattr(completion, "usage", None)
        prompt_tokens = int(getattr(usage_obj, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage_obj, "completion_tokens", 0) or 0)
        usage = LLMUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=self.cost_for(prompt_tokens, completion_tokens),
        )
        self.spent += usage.cost_usd
        self.calls += 1

        text = ""
        try:
            text = completion.choices[0].message.content or ""
            content = json.loads(text)
        except (AttributeError, IndexError, json.JSONDecodeError) as exc:
            raise LLMResponseError("LLM returned invalid JSON", usage) from exc
        if not isinstance(content, dict):
            raise LLMResponseError("LLM returned JSON that is not an object", usage)
        logger.info(
            "LLM call school=%s model=%s tokens=%d cost=%s",
            self.school_id,
            self.model,
            usage.total_tokens,
            usage.cost_usd,
        )
        return LLMResult(content=content, usage=usage, model=self.model, raw_text=text)
