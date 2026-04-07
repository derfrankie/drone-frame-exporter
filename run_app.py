from __future__ import annotations

import site
import sys
from pathlib import Path


def _bootstrap() -> None:
    repo_dir = Path(__file__).resolve().parent
    src_dir = repo_dir / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    for site_packages in sorted((repo_dir / ".venv" / "lib").glob("python*/site-packages")):
        site.addsitedir(str(site_packages))


def main() -> int:
    _bootstrap()
    from app.main import main as app_main

    return app_main()


if __name__ == "__main__":
    raise SystemExit(main())
