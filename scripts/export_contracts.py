"""Export shared contracts without requiring a running API or provider credentials."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))

from market_research.contracts import AnalysisReport, ConfirmedPlan, ResearchRequest  # noqa: E402


def main() -> None:
    destination = ROOT / "docs/contracts"
    destination.mkdir(parents=True, exist_ok=True)
    for model in (ResearchRequest, ConfirmedPlan, AnalysisReport):
        schema = model.model_json_schema(mode="serialization")
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        path = destination / f"{model.__name__}.schema.json"
        path.write_text(json.dumps(schema, indent=2) + "\n")
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
