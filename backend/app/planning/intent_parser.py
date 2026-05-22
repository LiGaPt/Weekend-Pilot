from __future__ import annotations

import re
from datetime import datetime

from backend.app.planning.errors import IntentParseError
from backend.app.planning.schemas import (
    IntentConstraints,
    IntentParseResult,
    IntentParseSignals,
    LocalLifeIntent,
    ParticipantProfile,
    TimeWindow,
)


class DeterministicIntentParser:
    parser_version = "deterministic_intent_parser_v1"

    _ZH_WIFE = "\u8001\u5a46"
    _ZH_SPOUSE = "\u59bb\u5b50"
    _ZH_HUSBAND = "\u4e08\u592b"
    _ZH_CHILD = "\u5b69\u5b50"
    _ZH_LITTLE_CHILD = "\u5c0f\u5b69"
    _ZH_PARENT_CHILD = "\u4eb2\u5b50"
    _ZH_FRIEND = "\u670b\u53cb"
    _ZH_SOLO = "\u4e00\u4e2a\u4eba"
    _ZH_THIS_AFTERNOON = "\u4eca\u5929\u4e0b\u5348"
    _ZH_FEW_HOURS = "\u51e0\u4e2a\u5c0f\u65f6"
    _ZH_NOT_TOO_FAR = "\u522b\u592a\u8fdc"
    _ZH_DONT_GO_TOO_FAR = "\u4e0d\u8981\u592a\u8fdc"
    _ZH_NOT_FAR = "\u4e0d\u592a\u8fdc"
    _ZH_NEARBY = "\u9644\u8fd1"
    _ZH_LIGHT = "\u6e05\u6de1"
    _ZH_CITYWALK = "\u57ce\u5e02\u6f2b\u6b65"
    _ZH_INDOOR = "\u5ba4\u5185"
    _ZH_OUTDOOR = "\u6237\u5916"
    _ZH_OUTSIDE = "\u5ba4\u5916"
    _ZH_AGE = "\u5c81"
    _ZH_SON = "\u513f\u5b50"
    _ZH_DAUGHTER = "\u5973\u513f"

    _FAMILY_KEYWORDS = (
        "wife",
        "husband",
        "child",
        "kid",
        "family",
        _ZH_WIFE,
        _ZH_SPOUSE,
        _ZH_HUSBAND,
        _ZH_CHILD,
        _ZH_LITTLE_CHILD,
        _ZH_PARENT_CHILD,
    )
    _SPOUSE_KEYWORDS = ("wife", "husband", _ZH_WIFE, _ZH_SPOUSE, _ZH_HUSBAND)
    _CHILD_KEYWORDS = (
        "child",
        "kid",
        "kids",
        "son",
        "daughter",
        _ZH_CHILD,
        _ZH_LITTLE_CHILD,
        _ZH_PARENT_CHILD,
    )
    _FRIEND_KEYWORDS = ("friend", "friends", _ZH_FRIEND)
    _SOLO_KEYWORDS = ("solo", "alone", "myself", _ZH_SOLO)

    def parse(self, text: str, reference_now: datetime | None = None) -> LocalLifeIntent:
        return self.parse_with_signals(text, reference_now=reference_now).intent

    def parse_with_signals(self, text: str, reference_now: datetime | None = None) -> IntentParseResult:
        raw_text = text.strip()
        if not raw_text:
            raise IntentParseError("User text is empty.")

        normalized = raw_text.lower()
        family_signal = self._contains_any(normalized, self._FAMILY_KEYWORDS)
        child_signal = self._contains_any(normalized, self._CHILD_KEYWORDS)
        spouse_signal = self._contains_any(normalized, self._SPOUSE_KEYWORDS)
        friend_signal = self._contains_any(normalized, self._FRIEND_KEYWORDS)
        solo_signal = self._contains_any(normalized, self._SOLO_KEYWORDS)

        child_ages = self._parse_child_ages(raw_text)
        adults = 2 if spouse_signal else 1
        time_window = self._parse_time_window(normalized, reference_now)
        max_distance_km = self._parse_max_distance_km(normalized)
        dining_preferences = self._parse_dining_preferences(normalized)
        child_friendly = family_signal or child_signal or bool(child_ages)
        activity_preferences = ["child_friendly"] if child_friendly else []
        explicit_activity_style = self._parse_activity_style(normalized)
        if explicit_activity_style and explicit_activity_style not in activity_preferences:
            activity_preferences.append(explicit_activity_style)
        scenario_type = self._parse_scenario_type(normalized, family_signal, friend_signal, solo_signal)

        intent = LocalLifeIntent(
            raw_text=raw_text,
            scenario_type=scenario_type,
            participants=ParticipantProfile(adults=adults, children_ages=child_ages),
            time_window=time_window,
            constraints=IntentConstraints(
                child_friendly=child_friendly,
                max_distance_km=max_distance_km,
            ),
            activity_preferences=activity_preferences,
            dining_preferences=dining_preferences,
            origin_text=None,
            parser_version=self.parser_version,
        )
        signals = IntentParseSignals(
            scenario_or_participants=(
                family_signal
                or child_signal
                or spouse_signal
                or friend_signal
                or solo_signal
                or bool(child_ages)
            ),
            time_window=self._time_window_has_explicit_signal(time_window),
            max_distance_km=max_distance_km is not None,
            dining_preferences=bool(dining_preferences),
            activity_preferences=explicit_activity_style is not None,
        )
        return IntentParseResult(intent=intent, signals=signals)

    def _parse_scenario_type(
        self,
        text: str,
        family_signal: bool,
        friend_signal: bool,
        solo_signal: bool,
    ) -> str:
        if family_signal:
            return "family"
        if friend_signal:
            return "friends"
        if solo_signal:
            return "solo"
        return "unknown"

    def _parse_child_ages(self, text: str) -> list[int]:
        patterns = (
            r"(?:child|kid|son|daughter)\s*(?:is|aged|age)?\s*(\d{1,2})",
            r"(\d{1,2})\s*[- ]?\s*year[- ]?old",
            rf"(\d{{1,2}})\s*{self._ZH_AGE}\s*(?:{self._ZH_CHILD}|{self._ZH_LITTLE_CHILD}|{self._ZH_SON}|{self._ZH_DAUGHTER})?",
            rf"(?:{self._ZH_CHILD}|{self._ZH_LITTLE_CHILD}|{self._ZH_SON}|{self._ZH_DAUGHTER})\s*(\d{{1,2}})\s*{self._ZH_AGE}",
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
        if "this afternoon" in text or "afternoon" in text or self._ZH_THIS_AFTERNOON in text:
            label = "this_afternoon"
            if reference_now is not None:
                start_at = reference_now.replace(hour=13, minute=30, second=0, microsecond=0)
                end_at = reference_now.replace(hour=18, minute=30, second=0, microsecond=0)

        duration_min = None
        duration_max = None
        if "few hours" in text or "several hours" in text or self._ZH_FEW_HOURS in text:
            duration_min = 4
            duration_max = 6

        return TimeWindow(
            label=label,
            start_at=start_at,
            end_at=end_at,
            duration_hours_min=duration_min,
            duration_hours_max=duration_max,
        )

    def _time_window_has_explicit_signal(self, time_window: TimeWindow) -> bool:
        return any(
            value is not None
            for value in (
                time_window.label,
                time_window.start_at,
                time_window.end_at,
                time_window.duration_hours_min,
                time_window.duration_hours_max,
            )
        )

    def _parse_max_distance_km(self, text: str) -> int | None:
        if any(
            phrase in text
            for phrase in (
                "not too far",
                "not far",
                "nearby",
                "close",
                self._ZH_NOT_TOO_FAR,
                self._ZH_DONT_GO_TOO_FAR,
                self._ZH_NOT_FAR,
                self._ZH_NEARBY,
            )
        ):
            return 8
        return None

    def _parse_dining_preferences(self, text: str) -> list[str]:
        if any(phrase in text for phrase in ("lighter", "eat lighter", "light food", self._ZH_LIGHT)):
            return ["lighter_options"]
        return []

    def _parse_activity_style(self, text: str) -> str | None:
        for style, fragments in (
            ("citywalk", ("citywalk", "city walk", self._ZH_CITYWALK)),
            ("indoor", ("indoor", "inside", self._ZH_INDOOR)),
            ("outdoor", ("outdoor", "outside", self._ZH_OUTDOOR, self._ZH_OUTSIDE)),
        ):
            if any(fragment in text for fragment in fragments):
                return style
        return None

    def _contains_any(self, text: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in text for keyword in keywords)
