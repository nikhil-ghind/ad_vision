"""TensorFlow content analysis: image classification + text sentiment for brand safety."""
from __future__ import annotations
import numpy as np
import tensorflow as tf
from typing import Dict, Any, List
import base64
import io


_mobilenet: tf.keras.Model = None
_CLASS_NAMES: List[str] = []


def _load_mobilenet():
    global _mobilenet, _CLASS_NAMES
    if _mobilenet is None:
        _mobilenet = tf.keras.applications.MobileNetV3Small(
            input_shape=(224, 224, 3), weights="imagenet", include_top=True
        )
        _CLASS_NAMES = [l.strip() for l in
                        tf.keras.applications.mobilenet_v3.decode_predictions.__doc__.split()[:1001]]
    return _mobilenet


def analyze_image(image_bytes: bytes) -> Dict[str, Any]:
    """Classify image content and flag brand-safety concerns."""
    model = _load_mobilenet()
    img = tf.image.decode_image(image_bytes, channels=3, expand_animations=False)
    img = tf.image.resize(img, [224, 224])
    img = tf.keras.applications.mobilenet_v3.preprocess_input(img[tf.newaxis])
    preds = model(img, training=False).numpy()[0]
    top5_idx  = np.argsort(preds)[::-1][:5]
    top5 = tf.keras.applications.mobilenet_v3.decode_predictions(preds[np.newaxis], top=5)[0]

    categories = [{"label": name, "score": float(score)} for _, name, score in top5]
    flagged = any(score > 0.5 and any(kw in name.lower() for kw in ["weapon", "violence", "nude"])
                  for _, name, score in top5)

    return {
        "categories": categories,
        "brand_safe": not flagged,
        "top_label": top5[0][1],
        "confidence": float(top5[0][2]),
    }


def analyze_text(text: str) -> Dict[str, Any]:
    """Simple rule-based + keyword brand-safety text check (placeholder for fine-tuned model)."""
    UNSAFE_KEYWORDS = {"violence", "hate", "explicit", "illegal", "weapon"}
    words = set(text.lower().split())
    hits  = words & UNSAFE_KEYWORDS
    sentiment_score = float(len([w for w in words if w in {"great", "good", "excellent", "love"}]) -
                             len([w for w in words if w in {"bad", "terrible", "worst", "awful"}]))
    return {
        "brand_safe": len(hits) == 0,
        "flagged_keywords": list(hits),
        "sentiment": "positive" if sentiment_score > 0 else "negative" if sentiment_score < 0 else "neutral",
        "sentiment_score": sentiment_score,
    }
