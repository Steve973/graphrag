"""Run the original Hasson BiaffineDG training and raw-question predictor."""

import argparse
from importlib import import_module
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
from tempfile import NamedTemporaryFile, TemporaryDirectory
from zipfile import ZipFile


CONFIG = Path(
    "experiments/_best/Break/QDMR/dependencies_graph/"
    "biaffine-graph-parser--transformer-encoder.json"
)
DATA_MEMBERS = tuple(
    "datasets/Break/QDMR/{}_{}.json".format(split, kind)
    for split in ("train", "dev")
    for kind in ("dependencies_graph", "spans")
)
GRAPH_MODULES = (
    "qdecomp_nlp.data.dataset_readers.dependencies_graph",
    "qdecomp_nlp.models.dependencies_graph.biaffine_graph_parser",
    "qdecomp_nlp.predictors.dependencies_graph.biaffine_dependency_parser_predictor",
    "qdecomp_nlp.training.metrics.logical_form_em",
)
SOURCE_DIRECTORIES = ("qdecomp_nlp", "dependencies_graph", "evaluation", "scripts", "utils")
DEV_ANNOTATIONS = Path("datasets/Break/QDMR/dev.csv")


def extract_member(archive, member, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=target.parent, delete=False) as destination:
        temporary = Path(destination.name)
        try:
            with archive.open(member) as source:
                shutil.copyfileobj(source, destination)
            destination.close()
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)


def prepare_data(upstream, break_archive=None, *, require_references=True):
    """Use the published graphs, spans and reference QDMRs."""
    with ZipFile(upstream / "datasets.zip") as archive:
        for member in DATA_MEMBERS:
            target = upstream / member
            if target.is_file() and target.stat().st_size:
                continue
            extract_member(archive, member, target)
    if not require_references:
        return
    target = upstream / DEV_ANNOTATIONS
    if target.is_file() and target.stat().st_size:
        return
    if break_archive is None:
        raise FileNotFoundError(
            "The upstream logical-form metric needs {}. "
            "Supply the official Break-dataset.zip with --break-archive.".format(target)
        )
    with ZipFile(break_archive) as archive:
        members = [name for name in archive.namelist() if Path(name).parts[-2:] == ("QDMR", "dev.csv")]
        if len(members) != 1:
            raise ValueError("Expected one QDMR/dev.csv in the BREAK archive.")
        extract_member(archive, members[0], target)


def stage_modern_source(upstream, overlay):
    """Adapt removed Python/NumPy APIs without editing the upstream checkout."""
    for directory in SOURCE_DIRECTORIES:
        shutil.copytree(upstream / directory, overlay / directory, ignore=shutil.ignore_patterns("__pycache__"))
    for path in overlay.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        updated = source.replace("from overrides import overrides", "from typing import override as overrides")
        if updated != source:
            path.write_text(updated, encoding="utf-8")

    path = overlay / "utils/data_structures.py"
    source = path.read_text(encoding="utf-8")
    path.write_text(
        source.replace("import collections\n", "from collections.abc import MutableMapping\n")
        .replace("collections.MutableMapping", "MutableMapping"),
        encoding="utf-8",
    )
    for relative in (
        "dependencies_graph/examine_predictions.py",
        "dependencies_graph/extractors/steps_spans_extractors/aligners/ILP_based_aligner.py",
    ):
        path = overlay / relative
        path.write_text(path.read_text(encoding="utf-8").replace("dtype=np.int)", "dtype=int)"), encoding="utf-8")


def training_overrides(
    config, cuda_device, epochs=None, bert=None, *, batch_size=None, gradient_accumulation_steps=None
):
    overrides = {"trainer.cuda_device": cuda_device}
    if epochs is not None:
        overrides["trainer.num_epochs"] = epochs
    if batch_size is not None:
        overrides["data_loader.batch_sampler.batch_size"] = batch_size
    if gradient_accumulation_steps is not None:
        overrides["trainer.num_gradient_accumulation_steps"] = gradient_accumulation_steps
    if bert is not None:
        # Both the wordpiece indexer and encoder must load the same BERT files.
        reader = config["dataset_reader"]["token_indexers"]["tokens"]
        encoder = config["model"]["text_field_embedder"]["token_embedders"]["tokens"]
        if reader["model_name"] != encoder["model_name"]:
            raise ValueError("The upstream config uses different tokenizer and encoder models.")
        overrides["dataset_reader.token_indexers.tokens.model_name"] = str(bert)
        overrides["model.text_field_embedder.token_embedders.tokens.model_name"] = str(bert)
    return overrides


