"""Dorothy OS v2.0 — Layer 1 Fast Intent Router.

A zero-dependency, pure-regex intent classifier designed to resolve the
user's top-level intent in under 5 ms.  Each pattern maps to an
``(intent_name, agent_target)`` tuple so the supervisor can dispatch
immediately without waiting for an LLM round-trip.

Hindi keywords are included alongside their English equivalents so the
router works for bilingual / Hinglish queries out of the box.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class IntentMatch:
    """Result returned by the intent router when a pattern fires.

    Attributes:
        intent_name:    Canonical intent label (e.g. ``open_app``).
        confidence:     Float in ``[0.0, 1.0]`` — 1.0 for exact regex hits.
        matched_pattern: The regex pattern string that matched.
        agent_target:   ID of the agent responsible for handling this intent.
    """

    intent_name: str
    confidence: float
    matched_pattern: str
    agent_target: str


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class IntentRouter:
    """Regex-based Layer 1 intent classifier.

    The router iterates through a static ``PATTERNS`` dict, compiles each
    pattern once, and returns the highest-confidence match.  Because every
    match from a regex hit is scored at ``1.0`` by default, the *first*
    match in insertion order wins — so more specific patterns are listed
    before generic catch-alls.

    Example::

        router = IntentRouter()
        match = router.route("open chrome")
        if match:
            print(match.intent_name)  # "open_app"
    """

    # Class-level pattern registry: pattern → (intent_name, agent_target)
    PATTERNS: Dict[str, Tuple[str, str]] = {
        # ── App lifecycle ───────────────────────────────────────────────
        r"(?:\b(?:open|launch|start|run)\b|चालू कर(?:ो)?|खोल(?:ो)?)\s+(.+)":
            ("open_app", "desktop_agent"),

        r"(?:\b(?:close|exit|quit|kill)\b|बंद कर(?:ो)?|हटा(?:ओ)?)\s+(.+)":
            ("close_app", "desktop_agent"),

        # ── URLs / web ─────────────────────────────────────────────────
        r"(?:\b(?:open|go to|visit|navigate to|browse)\b)\s+(?:the\s+)?(?:website|url|site|page)?\s*(https?://\S+|\S+\.\S+)":
            ("open_url", "browser_agent"),

        r"(?:\b(?:search|google|look up)\b|खोज(?:ो)?|ढूंढ(?:ो)?)\s+(?:for\s+)?(.+?)(?:\s+on\s+(?:the\s+)?(?:web|internet|google))?$":
            ("search_web", "browser_agent"),

        # ── File operations ────────────────────────────────────────────
        r"(?:\b(?:find|search|locate|look for)\b|फ़ाइल\s*ढूंढ(?:ो)?)\s+(?:file|files)?\s*(.+)":
            ("search_file", "desktop_agent"),

        # ── System info ────────────────────────────────────────────────
        r"(?:\b(?:what(?:'s| is)?\s+the\s+)?(?:current\s+)?(?:time|date)\b|समय|तारीख|टाइम)\s*(?:बता(?:ओ)?)?":
            ("get_time", "system_agent"),

        r"(?:\b(?:system|sys)\b\s*(?:stats?|status|info|health|performance)|\b(?:cpu|ram|memory|battery|disk)\b\s*(?:usage|status|stats?)?|(?:सिस्टम\s*(?:स्टेट्स|जानकारी)))":
            ("system_stats", "system_agent"),

        # ── Power ──────────────────────────────────────────────────────
        r"(?:\b(?:shutdown|shut down|power off|restart|reboot)\b|बंद कर(?:ो)?\s+(?:कंप्यूटर|सिस्टम|pc))":
            ("shutdown", "system_agent"),

        # ── Media ──────────────────────────────────────────────────────
        r"(?:\b(?:play|pause|resume|stop|next|previous)\b|गाना\s*(?:बजा(?:ओ)?|चला(?:ओ)?))\s*(.*)":
            ("play_media", "media_agent"),

        # ── Vision ─────────────────────────────────────────────────────
        r"(?:\b(?:webcam|camera)\b|कैमरा)\s*(?:scan|capture|photo|खोल(?:ो)?|खींच(?:ो)?)":
            ("webcam_scan", "vision_agent"),

        r"(?:\b(?:screenshot|screen\s*capture|snap)\b|स्क्रीनशॉट|what(?:'s|\s+is)\s+on\s+my\s+screen|describe\s+my\s+screen|see\s+my\s+screen)":
            ("screenshot", "vision_agent"),

        # ── Hardware controls ──────────────────────────────────────────
        r"(?:\b(?:set|change|adjust)?\b\s*\b(?:volume)\b|आवाज़|आवाज)\s*(?:to|at|पर)?\s*(\d+)":
            ("set_volume", "system_agent"),

        r"(?:\b(?:set|change|adjust)?\b\s*\b(?:brightness)\b|रोशनी|ब्राइटनेस)\s*(?:to|at|पर)?\s*(\d+)":
            ("set_brightness", "system_agent"),

        # ── Process management ─────────────────────────────────────────
        r"(?:\b(?:list|show|display)\b|दिखा(?:ओ)?)\s+(?:running\s+)?(?:processes|tasks|apps|applications|प्रोसेस)":
            ("list_processes", "system_agent"),

        # ── Terminal / shell ───────────────────────────────────────────
        r"(?:\b(?:run|execute|terminal|shell|cmd)\b|कमांड)\s*(?:command)?\s*[:\-]?\s*(.+)":
            ("terminal_command", "desktop_agent"),
    }

    def __init__(self) -> None:
        """Pre-compile all regex patterns for fast matching."""
        self._compiled: List[Tuple[re.Pattern[str], str, str]] = []
        for pattern, (intent, agent) in self.PATTERNS.items():
            try:
                compiled = re.compile(pattern, re.IGNORECASE | re.UNICODE)
                self._compiled.append((compiled, intent, agent))
            except re.error as exc:
                logger.error("Failed to compile intent pattern %r: %s", pattern, exc)

        logger.debug("IntentRouter initialised with %d patterns", len(self._compiled))

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def route(self, query: str) -> Optional[IntentMatch]:
        """Classify *query* against all registered patterns.

        The first pattern that matches wins (patterns are ordered from
        most-specific to most-generic).  If no pattern matches, ``None``
        is returned so the orchestrator can fall back to LLM-based
        classification.

        Args:
            query: Raw user utterance (may be English, Hindi, or mixed).

        Returns:
            An ``IntentMatch`` on success, or ``None`` when no pattern
            fires.
        """
        query = query.strip()
        if not query:
            return None

        t0 = time.perf_counter_ns()

        best: Optional[IntentMatch] = None
        best_confidence: float = 0.0

        for compiled, intent_name, agent_target in self._compiled:
            match = compiled.search(query)
            if match is None:
                continue

            # Confidence heuristic: ratio of matched span to full query.
            span_len = match.end() - match.start()
            coverage = span_len / len(query) if len(query) > 0 else 0.0
            # Regex hits get a base score of 0.80 + up to 0.20 from coverage.
            confidence = round(0.80 + 0.20 * coverage, 4)

            if confidence > best_confidence:
                best_confidence = confidence
                best = IntentMatch(
                    intent_name=intent_name,
                    confidence=confidence,
                    matched_pattern=compiled.pattern,
                    agent_target=agent_target,
                )

        elapsed_us = (time.perf_counter_ns() - t0) / 1_000
        logger.debug(
            "IntentRouter.route completed in %.1f µs — result=%s",
            elapsed_us,
            best.intent_name if best else "NO_MATCH",
        )

        return best
