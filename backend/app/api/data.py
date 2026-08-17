from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.data_export import (
    TABLE_FILTERS,
    TABLE_MODELS,
    count_table_rows,
    fetch_table_rows,
    list_export_tables,
    rows_to_csv,
)

router = APIRouter(prefix="/api/data", tags=["data"])

MAX_LIMIT = 100_000
DEFAULT_LIMIT = 10_000


@router.get("/tables")
async def list_tables() -> dict[str, Any]:
    return {"tables": list_export_tables()}


@router.get("/{table}")
async def export_table(
    table: str,
    request: Request,
    format: Literal["json", "csv"] = Query(default="json"),
    meta: bool = Query(default=False, description="When format=json, wrap rows with pagination metadata"),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    include_total: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> Any:
    if table not in TABLE_MODELS:
        raise HTTPException(status_code=404, detail=f"Unknown table: {table}")

    allowed_filters = TABLE_FILTERS.get(table, ())
    filters: dict[str, str] = {}
    for name in allowed_filters:
        value = request.query_params.get(name)
        if value is not None and value != "":
            filters[name] = value

    try:
        rows, inferred_total = await fetch_table_rows(
            db,
            table,
            limit=limit,
            offset=offset,
            filters=filters,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    total_count = inferred_total
    if include_total and total_count is None:
        total_count = await count_table_rows(db, table, filters)

    if format == "csv":
        return PlainTextResponse(
            content=rows_to_csv(rows),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{table}.csv"'},
        )

    if not meta:
        return JSONResponse(content=rows)

    payload: dict[str, Any] = {
        "table": table,
        "limit": limit,
        "offset": offset,
        "count": len(rows),
        "rows": rows,
    }
    if total_count is not None:
        payload["total_count"] = total_count
    if filters:
        payload["filters"] = filters

    return JSONResponse(content=payload)
