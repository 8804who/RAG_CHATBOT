"""Move AGENT_WORKLOG / CODE_REVIEW_LOG entries whose tasks are all COMPLETED into archive/.

Keeps the live logs small so agents grep/read less. Entries are `### ...` blocks after the
records heading; an entry's tasks are every T-xxx in its heading (T-002~T-007 counts both ends).
Entries with no task id, or any task not COMPLETED on TASK_BOARD.md (including VERIFY_BLOCKED), stay.

Run from anywhere:  python3 docs/harness/archive_logs.py [--dry-run]
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
LOGS = {"AGENT_WORKLOG.md": "## Records", "CODE_REVIEW_LOG.md": "## Review records"}
TASK = re.compile(r"T-\d{3}")


def completed_tasks(board: str) -> set[str]:
    done = set()
    for line in board.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) > 2 and TASK.fullmatch(cells[1]) and "COMPLETED" in cells:
            done.add(cells[1])
    return done


def split(text: str, records_heading: str) -> tuple[str, list[str]]:
    head, sep, body = text.partition(records_heading + "\n")
    if not sep:
        return text, []
    parts = re.split(r"(?m)^(?=### )", body)
    return head + sep + parts[0], [p for p in parts[1:] if p.strip()]


def archivable(entry: str, done: set[str]) -> bool:
    ids = TASK.findall(entry.splitlines()[0])
    return bool(ids) and all(i in done for i in ids)


def main(dry: bool) -> None:
    done = completed_tasks((HERE / "TASK_BOARD.md").read_text())
    (HERE / "archive").mkdir(exist_ok=True)
    for name, heading in LOGS.items():
        live = HERE / name
        head, entries = split(live.read_text(), heading)
        keep = [e for e in entries if not archivable(e, done)]
        move = [e for e in entries if archivable(e, done)]
        print(f"{name}: archive {len(move)}, keep {len(keep)}")
        if dry or not move:
            continue
        arc = HERE / "archive" / name
        prev = arc.read_text() if arc.exists() else f"# {name} archive (COMPLETED tasks)\n\n"
        arc.write_text(prev + "".join(e if e.endswith("\n") else e + "\n" for e in move))
        live.write_text(head + "".join(keep))


def _selfcheck() -> None:
    board = "| T-001 | a | x | COMPLETED |\n| T-002 | b | x | IN_PROGRESS |\n"
    done = completed_tasks(board)
    assert done == {"T-001"}, done
    head, entries = split("# L\n## Records\n\nintro\n### d · T-001\nx\n### d · T-001~T-002\ny\n### d · note\nz\n", "## Records")
    assert head.endswith("intro\n") and len(entries) == 3, (head, entries)
    assert [archivable(e, done) for e in entries] == [True, False, False]


if __name__ == "__main__":
    _selfcheck()
    main("--dry-run" in sys.argv)
