from pathlib import Path


BAD_SEQUENCES = [
    "\u00c3",  # Common mojibake prefix from UTF-8 interpreted as latin-1
    "\u00c2",  # Common mojibake prefix from UTF-8 interpreted as latin-1
    "\ufffd",  # Replacement character
    "?ltimo",
    "? Todos",
    "Inversi?n",
    "Pa?s",
    "Exposici?n",
]

TEXT_EXTENSIONS = {".py", ".html", ".md", ".txt", ".css", ".js"}


def _iter_project_text_files():
    root = Path(__file__).resolve().parents[3]
    current_test_file = Path(__file__).resolve()
    for base in (root / "apps", root / "templates"):
        for path in base.rglob("*"):
            if (
                path.is_file()
                and path.suffix in TEXT_EXTENSIONS
                and "migrations" not in path.parts
                and path.resolve() != current_test_file
            ):
                yield path


def test_no_mojibake_sequences_in_project_texts():
    offenders = []
    for path in _iter_project_text_files():
        content = path.read_text(encoding="utf-8")
        for token in BAD_SEQUENCES:
            if token in content:
                offenders.append(f"{path}: '{token}'")
                break

    assert not offenders, "Mojibake/text encoding issues detected:\n" + "\n".join(offenders)
