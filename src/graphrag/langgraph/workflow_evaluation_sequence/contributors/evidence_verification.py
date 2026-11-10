"""Ragas-inspired, Ragas-independent interface to a locally loaded HHEM model.

One operation: evaluate whether the supplied premise supports the supplied hypothesis.
The caller controls evidence selection, atomicity, assertion/criterion distinction,
validation policy, scheduling, aggregation, and workflow decisions.

Requires `transformers` and a trusted, locally available HHEM checkpoint.
`trust_remote_code=True` executes code stored in the supplied local model directory.
"""
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Protocol, Sequence


class EvaluationStatus(str, Enum):
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class EvaluationResult:
    status: EvaluationStatus
    score: float | None = None
    error: str | None = None


class HHEMClassifier(Protocol):
    def predict(self, pairs: list[tuple[str, str]]): ...


class LocalHHEMEvaluator:
    """Single shared HHEM inference adapter, without any orchestration.

    `premise` is only the evidence (or verified statements) selected by the caller.
    `hypothesis` is one atomic assertion or a proposed criterion conclusion.
    A result's `score` is the classifier's support score, not proof of factual
    truth, evidence completeness, or criterion satisfaction.
    """

    def __init__(
        self,
        *,
        model_dir: str | Path | None = None,
        foundation_dir: str | Path | None = None,
        device: str = "cpu",
        batch_size: int = 10,
        classifier: HHEMClassifier | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.batch_size = batch_size
        self._lock = Lock()
        if classifier is not None:
            self._classifier = classifier
            return
        if model_dir is None:
            raise ValueError("model_dir is required unless classifier is provided")
        root = Path(model_dir).expanduser().resolve()
        foundation = (
            Path(foundation_dir).expanduser().resolve()
            if foundation_dir is not None
            else root / "foundation"
        )
        if not root.is_dir():
            raise NotADirectoryError(f"HHEM model directory does not exist: {root}")
        if not foundation.is_dir():
            raise NotADirectoryError(f"HHEM foundation directory does not exist: {foundation}")

        from transformers import AutoConfig, AutoModelForSequenceClassification

        config = AutoConfig.from_pretrained(
            str(root), local_files_only=True, trust_remote_code=True
        )
        config.foundation = str(foundation)
        model = AutoModelForSequenceClassification.from_pretrained(
            str(root), config=config, local_files_only=True, trust_remote_code=True
        )
        self._classifier = model.to(device)
        self._classifier.eval()

    def _predict(self, pairs: Sequence[tuple[str, str]]) -> tuple[float, ...]:
        if not pairs:
            return ()
        values: list[float] = []
        # HHEM models are often not thread-safe when predict is called concurrently.
        with self._lock:
            for start in range(0, len(pairs), self.batch_size):
                batch = list(pairs[start : start + self.batch_size])
                output = self._classifier.predict(batch)
                if hasattr(output, "detach"):
                    output = output.detach().cpu()
                if hasattr(output, "tolist"):
                    output = output.tolist()
                if isinstance(output, (int, float)):
                    output = [output]
                if len(output) != len(batch):
                    raise ValueError("HHEM returned an unexpected number of scores")
                for score in output:
                    if isinstance(score, (tuple, list)):
                        if len(score) != 1:
                            raise ValueError("Expected one support score per premise/hypothesis pair")
                        score = score[0]
                    value = float(score)
                    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                        raise ValueError(f"Invalid HHEM support score: {value}")
                    values.append(value)
        return tuple(values)

    async def evaluate(self, *, premise: str, hypothesis: str) -> EvaluationResult:
        """Evaluate exactly one supplied premise/hypothesis pair."""
        if not premise.strip() or not hypothesis.strip():
            return EvaluationResult(
                status=EvaluationStatus.SKIPPED,
                error="Both premise and hypothesis must be nonempty",
            )
        try:
            (score,) = await asyncio.to_thread(self._predict, [(premise, hypothesis)])
            return EvaluationResult(status=EvaluationStatus.COMPLETED, score=score)
        except Exception as exc:
            return EvaluationResult(
                status=EvaluationStatus.FAILED,
                error=f"{type(exc).__name__}: {exc}",
            )

    async def evaluate_batch(
        self, *, pairs: Sequence[tuple[str, str]]
    ) -> tuple[EvaluationResult, ...]:
        """Optional inference batching only; caller chooses and groups the pairs.

        Malformed inputs are skipped individually. Inference failures mark the
        attempted batch as failed; the adapter does not retry or route work.
        """
        results: list[EvaluationResult | None] = [None] * len(pairs)
        valid: list[tuple[str, str]] = []
        indices: list[int] = []
        for index, (premise, hypothesis) in enumerate(pairs):
            if not premise.strip() or not hypothesis.strip():
                results[index] = EvaluationResult(
                    status=EvaluationStatus.SKIPPED,
                    error="Both premise and hypothesis must be nonempty",
                )
            else:
                valid.append((premise, hypothesis))
                indices.append(index)
        if valid:
            try:
                scores = await asyncio.to_thread(self._predict, valid)
                for index, score in zip(indices, scores, strict=True):
                    results[index] = EvaluationResult(
                        status=EvaluationStatus.COMPLETED, score=score
                    )
            except Exception as exc:
                for index in indices:
                    results[index] = EvaluationResult(
                        status=EvaluationStatus.FAILED,
                        error=f"{type(exc).__name__}: {exc}",
                    )
        return tuple(result for result in results if result is not None)


async def example_evidence_verification() -> None:
    evaluator = LocalHHEMEvaluator(
        model_dir="/models/hhem",
        foundation_dir="/models/flan-t5-base",
        device="cpu",
    )
    # Atomic assertion: caller supplies only its relevant evidence.
    assertion = await evaluator.evaluate(
        premise="Publication P123 lists Alice Smith as an author.",
        hypothesis="Alice Smith authored publication P123.",
    )
    print("Atomic assertion:", assertion)

    # Criterion-level conclusion: caller supplies only verified statements
    # relevant to that conclusion. No re-retrieval or aggregation here.
    criterion = await evaluator.evaluate(
        premise=(
            "Alice Smith authored P123.\n"
            "P123 concerns agricultural robotics.\n"
            "P123 was published in 2021."
        ),
        hypothesis="Alice Smith authored an agricultural robotics publication after 2020.",
    )
    print("Criterion conclusion:", criterion)
