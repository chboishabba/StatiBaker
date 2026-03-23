import json
import unittest
from pathlib import Path

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "STATE_SCHEMA.json"
RUNS_DIR = ROOT / "runs"


class TestStateSchemaValidation(unittest.TestCase):
    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_all_state_jsons_match_schema(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        
        state_files = list(RUNS_DIR.glob("**/outputs/state.json"))
        # Also check SAMPLE_STATE.json
        state_files.append(ROOT / "SAMPLE_STATE.json")
        
        failures = []
        for state_file in state_files:
            if not state_file.exists():
                continue
            
            with open(state_file, "r", encoding="utf-8") as f:
                try:
                    state_data = json.load(f)
                    jsonschema.validate(instance=state_data, schema=schema)
                except json.JSONDecodeError:
                    failures.append(f"{state_file.relative_to(ROOT)}: Invalid JSON")
                except jsonschema.exceptions.ValidationError as e:
                    failures.append(f"{state_file.relative_to(ROOT)}: Validation Error: {e.message}")
                    
        if failures:
            self.fail("\n".join(failures))

    def test_schema_exists(self):
        self.assertTrue(SCHEMA_PATH.exists(), f"Schema file {SCHEMA_PATH} is missing")

if __name__ == "__main__":
    unittest.main()
