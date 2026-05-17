from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest

from incognito.models import EntityType, RawDetection

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CORPUS_DIR: Final[Path] = Path(__file__).parent / "evaluation" / "corpus"
BENCHMARK_PATH: Final[Path] = (
    Path(__file__).parent.parent / "tmp_tests" / "benchmark_v1_tuned_results.json"
)

CORPUS_PAIRS: Final[list[tuple[Path, Path]]] = [
    (
        CORPUS_DIR / "housing_allocation_decision_notice.pdf",
        CORPUS_DIR / "housing_allocation_decision_notice_pii.json",
    ),
    (
        CORPUS_DIR / "ssa_benefit_verification.pdf",
        CORPUS_DIR / "ssa_benefit_verification_pii.json",
    ),
]

BASELINE_DOCS: Final[frozenset[str]] = frozenset(
    [
        "housing_allocation_decision_notice.pdf",
        "ssa_benefit_verification.pdf",
    ]
)

BASELINE_TOLERANCE: Final[float] = 0.05
MICRO_F1_THRESHOLD: Final[float] = 0.70
EMAIL_F1_THRESHOLD: Final[float] = 1.00
PHONE_F1_THRESHOLD: Final[float] = 1.00
PERSON_RECALL_THRESHOLD: Final[float] = 0.90
PERSON_PRECISION_THRESHOLD: Final[float] = 0.50

REPORT_PATH: Final[Path] = CORPUS_DIR.parent / "eval_results.json"


# ---------------------------------------------------------------------------
# Scoring types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GroundTruth:
    text: str
    entity_type: str
    page: int
    block_index: int
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class EntityCounts:
    tp: int
    fp: int
    fn: int

    @property
    def precision(self: EntityCounts) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) > 0 else 0.0

    @property
    def recall(self: EntityCounts) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) > 0 else 0.0

    @property
    def f1(self: EntityCounts) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


@dataclass(frozen=True, slots=True)
class F1Result:
    per_entity: dict[str, EntityCounts]
    micro: EntityCounts


# ---------------------------------------------------------------------------
# Scoring logic (two-pass overlap matching)
# ---------------------------------------------------------------------------


def _spans_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return max(start_a, start_b) < min(end_a, end_b)


def _det_span_len(det: RawDetection) -> int:
    return det.end - det.start


def _load_ground_truth(gt_path: Path) -> list[GroundTruth]:
    raw: list[dict[str, object]] = json.loads(gt_path.read_text())
    return [
        GroundTruth(
            text=str(item["text"]),
            entity_type=str(item["entity_type"]),
            page=int(str(item["page"])),
            block_index=int(str(item["block_index"])),
            start=int(str(item["start"])),
            end=int(str(item["end"])),
        )
        for item in raw
    ]


def _det_matches_gt(det: RawDetection, gt: GroundTruth) -> bool:
    return (
        det.page == gt.page
        and det.block_index == gt.block_index
        and _spans_overlap(det.start, det.end, gt.start, gt.end)
    )


def _match_non_address(
    ground_truth: list[GroundTruth],
    detections: list[RawDetection],
    matched_gt: set[int],
    matched_det: set[int],
) -> None:
    for gt_idx, gt in enumerate(ground_truth):
        if gt.entity_type == EntityType.ADDRESS:
            continue
        best_det_idx: int | None = None
        best_span_len: int = -1
        for det_idx, det in enumerate(detections):
            if det_idx in matched_det or str(det.entity_type) != gt.entity_type:
                continue
            if _det_matches_gt(det, gt) and _det_span_len(det) > best_span_len:
                best_span_len = _det_span_len(det)
                best_det_idx = det_idx
        if best_det_idx is not None:
            matched_gt.add(gt_idx)
            matched_det.add(best_det_idx)


def _match_address_fragments(
    ground_truth: list[GroundTruth],
    detections: list[RawDetection],
    matched_gt: set[int],
    matched_det: set[int],
) -> None:
    for gt_idx, gt in enumerate(ground_truth):
        if gt.entity_type != EntityType.ADDRESS:
            continue
        overlapping = [
            di
            for di, det in enumerate(detections)
            if di not in matched_det
            and str(det.entity_type) == EntityType.ADDRESS
            and _det_matches_gt(det, gt)
        ]
        if overlapping:
            matched_gt.add(gt_idx)
            matched_det.update(overlapping)


def _compute_counts(
    ground_truth: list[GroundTruth],
    detections: list[RawDetection],
    matched_gt: set[int],
    matched_det: set[int],
) -> F1Result:
    per_entity: dict[str, EntityCounts] = {}
    for et in (e.value for e in EntityType):
        gt_indices = [i for i, g in enumerate(ground_truth) if g.entity_type == et]
        det_indices = [i for i, d in enumerate(detections) if str(d.entity_type) == et]
        tp = sum(1 for i in gt_indices if i in matched_gt)
        fp = sum(1 for i in det_indices if i not in matched_det)
        per_entity[et] = EntityCounts(tp=tp, fp=fp, fn=len(gt_indices) - tp)
    total_tp = sum(c.tp for c in per_entity.values())
    total_fp = sum(c.fp for c in per_entity.values())
    total_fn = sum(c.fn for c in per_entity.values())
    return F1Result(
        per_entity=per_entity, micro=EntityCounts(tp=total_tp, fp=total_fp, fn=total_fn)
    )


