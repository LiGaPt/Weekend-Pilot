from __future__ import annotations

import re
from datetime import datetime

from backend.app.planning.errors import IntentParseError
from backend.app.planning.schemas import IntentConstraints, LocalLifeIntent, ParticipantProfile, TimeWindow


class DeterministicIntentParser:
    parser_version = "deterministic_intent_parser_v1"

    _FAMILY_KEYWORDS = (
        "wife",
        "husband",
        "child",
        "kid",
        "family",
        "老婆",
        "妻子",
        "丈夫",
        "孩子",
        "小孩",
        "亲子",
    )
    _SPOUSE_KEYWORDS = ("wife", "husband", "老婆", "妻子", "丈夫")
    _CHILD_KEYWORDS = ("child", "kid", "kids", "son", "daughter", "孩子", "小孩", "亲子")
    _FRIEND_KEYWORDS = ("friend", "friends", "朋友")
    _SOLO_KEYWORDS = ("solo", "alone", "myself", "一个人")

    def parse(self, text: str, reference_now: datetime | None = None) -> LocalLifeIntent:
        raw_text = text.strip()
        if not raw_text:
            raise IntentParseError("User text is empty.")

        normalized = raw_text.lower()
        family_signal = self._contains_any(normalized, self._FAMILY_KEYWORDS)
        child_signal = self._contains_any(normalized, self._CHILD_KEYWORDS)
        spouse_signal = self._contains_any(normalized, self._SPOUSE_KEYWORDS)

        scenario_type = self._parse_scenario_type(normalized, family_signal)
        child_ages = self._parse_child_ages(raw_text)
        adults = 2 if spouse_signal else 1

        time_window = self._parse_time_window(normalized, reference_now)
        child_friendly = family_signal or child_signal or bool(child_ages)
        activity_preferences = ["child_friendly"] if child_friendly else []
        dining_preferences = self._parse_dining_preferences(normalized)

        return LocalLifeIntent(
            raw_text=raw_text,
            scenario_type=scenario_type,
            participants=ParticipantProfile(adults=adults, children_ages=child_ages),
            time_window=time_window,
            constraints=IntentConstraints(
                child_friendly=child_friendly,
                max_distance_km=self._parse_max_distance_km(normalized),
            ),
            activity_preferences=activity_preferences,
            dining_preferences=dining_preferences,
            origin_text=None,
            parser_version=self.parser_version,
        )

    def _parse_scenario_type(self, text: str, family_signal: bool) -> str:
        if family_signal:
            return "family"
        if self._contains_any(text, self._FRIEND_KEYWORDS):
            return "friends"
        if self._contains_any(text, self._SOLO_KEYWORDS):
            return "solo"
        return "unknown"

    def _parse_child_ages(self, text: str) -> list[int]:
        patterns = (
            r"(?:child|kid|son|daughter)\s*(?:is|aged|age)?\s*(\d{1,2})",
            r"(\d{1,2})\s*[- ]?\s*year[- ]?old",
            r"(\d{1,2})\s*岁\s*(?:孩子|小孩|儿子|女儿)?",
            r"(?:孩子|小孩|儿子|女儿)\s*(\d{1,2})\s*岁",
        )
        ages: list[int] = []
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                age = int(match.group(1))
                if age not in ages:
                    ages.append(age)
        return ages

    def _parse_time_window(self, text: str, reference_now: datetime | None) -> TimeWindow:
        label = None
        start_at = None
        end_at = None
        if "this afternoon" in text or "afternoon" in text or "今天下午" in text:
            label = "this_afternoon"
            if reference_now is not None:
                start_at = reference_now.replace(hour=13, minute=30, second=0, microsecond=0)
                end_at = reference_now.replace(hour=18, minute=30, second=0, microsecond=0)

        duration_min = None
        duration_max = None
        if "few hours" in text or "several hours" in text or "几个小时" in text:
            duration_min = 4
            duration_max = 6

        return TimeWindow(
            label=label,
            start_at=start_at,
            end_at=end_at,
            duration_hours_min=duration_min,
            duration_hours_max=duration_max,
        )

    def _parse_max_distance_km(self, text: str) -> int | None:
        if any(phrase in text for phrase in ("not too far", "not far", "nearby", "close", "别太远", "不要太远", "不太远", "附近")):
            return 8
        return None

    def _parse_dining_preferences(self, text: str) -> list[str]:
        if any(phrase in text for phrase in ("lighter", "eat lighter", "light food", "清淡")):
            return ["lighter_options"]
        return []

    def _contains_any(self, text: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in text for keyword in keywords)
