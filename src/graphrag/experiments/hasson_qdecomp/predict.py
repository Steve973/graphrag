"""Train a compact token-graph parser on published BREAK graphs and predict from text."""

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import random
import re
import sys
from zipfile import ZipFile

import networkx as nx

try:
    import torch
    from torch import nn
    from torch.nn import functional as F
except ModuleNotFoundError as error:
    if error.name != "torch":
        raise
    raise SystemExit("Install PyTorch in the experiment environment to train or predict.") from None


@dataclass
class Example:
    tokens: list[str]
    extras: list[str]
    edges: list[tuple[int, int, str]]


def read_examples(upstream: Path, split: str) -> list[Example]:
    member = f"datasets/Break/QDMR/{split}_dependencies_graph.json"
    with ZipFile(upstream / "datasets.zip") as archive, archive.open(member) as stream:
        rows = (json.loads(line) for line in stream if line.strip())
        return [
            Example(
                [token["text"] for token in row["tokens"]],
                [token["text"] for token in row.get("extra_tokens", [])],
                [tuple(edge) for edge in row["deps"]],
            )
            for row in rows
        ]


def tokenize(question: str) -> list[str]:
    # Preserve the source surface forms. This is a lightweight tokenizer for the
    # baseline; upstream's BERT model used the dataset's spaCy tokenization.
    return re.findall(r"\w+(?:[’'-]\w+)*|[^\w\s]", question)


def encode(tokens: list[str], vocabulary: dict[str, int]) -> list[int]:
    return [vocabulary.get(token.casefold(), 1) for token in tokens]


class GraphParser(nn.Module):
    def __init__(self, word_count: int, label_count: int):
        super().__init__()
        self.words = nn.Embedding(word_count, 56, padding_idx=0)
        self.extras = nn.Embedding(2, 8)
        self.encoder = nn.ModuleList(
            nn.Conv1d(64, 64, kernel_size=3, padding=dilation, dilation=dilation)
            for dilation in (1, 2, 4, 8)
        )
        self.dropout = nn.Dropout(0.2)
        self.source = nn.Linear(64, 48)
        self.target = nn.Linear(64, 48)
        self.arc_target = nn.Linear(48, 48)
        self.arc_source_bias = nn.Linear(48, 1)
        self.arc_target_bias = nn.Linear(48, 1)
        self.tag_source = nn.Linear(64, 32)
        self.tag_target = nn.Linear(64, 32)
        self.tag = nn.Linear(32, label_count)

    def forward(self, words, question_lengths, lengths):
        positions = torch.arange(words.shape[1])
        is_extra = positions[None, :] >= question_lengths[:, None]
        if self.training:
            # Learn to predict even when names and technical terms are unseen.
            replace = (torch.rand(words.shape) < 0.12) & (words > 1) & ~is_extra
            words = words.masked_fill(replace, 1)
        inputs = self.dropout(torch.cat((self.words(words), self.extras(is_extra.long())), dim=-1))
        active = positions[None, None, :] < lengths[:, None, None]
        encoded = inputs.transpose(1, 2) * active
        for layer in self.encoder:
            encoded = (encoded + self.dropout(F.gelu(layer(encoded)))) * active
        encoded = encoded.transpose(1, 2)
        source = F.elu(self.source(encoded))
        target = F.elu(self.target(encoded))
        arc = (
            source @ self.arc_target(target).transpose(1, 2) / (48 ** 0.5)
            + self.arc_source_bias(source)
            + self.arc_target_bias(target).transpose(1, 2)
        )
        return arc, F.elu(self.tag_source(encoded)), F.elu(self.tag_target(encoded))

    def labels(self, source, target, batch, start, end):
        return self.tag(source[batch, start] * target[batch, end])


@dataclass
class TrainingExample:
    words: list[int]
    question_length: int
    edges: dict[tuple[int, int], int]
    gold: set[tuple[int, int, str]]


def prepare(examples, vocabulary, labels) -> list[TrainingExample]:
    label_ids = {label: index for index, label in enumerate(labels)}
    return [
        TrainingExample(
            encode(example.tokens + example.extras, vocabulary),
            len(example.tokens),
            {
                (source, target): label_ids[label]
                for source, target, label in example.edges
                if label in label_ids and source != target
            },
            set(example.edges),
        )
        for example in examples
        if example.tokens
    ]


def batches(examples, size: int, rng: random.Random | None = None):
    ordered = list(examples)
    if rng is not None:
        rng.shuffle(ordered)
    ordered.sort(key=lambda example: len(example.words))
    groups = [ordered[index:index + size] for index in range(0, len(ordered), size)]
    if rng is not None:
        rng.shuffle(groups)
    yield from groups


