"""Schemas pydantic: envelope de resposta e modelos de validação."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorInfo(BaseModel):
    code: str
    message: str
    details: Any = None


class ToolResult(BaseModel):
    """Envelope de TODA ferramenta: {ok, data, warnings, error}."""

    ok: bool
    data: Any = None
    warnings: list[str] = Field(default_factory=list)
    error: ErrorInfo | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class PageInfo(BaseModel):
    total: int
    offset: int
    limit: int
    returned: int
    has_more: bool
    next_offset: int | None = None

    @classmethod
    def build(cls, total: int, offset: int, limit: int, returned: int) -> PageInfo:
        end = offset + returned
        more = end < total
        return cls(total=total, offset=offset, limit=limit, returned=returned,
                   has_more=more, next_offset=end if more else None)


class RowSpec(BaseModel):
    """Uma linha de planilha já normalizada (import_blocks_from_excel)."""

    row: int
    block: str | None = None
    x: float | None = None
    y: float | None = None
    z: float | None = None
    rotation: float = 0.0
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    layer: str | None = None
    handle: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)

    @property
    def has_position(self) -> bool:
        return self.x is not None and self.y is not None

    @property
    def point(self) -> tuple[float, float, float]:
        return (self.x or 0.0, self.y or 0.0, self.z or 0.0)
