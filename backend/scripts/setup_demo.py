"""Initialize the explicitly enabled demo without changing other shops or their data."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import Settings  # noqa: E402
from app.core.errors import BusinessError  # noqa: E402
from app.repositories.database import create_database_engine, create_session_factory  # noqa: E402
from app.repositories.unit_of_work import UnitOfWork  # noqa: E402
from app.services.demo import DemoService  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--adopt-existing-admin",
        action="store_true",
        help="Convert an existing admin to the public demo account and reset its password",
    )
    args = parser.parse_args()
    settings = Settings(_env_file=ROOT / ".env")  # type: ignore[call-arg]
    if not settings.demo_enabled:
        parser.error("Set SOLOOPS_DEMO_ENABLED=true before initializing the demo")
    engine = create_database_engine(settings)
    try:
        with create_session_factory(engine)() as session:
            result = DemoService(UnitOfWork(session), settings).setup(
                adopt_existing_admin=args.adopt_existing_admin
            )
        print(json.dumps(asdict(result), ensure_ascii=False))
    except BusinessError as error:
        raise SystemExit(error.message) from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