def make_batch(examples):
    lengths = torch.tensor([len(example.words) for example in examples])
    questions = torch.tensor([example.question_length for example in examples])
    width = int(lengths.max())
    words = torch.tensor([
        example.words + [0] * (width - len(example.words)) for example in examples
    ])
    active = torch.arange(width)[None, :] < lengths[:, None]
    mask = active[:, :, None] & active[:, None, :] & ~torch.eye(width, dtype=torch.bool)
    return words, questions, lengths, mask


def training_loss(model, examples):
    words, questions, lengths, mask = make_batch(examples)
    arcs, source, target = model(words, questions, lengths)
    expected = torch.zeros_like(arcs)
    edges = [
        (batch, start, end, label)
        for batch, example in enumerate(examples)
        for (start, end), label in example.edges.items()
    ]
    if not edges:
        return F.binary_cross_entropy_with_logits(arcs[mask], expected[mask])
    batch, start, end, tags = torch.tensor(edges).T
    expected[batch, start, end] = 1
    # Positive arcs are sparse. Weight them for training, then choose a
    # probability threshold on held-out graphs.
    arc_loss = F.binary_cross_entropy_with_logits(
        arcs[mask], expected[mask], pos_weight=torch.tensor(6.0)
    )
    return arc_loss + F.cross_entropy(model.labels(source, target, batch, start, end), tags)


def predict_edges(model, inputs, labels, min_threshold):
    words, questions, lengths, mask = inputs
    arcs, source, target = model(words, questions, lengths)
    probabilities = arcs.sigmoid()
    batch, start, end = (mask & (probabilities >= min_threshold)).nonzero(as_tuple=True)
    predictions = [[] for _ in range(len(words))]
    if len(batch):
        tags = model.labels(source, target, batch, start, end).argmax(dim=-1)
        for b, s, e, tag, probability in zip(
            batch.tolist(), start.tolist(), end.tolist(), tags.tolist(),
            probabilities[batch, start, end].tolist(), strict=True,
        ):
            predictions[b].append((s, e, labels[tag], probability))
    return predictions


def prune_edges(edges):
    """Drop incompatible predictions in confidence order without inventing arcs."""
    ranked = sorted(edges, key=lambda edge: edge[3], reverse=True)
    spans = nx.DiGraph()
    for start, end, tag, _ in ranked:
        if tag == "span" and start < end and not spans.succ.get(start) and not spans.pred.get(end):
            spans.add_edge(start, end)
    representative = {
        token: max(span)
        for span in nx.weakly_connected_components(spans)
        for token in span
    }
    accepted = [edge for edge in ranked if edge[2] == "span" and spans.has_edge(*edge[:2])]
    dependencies = nx.DiGraph()
    operators = {}
    roles = set()
    seen = set()
    repeated = {"union-sub", "intersection-intersection", "comparison-arg", "arithmetic-arg"}
    for edge in ranked:
        start, end, tag, _ = edge
        if tag == "span":
            continue
        source = representative.get(start, start)
        target = representative.get(end, end)
        role = tag.partition("[")[0]
        operator = role.partition("-")[0]
        if source == target or (source, target, role) in seen:
            continue
        if role != "duplicate" and operator != operators.get(source, operator):
            continue
        if role not in repeated and (source, role) in roles:
            continue
        if target in dependencies and source in dependencies and nx.has_path(dependencies, target, source):
            continue
        dependencies.add_edge(source, target)
        if role != "duplicate":
            operators[source] = operator
        roles.add((source, role))
        seen.add((source, target, role))
        accepted.append(edge)
    return sorted(accepted)


@torch.inference_mode()
def validate(model, examples, labels, batch_size):
    model.eval()
    thresholds = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
    gold_count = sum(len(example.gold) for example in examples)
    scores = {threshold: [0, 0] for threshold in thresholds}
    for group in batches(examples, batch_size):
        predictions = predict_edges(model, make_batch(group), labels, thresholds[0])
        for example, edges in zip(group, predictions, strict=True):
            for threshold, counts in scores.items():
                predicted = {(s, e, tag) for s, e, tag, score in edges if score >= threshold}
                counts[0] += len(predicted & example.gold)
                counts[1] += len(predicted)
    return max(
        (2 * matches / max(1, predicted + gold_count), threshold)
        for threshold, (matches, predicted) in scores.items()
    )