def sample_training_data(config, upstream, directory, train_count, validation_count):
    rng = random.Random(23)
    overrides = {}
    for key, count in (
        ("train_data_path", train_count),
        ("validation_data_path", validation_count),
    ):
        if count is None:
            continue
        source = upstream / config[key]
        with source.open(encoding="utf-8") as stream:
            rows = stream.readlines()
        if count > len(rows):
            raise ValueError(f"{key} has {len(rows)} rows, fewer than the requested {count}.")
        target = directory / source.name
        target.write_text("".join(rng.sample(rows, count)), encoding="utf-8")
        overrides[key] = str(target)
    return overrides


def launch(args):
    upstream = args.upstream.resolve()
    if not (upstream / CONFIG).is_file():
        raise FileNotFoundError("BiaffineDG configuration missing in {}".format(upstream))
    prepare_data(upstream, args.break_archive, require_references=args.command == "train")
    python = args.python.absolute()
    command = [str(python), str(Path(__file__).resolve())]
    environment = dict(os.environ, PYTHONPATH=str(upstream), DEP_CONF="default")
    if args.command == "train":
        config = json.loads((upstream / CONFIG).read_text(encoding="utf-8"))
        overrides = training_overrides(
            config, args.cuda_device, args.epochs, args.bert,
            batch_size=args.batch_size, gradient_accumulation_steps=args.gradient_accumulation_steps,
        )
        with TemporaryDirectory(prefix="hasson-samples-") as directory:
            overrides.update(sample_training_data(
                config, upstream, Path(directory), args.train_samples, args.validation_samples
            ))
            command.extend([
                "_train", str(args.serialization_dir.resolve()), "--overrides", json.dumps(overrides),
            ])
            return subprocess.run(command, cwd=upstream, env=environment, check=False).returncode
    archive = args.archive.resolve(strict=True)
    command.extend(["_predict", str(archive), "--cuda-device", str(args.cuda_device)])
    if args.decode:
        command.append("--decode")
    # JSON over stdin preserves prompts even when they contain newlines.
    return subprocess.run(
        command,
        cwd=upstream,
        env=environment,
        input=json.dumps(args.questions),
        text=True,
        check=False,
    ).returncode


def run_worker(args):
    if sys.version_info < (3, 12):
        from allennlp.common.util import import_module_and_submodules

        import_module_and_submodules("qdecomp_nlp")
        return run_registered_worker(args)
    with TemporaryDirectory(prefix="hasson-py312-") as directory:
        stage_modern_source(Path.cwd(), Path(directory))
        sys.path.insert(0, directory)
        try:
            for module in GRAPH_MODULES:
                import_module(module)
            return run_registered_worker(args)
        finally:
            sys.path.remove(directory)


def run_registered_worker(args):
    if args.command == "_train":
        from allennlp.commands.train import train_model_from_file

        overrides = json.loads(args.overrides)
        if sys.version_info >= (3, 12):
            config = json.loads(CONFIG.read_text(encoding="utf-8"))
            checkpointer = dict(config["trainer"].get("checkpointer", {}))
            if "num_serialized_models_to_keep" in checkpointer:
                checkpointer["keep_most_recent_by_count"] = checkpointer.pop(
                    "num_serialized_models_to_keep"
                )
                overrides["trainer.checkpointer"] = checkpointer
            # The public archive contains train and dev graphs. Modern AllenNLP
            # opens a configured test split even with test evaluation disabled.
            test_data = config.get("test_data_path")
            if test_data and not Path(test_data).is_file():
                overrides.setdefault("test_data_path", None)
        train_model_from_file(
            parameter_filename=str(CONFIG),
            serialization_dir=args.serialization_dir,
            overrides=json.dumps(overrides),
            file_friendly_logging=True,
        )
        return 0

    from allennlp.models.archival import load_archive
    from qdecomp_nlp.predictors.dependencies_graph.biaffine_dependency_parser_predictor import (
        BiaffineDependencyParserPredictor,
    )

    # The training metric looks up gold QDMRs by question ID even in eval mode.
    # New prompts have no reference rows. This does not affect arc prediction.
    archive = load_archive(
        args.archive,
        cuda_device=args.cuda_device,
        overrides=json.dumps({"model.graph_based_metric": None}),
    )
    if archive.config.get("model").get("type") != "biaffine_graph_parser":
        raise ValueError("Expected an archive for the upstream biaffine_graph_parser.")
    predictor = BiaffineDependencyParserPredictor.from_archive(
        archive, "biaffine-dependency-parser",
    )
    failed = False
    for index, question in enumerate(json.load(sys.stdin), 1):
        result = predictor.predict(
            question, metadata={"question_id": "prompt-{}".format(index), "question": question}
        )
        # Keep the graph format expected by upstream examine_predictions.py.
        row = {key: result[key] for key in ("metadata", "arcs", "arc_tags")}
        if args.decode:
            try:
                row["steps"] = decode_original(row)
            except (AssertionError, IndexError, KeyError, ValueError) as error:
                failed = True
                row["decode_error"] = "{}: {}".format(type(error).__name__, error)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    return int(failed)


