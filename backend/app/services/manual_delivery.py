"""Human-readable delivery formats; never submit to an external channel."""

import csv
import io


def delivery_csv(fields: list[tuple[str, str]]) -> str:
    # Every data cell is a literal, including leading controls and full-width formulas.
    # csv.writer prevents embedded separators/quotes from creating unprotected cells.
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
    writer.writerow([name for name, _ in fields])
    writer.writerow(["'" + value for _, value in fields])
    return "\ufeff" + buffer.getvalue()


def delivery_text(fields: list[tuple[str, str]]) -> str:
    return "\n\n".join(f"{name}：\n{value}" for name, value in fields)
