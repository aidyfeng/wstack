"""Assert every skill folder is a loadable SKILL.md whose name matches the folder."""
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parents[1] / "skills"
errors = []
dirs = sorted(p for p in root.iterdir() if p.is_dir())
if not dirs:
    errors.append("skills/ is empty")
for folder in dirs:
    skill = folder / "SKILL.md"
    if not skill.is_file():
        errors.append(f"{folder.name}: missing SKILL.md")
        continue
    text = skill.read_text(encoding="utf-8")
    match = re.search(r"^name:\s*(\S+)\s*$", text, re.M)
    if not match:
        errors.append(f"{folder.name}: SKILL.md has no name")
    elif match.group(1) != folder.name:
        errors.append(f"{folder.name}: name is {match.group(1)}")
    if not re.search(r"^description:\s*", text, re.M):
        errors.append(f"{folder.name}: SKILL.md has no description")
if errors:
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)
print(f"{len(dirs)} skills ok")