def score_detections(
    ground_truth: list[GroundTruth],
    detections: list[RawDetection],
) -> F1Result:
    matched_gt: set[int] = set()
    matched_det: set[int] = set()
    _match_non_address(ground_truth, detections, matched_gt, matched_det)
    _match_address_fragments(ground_truth, detections, matched_gt, matched_det)
    return _compute_counts(ground_truth, detections, matched_gt, matched_det)


def _aggregate_counts(results: list[F1Result]) -> F1Result:
    entity_types = [e.value for e in EntityType]
    per_entity: dict[str, EntityCounts] = {}
    for et in entity_types:
        tp = sum(r.per_entity[et].tp for r in results)
        fp = sum(r.per_entity[et].fp for r in results)
        fn = sum(r.per_entity[et].fn for r in results)
        per_entity[et] = EntityCounts(tp=tp, fp=fp, fn=fn)
    micro = EntityCounts(
        tp=sum(r.micro.tp for r in results),
        fp=sum(r.micro.fp for r in results),
        fn=sum(r.micro.fn for r in results),
    )
    return F1Result(per_entity=per_entity, micro=micro)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_RESULTS: dict[str, F1Result] = {}


def _counts_to_dict(c: EntityCounts) -> dict[str, object]:
    return {
        "tp": c.tp,
        "fp": c.fp,
        "fn": c.fn,
        "precision": round(c.precision, 4),
        "recall": round(c.recall, 4),
        "f1": round(c.f1, 4),
    }


