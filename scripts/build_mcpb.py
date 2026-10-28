"""Build a source-only MCP bundle from an explicit file allowlist."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json
root = Path(__file__).resolve().parent.parent
version = json.loads((root / "manifest.json").read_text())["version"]
out = root / "dist" / f"docket-lens-{version}.mcpb"
out.parent.mkdir(exist_ok=True)
files = [root / n for n in ("manifest.json", "pyproject.toml", "LICENSE", "README.md")]
files += sorted((root / "regintel_mcp").glob("*.py"))
for folder in ("commands", "skills"):
    files += sorted((root / folder).rglob("*.md"))
with ZipFile(out, "w", ZIP_DEFLATED) as bundle:
    for file in files:
        bundle.write(file, file.relative_to(root))
print(out)
print("SHA256", hashlib.sha256(out.read_bytes()).hexdigest())
