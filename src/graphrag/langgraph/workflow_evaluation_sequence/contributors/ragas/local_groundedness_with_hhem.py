"""Local HHEM groundedness evaluation for pre-atomic GraphRAG assertions.

Unlike Ragas collections.ResponseGroundedness (two generative LLM judges), this
uses one local Vectara HHEM entailment classifier. It deliberately does NOT
extract claims: ``response`` must be one already-atomic assertion. For many
assertions, use ``score_assertions`` to batch inference over a shared context.

The resulting score is not numerically equivalent to Ragas's two-judge metric:
Ragas joins the evidence contexts, asks two separate LLM judges to rate the
whole response 0/1/2 (unsupported/partially/fully supported), and averages
both ratings after dividing by 2. This replacement returns HHEM's continuous
support score in [0, 1], not a fabricated 0/1/2 judgment. The optional
threshold is used only for a separate binary ``grounded`` verdict.

Because AEDR already supplies atomic assertions, neither a claim-extraction
LLM nor Ragas's two generative judges is invoked.

Only locally available model artifacts are loaded. The Vectara HHEM checkpoint
must include its trusted custom model Python code; Transformers executes that
local code when ``trust_remote_code=True``. Inspect those files before use.

Example (Ragas 0.4 collections result interface)::

    metric = LocalGroundednessWithHHEM(
        model_dir="/models/hhem",
        foundation_dir="/models/flan-t5-base",
        device="cpu",
        batch_size=10,
    )
    result = await metric.ascore(
        response="Paris is the capital of France.",  # ONE atomic assertion
        retrieved_contexts=["Paris is the capital of France."],
    )
    print(result.value)

    checks = metric.score_assertions(
        assertions=["Paris is in France.", "Paris is in Germany."],
        retrieved_contexts=["Paris is the capital of France."],
    )
    for check in checks:
        print(check.assertion, check.hhem_score, check.grounded)

Dependencies: ragas (0.4 collections MetricResult), transformers, torch, and
model-specific packages such as sentencepiece. No LLM is required.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Sequence

from ragas.metrics.result import MetricResult


@dataclass(frozen=True)
class AssertionGroundedness:
    """HHEM score and thresholded decision for one atomic assertion."""

    assertion: str
    hhem_score: float
    grounded: bool


class LocalGroundednessWithHHEM:
    """Drop-in ``score``/``ascore`` surface for a Ragas collections contributor.

    This is intentionally NOT a subclass of the legacy FaithfulnesswithHHEM or
    of collections.ResponseGroundedness: their LLM-dependent evaluation paths
    would reintroduce extraction or generative judging.

    ``threshold`` controls the binary groundedness verdict. Model scores can be
    inspected with ``score_assertions``; tune the threshold using labeled AEDR
    assertions rather than assuming 0.5 is optimal in your domain.
    """

    def __init__(
        self,
        *,
        model_dir: str | Path,
        foundation_dir: str | Path | None = None,
        device: str = "cpu",
        batch_size: int = 10,
        threshold: float = 0.5,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")

        model_dir = Path(model_dir).expanduser().resolve()
        if not model_dir.is_dir():
            raise NotADirectoryError(f"HHEM model directory does not exist: {model_dir}")
        foundation_dir = (
            Path(foundation_dir).expanduser().resolve()
            if foundation_dir is not None
            else model_dir / "foundation"
        )
        if not foundation_dir.is_dir():
            raise NotADirectoryError(
                f"FLAN-T5 foundation directory does not exist: {foundation_dir}"
            )

        from transformers import AutoConfig, AutoModelForSequenceClassification

        config = AutoConfig.from_pretrained(
            str(model_dir), local_files_only=True, trust_remote_code=True
        )
        # Match the local override used by local_faithfulness_with_hhem.py.
        # Vectara's remote-code constructor reads this path to load its base
        # config/tokenizer; its trained weights are in the HHEM checkpoint.
        config.foundation = str(foundation_dir)
        self.nli_classifier = AutoModelForSequenceClassification.from_pretrained(
            str(model_dir),
            config=config,
            local_files_only=True,
            trust_remote_code=True,
        )
        self.nli_classifier.to(device)
        self.nli_classifier.eval()
        self.device = device
        self.batch_size = batch_size
        self.threshold = threshold
        self._inference_lock = Lock()

    def score_assertions(
        self,
        *,
        assertions: Sequence[str],
        retrieved_contexts: Sequence[str],
    ) -> list[AssertionGroundedness]:
        """Evaluate assertions against the same combined evidence context.

        The model's ``predict`` method is used just as in Ragas's legacy
        FaithfulnesswithHHEM. It returns a scalar support score per pair.
        We preserve raw scores and threshold them instead of calling round().
        """
        if not assertions:
            raise ValueError("assertions must contain at least one atomic assertion")
        if any(not isinstance(a, str) or not a.strip() for a in assertions):
            raise ValueError("each assertion must be a non-empty string")
        if not retrieved_contexts:
            raise ValueError("retrieved_contexts must contain at least one context")
        if any(not isinstance(c, str) for c in retrieved_contexts):
            raise TypeError("each retrieved context must be a string")

        premise = "\n".join(retrieved_contexts)
        if not premise.strip():
            raise ValueError("retrieved_contexts must contain non-blank evidence")

        import torch

        results: list[AssertionGroundedness] = []
        with self._inference_lock, torch.inference_mode():
            for start in range(0, len(assertions), self.batch_size):
                batch = assertions[start : start + self.batch_size]
                pairs = [(premise, assertion) for assertion in batch]
                scores = self.nli_classifier.predict(pairs).detach().cpu().reshape(-1)
                if len(scores) != len(batch):
                    raise RuntimeError(
                        f"HHEM returned {len(scores)} scores for {len(batch)} assertions"
                    )
                for assertion, score in zip(batch, scores.tolist()):
                    confidence = float(score)
                    if not 0.0 <= confidence <= 1.0:
                        raise ValueError(f"HHEM returned an invalid score: {confidence}")
                    results.append(
                        AssertionGroundedness(
                            assertion=assertion,
                            hhem_score=confidence,
                            grounded=confidence >= self.threshold,
                        )
                    )
        return results

    def score(self, response: str, retrieved_contexts: Sequence[str]) -> MetricResult:
        """Return HHEM's continuous support score as a Ragas ``MetricResult``.

        Unlike Ragas's dual-judge rating, this is a classifier support score.
        The thresholded boolean remains available via ``score_assertions``.
        """
        # Match Ragas ResponseGroundedness's treatment of blank strings.
        if not response or not retrieved_contexts:
            raise ValueError("response and retrieved_contexts must be provided")
        if not response.strip() or not "\n".join(retrieved_contexts).strip():
            return MetricResult(value=0.0)

        result = self.score_assertions(
            assertions=[response], retrieved_contexts=retrieved_contexts
        )[0]