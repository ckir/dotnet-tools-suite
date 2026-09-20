import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

POLYFORM_HEADER = """Copyright (c) 2026 Hellen
Licensed under the PolyForm Noncommercial License 1.0.0
"""

COMMENT_STYLES = {
    ".cs": "// ",
    ".ps1": "# ",
    ".psm1": "# ",
    ".yml": "# ",
    ".yaml": "# ",
    ".md": "<!-- ",
    ".toml": "# ",
    ".xml": "<!-- ",
    ".props": "<!-- ",
    ".targets": "<!-- ",
}
# NOTE: .json intentionally excluded — JSON has no comment syntax,
# so injecting "// ..." headers makes files invalid.

def make_header(ext):
    style = COMMENT_STYLES.get(ext)
    if style == "<!-- ":
        return f"<!--\n{POLYFORM_HEADER}\n-->\n\n"
    elif style == "// ":
        return "\n".join([f"// {line}" for line in POLYFORM_HEADER.splitlines()]) + "\n\n"
    elif style == "# ":
        return "\n".join([f"# {line}" for line in POLYFORM_HEADER.splitlines()]) + "\n\n"
    else:
        return POLYFORM_HEADER + "\n"

def should_process(path):
    _, ext = os.path.splitext(path)
    return ext in COMMENT_STYLES

def has_header(content):
    return "PolyForm Noncommercial License 1.0.0" in content

def inject_header(path):
    with open(path, "r", encoding="utf8") as f:
        content = f.read()

    if has_header(content):
        return False

    _, ext = os.path.splitext(path)
    header = make_header(ext)

    new_content = header + content

    with open(path, "w", encoding="utf8") as f:
        f.write(new_content)

    return True

def check_only():
    missing = []
    for root, dirs, files in os.walk(ROOT):
        for file in files:
            path = os.path.join(root, file)
            if should_process(path):
                with open(path, "r", encoding="utf8") as f:
                    content = f.read()
                if not has_header(content):
                    missing.append(path)

    if missing:
        print("Missing PolyForm headers:")
        for m in missing:
            print(" -", m)
        sys.exit(1)
    else:
        print("All files contain PolyForm headers.")
        sys.exit(0)

def walk_and_inject():
    changed = 0
    for root, dirs, files in os.walk(ROOT):
        for file in files:
            path = os.path.join(root, file)
            if should_process(path):
                if inject_header(path):
                    print(f"Injected header into: {path}")
                    changed += 1
    print(f"\nCompleted. Headers added to {changed} files.")

if __name__ == "__main__":
    if "--check" in sys.argv:
        check_only()
    else:
        walk_and_inject()

