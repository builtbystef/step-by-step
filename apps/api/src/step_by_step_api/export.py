"""Dump the OpenAPI schema to disk so packages/api-client can generate from it.

Usage: python -m step_by_step_api.export [output-path]
"""

import json
import sys
from pathlib import Path

from step_by_step_api.main import app


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    out.write_text(json.dumps(app.openapi(), indent=2) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
