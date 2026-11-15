import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from rock_api.config import get_settings
from rock_api.storage import ObservationStore


def main() -> None:
    dataset_path = PROJECT_ROOT / "rock_api" / "nasa_analog_sites.json"
    sites = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(sites, list) or len(sites) < 30:
        raise ValueError(f"Expected at least 30 analog sites in {dataset_path}")

    settings = get_settings()
    count = ObservationStore(settings.database_path).upsert_analog_sites(sites)
    print(f"Imported {count} NASA-referenced analog sites into {settings.database_path}")


if __name__ == "__main__":
    main()
