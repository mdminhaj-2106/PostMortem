"""Step 3b (design doc §7): spaCy entity extraction + VADER sentiment, applied only
to the post-ranking survivor set (design doc §13's non-goal: no full-corpus
NER/sentiment tagging, to keep this cheap).
"""

import spacy
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_NEGATIVE_THRESHOLD = -0.05
_POSITIVE_THRESHOLD = 0.05

_nlp = None
_analyzer = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


def _get_analyzer():
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentIntensityAnalyzer()
    return _analyzer


def sentiment(text):
    compound = _get_analyzer().polarity_scores(text)["compound"]
    if compound <= _NEGATIVE_THRESHOLD:
        return "negative"
    if compound >= _POSITIVE_THRESHOLD:
        return "positive"
    return "neutral"


def entities(text):
    return [(ent.text, ent.label_) for ent in _get_nlp()(text).ents]
