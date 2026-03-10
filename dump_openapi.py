import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))


def main():
    try:
        from api.main import app

        schema = app.openapi()
        with open("openapi.json", "w") as f:
            json.dump(schema, f, indent=2)
        print("Successfully generated openapi.json")
    except Exception as e:
        print(f"Failed to generate openapi.json: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