def _write_report() -> None:
    if not _RESULTS:
        return
    from incognito.core.config import GLINER_THRESHOLD_ADDRESS, GLINER_THRESHOLD_PERSON

    agg = _aggregate_counts(list(_RESULTS.values()))
    report: dict[str, object] = {
        "timestamp": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "thresholds": {"person": GLINER_THRESHOLD_PERSON, "address": GLINER_THRESHOLD_ADDRESS},
        "per_document": {
            name: {et: _counts_to_dict(r.per_entity[et]) for et in r.per_entity}
            for name, r in _RESULTS.items()
        },
        "aggregate": {
            "per_entity_type": {et: _counts_to_dict(agg.per_entity[et]) for et in agg.per_entity},
            "micro_averaged": _counts_to_dict(agg.micro),
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n")


@pytest.fixture(scope="session", autouse=True)
def _eval_report() -> Iterator[None]:
    yield
    _write_report()


@pytest.fixture(scope="module")
def _ollama_ready() -> None:
    from incognito.ollama.manager import check_ready

    if not check_ready():
        pytest.skip("Ollama not reachable or gemma4:e4b not loaded")


@pytest.fixture(scope="module")
def per_doc_results(_ollama_ready: None) -> dict[str, F1Result]:
    from incognito.ollama.manager import generate
    from incognito.pipeline.detector import detect
    from incognito.pipeline.extractor import extract_blocks

    results: dict[str, F1Result] = {}
    for pdf_path, gt_path in CORPUS_PAIRS:
        blocks = extract_blocks(pdf_path)
        detections = detect(blocks, generate)
        gt = _load_ground_truth(gt_path)
        results[pdf_path.name] = score_detections(gt, detections)
    _RESULTS.update(results)
    return results


@pytest.fixture(scope="module")
def corpus_results(per_doc_results: dict[str, F1Result]) -> F1Result:
    return _aggregate_counts(list(per_doc_results.values()))


@pytest.fixture(scope="module")
def baseline_results(per_doc_results: dict[str, F1Result]) -> F1Result:
    baseline_docs = [r for name, r in per_doc_results.items() if name in BASELINE_DOCS]
    return _aggregate_counts(baseline_docs)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.ollama
def test_micro_f1_meets_threshold(corpus_results: F1Result) -> None:
    micro = corpus_results.micro
    assert micro.f1 >= MICRO_F1_THRESHOLD, (
        f"Micro F1 {micro.f1:.4f} < threshold {MICRO_F1_THRESHOLD} "
        f"(TP={micro.tp}, FP={micro.fp}, FN={micro.fn})"
    )


@pytest.mark.eval
@pytest.mark.ollama
def test_email_f1_is_perfect(corpus_results: F1Result) -> None:
    email = corpus_results.per_entity[EntityType.EMAIL]
    assert email.f1 == EMAIL_F1_THRESHOLD, (
        f"Email F1 {email.f1:.4f} != {EMAIL_F1_THRESHOLD} "
        f"(TP={email.tp}, FP={email.fp}, FN={email.fn})"
    )


@pytest.mark.eval
@pytest.mark.ollama
def test_phone_f1_is_perfect(corpus_results: F1Result) -> None:
    phone = corpus_results.per_entity[EntityType.PHONE]
    assert phone.f1 == PHONE_F1_THRESHOLD, (
        f"Phone F1 {phone.f1:.4f} != {PHONE_F1_THRESHOLD} "
        f"(TP={phone.tp}, FP={phone.fp}, FN={phone.fn})"
    )


@pytest.mark.eval
@pytest.mark.ollama
def test_person_recall_meets_threshold(corpus_results: F1Result) -> None:
    person = corpus_results.per_entity[EntityType.PERSON]
    assert person.recall >= PERSON_RECALL_THRESHOLD, (
        f"Person recall {person.recall:.4f} < threshold {PERSON_RECALL_THRESHOLD} "
        f"(TP={person.tp}, FN={person.fn})"
    )


@pytest.mark.eval
@pytest.mark.ollama
def test_person_precision_meets_threshold(corpus_results: F1Result) -> None:
    person = corpus_results.per_entity[EntityType.PERSON]
    assert person.precision >= PERSON_PRECISION_THRESHOLD, (
        f"Person precision {person.precision:.4f} < threshold {PERSON_PRECISION_THRESHOLD} "
        f"(TP={person.tp}, FP={person.fp})"
    )


@pytest.mark.eval
@pytest.mark.ollama
def test_baseline_micro_f1_within_tolerance(baseline_results: F1Result) -> None:
    benchmark = json.loads(BENCHMARK_PATH.read_text())
    expected_f1: float = benchmark["aggregate"]["micro_averaged"]["f1"]
    actual_f1 = baseline_results.micro.f1
    assert abs(actual_f1 - expected_f1) <= BASELINE_TOLERANCE, (
        f"Micro F1 {actual_f1:.4f} deviates from baseline {expected_f1:.4f} "
        f"by more than ±{BASELINE_TOLERANCE}"
    )


@pytest.mark.eval
@pytest.mark.ollama
def test_baseline_per_entity_f1_within_tolerance(baseline_results: F1Result) -> None:
    benchmark = json.loads(BENCHMARK_PATH.read_text())
    per_type = benchmark["aggregate"]["per_entity_type"]
    for et in (EntityType.EMAIL, EntityType.PHONE, EntityType.PERSON, EntityType.ADDRESS):
        expected_f1: float = per_type[et.value]["f1"]
        actual_f1 = baseline_results.per_entity[et].f1
        assert abs(actual_f1 - expected_f1) <= BASELINE_TOLERANCE, (
            f"{et}: F1 {actual_f1:.4f} deviates from baseline {expected_f1:.4f} "
            f"by more than ±{BASELINE_TOLERANCE}"
        )


@pytest.mark.eval
def test_gliner_threshold_person_env_tunable() -> None:
    """INCOGNITO_GLINER_THRESHOLD_PERSON env var must propagate into config."""
    # This test fails until config.py reads the env var at module level.
    # We import config fresh after patching env to confirm the value is read.
    import importlib

    import incognito.core.config as cfg_module

    original = os.environ.pop("INCOGNITO_GLINER_THRESHOLD_PERSON", None)
    try:
        os.environ["INCOGNITO_GLINER_THRESHOLD_PERSON"] = "0.75"
        importlib.reload(cfg_module)
        assert pytest.approx(0.75) == cfg_module.GLINER_THRESHOLD_PERSON, (
            f"GLINER_THRESHOLD_PERSON={cfg_module.GLINER_THRESHOLD_PERSON!r} "
            "after setting INCOGNITO_GLINER_THRESHOLD_PERSON=0.75"
        )
    finally:
        if original is not None:
            os.environ["INCOGNITO_GLINER_THRESHOLD_PERSON"] = original
        else:
            os.environ.pop("INCOGNITO_GLINER_THRESHOLD_PERSON", None)
        importlib.reload(cfg_module)


@pytest.mark.eval
def test_gliner_threshold_address_env_tunable() -> None:
    """INCOGNITO_GLINER_THRESHOLD_ADDRESS env var must propagate into config."""
    import importlib

    import incognito.core.config as cfg_module

    original = os.environ.pop("INCOGNITO_GLINER_THRESHOLD_ADDRESS", None)
    try:
        os.environ["INCOGNITO_GLINER_THRESHOLD_ADDRESS"] = "0.6"
        importlib.reload(cfg_module)
        assert pytest.approx(0.6) == cfg_module.GLINER_THRESHOLD_ADDRESS, (
            f"GLINER_THRESHOLD_ADDRESS={cfg_module.GLINER_THRESHOLD_ADDRESS!r} "
            "after setting INCOGNITO_GLINER_THRESHOLD_ADDRESS=0.6"
        )
    finally:
        if original is not None:
            os.environ["INCOGNITO_GLINER_THRESHOLD_ADDRESS"] = original
        else:
            os.environ.pop("INCOGNITO_GLINER_THRESHOLD_ADDRESS", None)
        importlib.reload(cfg_module)
