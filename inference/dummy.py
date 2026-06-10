from PIL import Image

from inference.base import AbstractAnnotationInference
from models.annotation import AnnotationCandidate, AnnotationResult


class DummyAnnotationInference(AbstractAnnotationInference):

    def analyze(self, image: Image.Image) -> AnnotationResult:
        return AnnotationResult(
            candidates=[
                AnnotationCandidate(
                    rank=1,
                    x_ratio=0.52,
                    y_ratio=0.38,
                    radius_ratio=0.06,
                    label="HSIL_suspicious",
                    findings=["dense_acetowhite", "sharp_margin", "coarse_mosaic"],
                    confidence=0.85,
                    reason="12時方向に境界明瞭な濃い酢酸白色上皮と粗大モザイクを認める。SCJに近接しており生検優先度が高い。",
                ),
                AnnotationCandidate(
                    rank=2,
                    x_ratio=0.68,
                    y_ratio=0.42,
                    radius_ratio=0.05,
                    label="LSIL_like",
                    findings=["dense_acetowhite"],
                    confidence=0.72,
                    reason="2時方向に限局した白色上皮。境界は比較的明瞭だが範囲は小さい。",
                ),
                AnnotationCandidate(
                    rank=3,
                    x_ratio=0.45,
                    y_ratio=0.55,
                    radius_ratio=0.04,
                    label="inflammation_like",
                    findings=["inflammation_like"],
                    confidence=0.55,
                    reason="6時方向に炎症様変化の疑い。偽陽性の可能性を考慮し比較部位として提示。",
                ),
            ],
            overall_comment="画質良好。SCJは概ね可視。",
        )
