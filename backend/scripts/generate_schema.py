import sys
import json
from pathlib import Path


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from app.main import app

    output_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "openapi.json"
    schema = app.openapi()
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    print(f"OpenAPI schema generated at: {output_path}")


if __name__ == "__main__":
    main()