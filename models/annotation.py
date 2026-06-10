from dataclasses import dataclass, field


@dataclass
class AnnotationCandidate:
    rank: int | None
    x_ratio: float
    y_ratio: float
    radius_ratio: float
    label: str
    findings: list[str]
    confidence: float | None
    reason: str


@dataclass
class AnnotationResult:
    candidates: list[AnnotationCandidate]
    overall_comment: str = ""
