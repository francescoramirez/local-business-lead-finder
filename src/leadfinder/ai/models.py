from __future__ import annotations

from dataclasses import asdict, dataclass, field

PROMPT_VERSION = "sales_prep_v1"

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_OUTPUT_LANGUAGE = "Spanish"
MAX_OUTPUT_TOKENS = 800
REQUEST_TIMEOUT = 30.0
TEMPERATURE = 0.3


@dataclass
class SalesPrepRequest:
    name: str
    business_type: str
    location: str
    region: str
    country: str
    rating: float | None
    review_count: int | None
    digital_presence: str
    website_status: str
    qualification_signals: str
    opportunity_score: int
    opportunity_level: str
    contact_status: str
    notes: str
    tags: str
    operational: bool
    language: str = DEFAULT_OUTPUT_LANGUAGE
    prompt_version: str = PROMPT_VERSION
    selected_template: str = ""

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "name": self.name,
            "business_type": self.business_type,
            "location": self.location,
            "region": self.region,
            "country": self.country,
            "rating": self.rating,
            "review_count": self.review_count,
            "digital_presence": self.digital_presence,
            "website_status": self.website_status,
            "qualification_signals": self.qualification_signals,
            "opportunity_score": self.opportunity_score,
            "opportunity_level": self.opportunity_level,
            "contact_status": self.contact_status,
            "notes": self.notes,
            "tags": self.tags,
            "operational": self.operational,
            "language": self.language,
        }
        if self.selected_template.strip():
            payload["selected_template"] = self.selected_template.strip()[:2000]
        return payload


@dataclass
class SalesPrepResult:
    opportunity_summary: str
    pitch_angle: str
    value_props: list[str] = field(default_factory=list)
    opening_message: str = ""
    talking_points: list[str] = field(default_factory=list)
    objections: list[str] = field(default_factory=list)
    cautions: list[str] = field(default_factory=list)
    next_step: str = ""
    observed: list[str] = field(default_factory=list)
    information_gaps: str = ""
    prompt_version: str = PROMPT_VERSION

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def as_notes_block(self) -> str:
        props = "\n".join(f"- {item}" for item in self.value_props)
        points = "\n".join(f"- {item}" for item in self.talking_points)
        return (
            "AI sales prep (draft — review before contact)\n"
            f"Summary: {self.opportunity_summary}\n"
            f"Angle: {self.pitch_angle}\n"
            f"Opener: {self.opening_message}\n"
            f"Value props:\n{props}\n"
            f"Talking points:\n{points}\n"
            f"Next step: {self.next_step}"
        )


REQUIRED_RESULT_FIELDS = (
    "opportunity_summary",
    "pitch_angle",
    "value_props",
    "opening_message",
    "talking_points",
    "objections",
    "cautions",
    "next_step",
)

INSIGHTS_PROMPT_VERSION = "analytics_insights_v1"
EXPERIMENT_PROMPT_VERSION = "experiment_summary_v1"

REQUIRED_INSIGHTS_FIELDS = (
    "summary",
    "observed",
    "hypotheses",
    "experiments",
    "cautions",
)


@dataclass
class InsightsExplanation:
    summary: str
    observed: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)
    experiments: list[str] = field(default_factory=list)
    cautions: list[str] = field(default_factory=list)
    prompt_version: str = INSIGHTS_PROMPT_VERSION

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
