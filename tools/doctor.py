"""Read-only runtime checks; no package installation or credential printing."""
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    python_ok = sys.version_info[:2] == (3, 12)
    print('Python 3.12:', 'OK' if python_ok else 'REQUIRED')
    core_ok = True
    for module in ('docx', 'reportlab', 'openpyxl', 'PIL', 'pypdf'):
        ok = importlib.util.find_spec(module) is not None
        core_ok &= ok
        print(module + ':', 'OK' if ok else 'MISSING')
    path = ROOT / '.local/runtime.json'
    runtime = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    for name in ('node', 'playwright_module', 'chromium', 'psql', 'font_regular', 'font_bold', 'pdftoppm', 'docx_renderer'):
        print(name + ':', 'CONFIGURED' if runtime.get(name) and Path(runtime[name]).exists() else 'OPTIONAL / NOT CONFIGURED')
    print('External tool presence does not imply live DB, Word or Excel visual verification.')
    return 0 if python_ok and core_ok else 1


if __name__ == '__main__':
    sys.exit(main())
