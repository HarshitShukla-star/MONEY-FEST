# Development guidelines

Use Python 3.12+, format code consistently, and keep public functions fully typed. Run `ruff check .`, `mypy`, and `pytest` before opening a change.

Business rules must remain independent of frameworks and remote services. Define interfaces with `typing.Protocol` at the consuming boundary and inject implementations at the composition root. Raise a meaningful exception or return `Result`; never swallow an error. Do not log secrets or personal data.