def train(args):
    rng = random.Random(args.seed)
    torch.manual_seed(args.seed)
    training = read_examples(args.upstream, "train")
    validation = read_examples(args.upstream, "dev")
    rng.shuffle(training)
    rng.shuffle(validation)
    if args.train_limit:
        training = training[:args.train_limit]
    validation = validation[:args.dev_limit]
    counts = Counter(token.casefold() for example in training for token in example.tokens + example.extras)
    vocabulary = {token: index for index, (token, _) in enumerate(counts.most_common(16000), 2)}
    labels = sorted({label for example in training for _, _, label in example.edges})
    extras = Counter(tuple(example.extras) for example in training).most_common(1)[0][0]
    training = prepare(training, vocabulary, labels)
    validation = prepare(validation, vocabulary, labels)
    model = GraphParser(len(vocabulary) + 2, len(labels))
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.003)
    best = -1.0
    for epoch in range(1, args.epochs + 1):
        model.train()
        loss_sum = 0.0
        count = 0
        for group in batches(training, args.batch_size, rng):
            optimizer.zero_grad()
            loss = training_loss(model, group)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            loss_sum += loss.item()
            count += 1
        score, threshold = validate(model, validation, labels, args.batch_size)
        print(
            f"epoch {epoch}: loss={loss_sum / count:.3f}, "
            f"dev labeled arc F1={score:.3f}, threshold={threshold:.2f}",
            file=sys.stderr, flush=True,
        )
        if score > best:
            best = score
            torch.save({
                "format": "break-biaffine-baseline/1", "weights": model.state_dict(),
                "vocabulary": vocabulary, "labels": labels, "extras": list(extras),
                "threshold": threshold, "dev_f1": score,
                "train_count": len(training), "dev_count": len(validation),
            }, args.checkpoint)


@torch.inference_mode()
def predict(args):
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    if checkpoint["format"] != "break-biaffine-baseline/1":
        raise ValueError("Unsupported graph-parser checkpoint")
    vocabulary = checkpoint["vocabulary"]
    labels = checkpoint["labels"]
    model = GraphParser(len(vocabulary) + 2, len(labels))
    model.load_state_dict(checkpoint["weights"])
    model.eval()
    for number, question in enumerate(args.questions, 1):
        tokens = tokenize(question)
        if not tokens:
            raise ValueError("Question must contain at least one token")
        all_tokens = tokens + checkpoint["extras"]
        example = TrainingExample(encode(all_tokens, vocabulary), len(tokens), {}, set())
        threshold = args.threshold if args.threshold is not None else checkpoint["threshold"]
        edges = predict_edges(model, make_batch([example]), labels, threshold)[0]
        raw_count = len(edges)
        if not args.raw:
            edges = prune_edges(edges)
        print(json.dumps({
            "metadata": {
                "question_id": f"prompt-{number}", "question": question,
                "tokens": all_tokens, "pos": ["NONE"] * len(all_tokens),
                "parser": checkpoint["format"], "arc_threshold": threshold,
                "pruned_arc_count": raw_count - len(edges),
            },
            "arcs": [[source, target] for source, target, _, _ in edges],
            "arc_tags": [label for _, _, label, _ in edges],
            "arc_probabilities": [round(score, 4) for _, _, _, score in edges],
        }, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    training = commands.add_parser("train", help="Train on the upstream datasets.zip")
    training.add_argument("--upstream", type=Path, required=True)
    training.add_argument("--checkpoint", type=Path, required=True)
    training.add_argument("--epochs", type=int, default=6)
    training.add_argument("--train-limit", type=int, default=0, help="Zero uses the full training split")
    training.add_argument("--dev-limit", type=int, default=1000)
    training.add_argument("--batch-size", type=int, default=96)
    training.add_argument("--seed", type=int, default=24)
    inference = commands.add_parser("predict", help="Emit upstream-compatible graph JSONL")
    inference.add_argument("--checkpoint", type=Path, required=True)
    inference.add_argument("--threshold", type=float, help="Override the held-out arc threshold")
    inference.add_argument("--raw", action="store_true", help="Skip structural pruning")
    inference.add_argument("questions", nargs="+")
    for command in (training, inference):
        command.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    if args.threads < 1:
        parser.error("--threads must be positive")
    torch.set_num_threads(args.threads)
    if args.command == "train":
        if min(args.epochs, args.dev_limit, args.batch_size) < 1 or args.train_limit < 0:
            parser.error("epochs, dev limit, and batch size must be positive; train limit must be nonnegative")
        train(args)
    else:
        if args.threshold is not None and not 0 < args.threshold < 1:
            parser.error("--threshold must be between zero and one")
        predict(args)


if __name__ == "__main__":
    main()
