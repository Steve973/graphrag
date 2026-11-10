"""Load the Ragas HHEM classifier from local model files.

Install PyTorch, Transformers, and SentencePiece in your environment. Use
your configured Ragas evaluator LLM to extract claims for HHEM to check.
For example, in an async function with `evaluator_llm` already configured::

    from ragas.dataset_schema import SingleTurnSample
    from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.local_faithfulness_with_hhem import (
        LocalFaithfulnessWithHHEM,
    )

    metric = LocalFaithfulnessWithHHEM(
        llm=evaluator_llm,
        model_dir="/models/hhem",
        foundation_dir="/models/flan-t5-base",
        device="cpu",
        batch_size=10,
    )
    sample = SingleTurnSample(
        user_input="What is the capital of France?",
        response="Paris is the capital of France.",
        retrieved_contexts=["Paris is the capital of France."],
    )
    score = await metric.single_turn_ascore(sample)
"""

from dataclasses import dataclass, field
from pathlib import Path

from ragas.metrics._faithfulness import Faithfulness, FaithfulnesswithHHEM


@dataclass
class LocalFaithfulnessWithHHEM(FaithfulnesswithHHEM):
    """Use a trusted Vectara HHEM snapshot and a local FLAN-T5 foundation.

    The HHEM directory must contain the weights, config, and custom Python
    files. Put the FLAN-T5 config and tokenizer files in its `foundation`
    subdirectory or pass a separate `foundation_dir`. The foundation's
    weights are already included in the HHEM checkpoint.
    """

    model_dir: str | Path = field(kw_only=True)
    foundation_dir: str | Path | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        model_dir = Path(self.model_dir).expanduser().resolve()
        if not model_dir.is_dir():
            raise NotADirectoryError(f"HHEM model directory does not exist: {model_dir}")

        foundation_dir = (
            Path(self.foundation_dir).expanduser().resolve()
            if self.foundation_dir is not None
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
        # Vectara's constructor uses this path for its nested config and tokenizer loads.
        config.foundation = str(foundation_dir)
        self.nli_classifier = AutoModelForSequenceClassification.from_pretrained(
            str(model_dir),
            config=config,
            local_files_only=True,
            trust_remote_code=True,
        )
        self.nli_classifier.to(self.device)

        # Run the Ragas metric initialization past the hardcoded HHEM loader.
        Faithfulness.__post_init__(self)
