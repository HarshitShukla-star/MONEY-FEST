"""Allow running the CLI as ``python -m content_pipeline``."""

from content_pipeline.app.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
