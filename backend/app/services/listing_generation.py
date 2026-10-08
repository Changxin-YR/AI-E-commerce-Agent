from typing import Literal, Protocol

from app.schemas.listings import ListingContent


class ListingGenerator(Protocol):
    # Implementations receive text only, with no database, credentials, or tools.
    engine: Literal["local_template", "test_double"]

    def generate(self, name: str, facts: str) -> ListingContent: ...


class FactTemplateGenerator:
    engine: Literal["local_template", "test_double"] = "local_template"

    def generate(self, name: str, facts: str) -> ListingContent:
        return ListingContent(title=name, description=facts)


def get_listing_generator() -> ListingGenerator:
    return FactTemplateGenerator()


def check_content(name: str, facts: str, content: ListingContent) -> list[str]:
    """Conservative extraction checks, not a semantic or platform compliance claim."""
    fact_lines = {line.strip() for line in facts.splitlines() if line.strip()}
    title_parts = content.title.split(" · ")
    title_ok = content.title == name or (
        title_parts[0] == name and all(part in fact_lines for part in title_parts[1:])
    )
    blockers = []
    if not title_ok:
        blockers.append("标题须保留完整商品名；可用 ‘ · ’ 连接完整参数行。新增事实请先补充来源。")
    if any(
        line.strip() not in fact_lines | {name}
        for line in content.description.splitlines()
        if line.strip()
    ):
        blockers.append(
            "描述包含来源未覆盖的文字。请选用完整商品名或完整参数行，或先补充商品来源。"
        )
    return blockers
