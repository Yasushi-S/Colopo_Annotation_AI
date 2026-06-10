from abc import ABC, abstractmethod

from PIL import Image

from models.annotation import AnnotationResult


class AbstractAnnotationInference(ABC):
    @abstractmethod
    def analyze(self, image: Image.Image) -> AnnotationResult:
        ...
