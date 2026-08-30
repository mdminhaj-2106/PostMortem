"""Declared config -- plain module-level constants, same pattern as every other
stage's config/cause_config.py. See .claude/plans/stage8-counterfactual-impact-engine.md.
"""

MINIMUM_CONFIDENCE = ("KNOWN", "LIKELY", "POSSIBLE")
ALLOW_UNKNOWN = False

# Buffer of trailing days fetched before window_start so Stage 2's baseline.py
# (14-day trailing median, 5-observation minimum) has enough history to produce a
# real `expected` for every day inside the investigated window.
PRE_WINDOW_HISTORY_DAYS = 30