def decode_original(row):
    from dependencies_graph.config.configuration_loader import config
    from dependencies_graph.data_types import TokensDependencies
    from dependencies_graph.examine_predictions import prediction_to_dependencies

    tokens, tags, arcs = prediction_to_dependencies(row)
    graph = TokensDependencies.from_tokens(tokens, tags, arcs)
    qdmr = config.tokens_dependencies_to_qdmr_extractor.extract(graph)
    if not qdmr.decomposition_list:
        raise ValueError("The upstream decoder produced no steps.")
    return qdmr.to_break_standard_string(multiline=True).splitlines()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    train = commands.add_parser("train", help="Train with the upstream BiaffineDG configuration")
    predict = commands.add_parser("predict", help="Run the upstream predictor on raw questions")
    for command in (train, predict):
        command.add_argument("--upstream", type=Path, required=True)
        command.add_argument("--python", type=Path, default=Path(sys.executable),
                             help="Worker interpreter (defaults to the launcher interpreter)")
        command.add_argument("--break-archive", type=Path, help="Official Break-dataset.zip for reference dev QDMRs")
        command.add_argument("--cuda-device", type=int, default=-1, help="GPU index, or -1 for CPU")
    train.add_argument("--serialization-dir", type=Path, required=True)
    train.add_argument("--epochs", type=int, help="Override upstream epoch count for a smoke run")
    train.add_argument("--batch-size", type=int, help="Override the upstream batch size")
    train.add_argument("--gradient-accumulation-steps", type=int,
                       help="Accumulate gradients over this many batches per optimizer step")
    train.add_argument("--train-samples", type=int, help="Train on a reproducible sample of the upstream train split")
    train.add_argument("--validation-samples", type=int, help="Validate on a reproducible sample of the dev split")
    train.add_argument("--bert", type=Path, help="Local copy of bert-base-uncased")
    predict.add_argument("--archive", type=Path, required=True)
    predict.add_argument("--decode", action="store_true", help="Also run the original upstream graph decoder")
    predict.add_argument("questions", nargs="+")
    worker_train = commands.add_parser("_train")
    worker_train.add_argument("serialization_dir")
    worker_train.add_argument("--overrides", required=True)
    worker_predict = commands.add_parser("_predict")
    worker_predict.add_argument("archive")
    worker_predict.add_argument("--cuda-device", type=int, required=True)
    worker_predict.add_argument("--decode", action="store_true")
    args = parser.parse_args()

    if args.command.startswith("_"):
        return run_worker(args)
    if args.cuda_device < -1:
        parser.error("--cuda-device must be -1 or a GPU index")
    if args.command == "train":
        for flag, value in (
            ("--epochs", args.epochs),
            ("--batch-size", args.batch_size),
            ("--gradient-accumulation-steps", args.gradient_accumulation_steps),
            ("--train-samples", args.train_samples),
            ("--validation-samples", args.validation_samples),
        ):
            if value is not None and value < 1:
                parser.error(f"{flag} must be positive")
        if args.bert is not None:
            args.bert = args.bert.resolve(strict=True)
            if not args.bert.is_dir():
                parser.error("--bert must be a directory")
    elif any(not question.strip() for question in args.questions):
        parser.error("Questions must be nonempty")
    try:
        return launch(args)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, "{}\n".format(error))


if __name__ == "__main__":
    raise SystemExit(main())
