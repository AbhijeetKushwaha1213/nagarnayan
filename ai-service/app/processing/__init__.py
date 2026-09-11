"""Processing package for frame sampling and YOLO inference."""

from app.processing.frame_sampler import FrameSampler, SampledFrame
from app.processing.inference import InferenceProcessor

__all__ = ["FrameSampler", "InferenceProcessor", "SampledFrame"]
