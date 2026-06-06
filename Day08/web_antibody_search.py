from __future__ import annotations

import csv
import io
import re
import urllib.error
from html import escape
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from antibody_processing import OUTPUT_COLUMNS, SPECIES_OPTIONS, write_excel_results, write_results
from data_sources import (
    count_pubmed_references,
    fetch_iedb_antigen_aliases,
    fetch_ncbi_gene_aliases,
    load_antibody_table,
)
from multi_source_search import search_all_sources

SAFE_QUERY_RE = re.compile(r"^[A-Za-z0-9 ._\-/()]+$")
MAX_QUERY_LENGTH = 100
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

app = FastAPI(
    title="Antibody Target Search API",
    description="Search therapeutic antibodies against a cancer target using Thera-SAbDab, IEDB, PLAbDab and Lens PatSeq.",
)

app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent / "static"), name="static")


def is_safe_target_query(target_query: str) -> bool:
    """Validate target text and reject dangerous or overly long input."""
    query = target_query.strip()
    if not query or len(query) > MAX_QUERY_LENGTH:
        return False
    return bool(SAFE_QUERY_RE.fullmatch(query))


def normalize_species_filters(species_filters: list[str] | None) -> list[str]:
    """Keep only safe species/type filter values."""
    if not species_filters:
        return []
    return [value for value in species_filters if is_safe_target_query(value)]


def safe_count_pubmed_references(antibody_name: str) -> int:
    """Count PubMed mentions, but return zero if the service is unavailable."""
    try:
        return count_pubmed_references(antibody_name)
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError, RuntimeError):
        return 0


def safe_fetch_gene_aliases(target_query: str) -> list[str]:
    """Fetch gene aliases from NCBI and IEDB, with a fallback to the query itself."""
    seed_aliases = [target_query]
    aliases = [*seed_aliases]

    try:
        aliases = fetch_ncbi_gene_aliases(target_query, seed_aliases=seed_aliases)
    except Exception:
        aliases = [*seed_aliases]

    try:
        iedb_aliases = fetch_iedb_antigen_aliases(target_query, seed_aliases=aliases)
        aliases = list(dict.fromkeys([*aliases, *iedb_aliases]))
    except Exception:
        aliases = list(dict.fromkeys(aliases))

    return aliases or seed_aliases


def save_output_files(rows: list[dict[str, str | int]], output_dir: Path) -> tuple[Path, Path]:
    """Write a CSV and Excel copy to the local output folder."""
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "antibody_results.csv"
    excel_path = output_dir / "antibody_results.xlsx"
    write_results(csv_path, rows)
    write_excel_results(excel_path, rows)
    return csv_path, excel_path


def build_data_rows(rows: list[dict[str, str | int]]) -> list[dict[str, str | int]]:
    """Ensure every row contains the expected columns."""
    return [
        {column: row.get(column, "N.A") for column in OUTPUT_COLUMNS}
        for row in rows
    ]


def run_search(target_query: str, limit: int, species_filters: list[str]) -> tuple[list[dict[str, str | int]], list[str]]:
    """Search all sources and return processed antibody rows plus target aliases."""
    safe_query = target_query.strip()
    aliases = safe_fetch_gene_aliases(safe_query)
    rows = search_all_sources(
        therasabdab_loader=lambda: load_antibody_table(None),
        target_query=safe_query,
        target_aliases=aliases,
        limit=limit,
        reference_counter=safe_count_pubmed_references,
        species_filters=normalize_species_filters(species_filters),
    )
    return rows, aliases


def build_result_table_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>No matching antibodies were found.</p>"

    header_html = "".join(f"<th>{escape(column)}</th>" for column in OUTPUT_COLUMNS)
    rows_html = ""
    for row in rows:
        rows_html += "<tr>"
        for column in OUTPUT_COLUMNS:
            rows_html += f"<td>{escape(str(row.get(column, '')))}</td>"
        rows_html += "</tr>"

    return (
        "<table border=1 cellpadding=6 cellspacing=0>"
        "<thead><tr>" + header_html + "</tr></thead>"
        "<tbody>" + rows_html + "</tbody>"
        "</table>"
    )


def build_species_checkbox_html(selected: list[str] | None = None) -> str:
    selected_values = set(selected or [])
    checkbox_rows = ""
    for species in SPECIES_OPTIONS:
        checked = "checked" if species in selected_values else ""
        checkbox_rows += (
            "<label style='display:inline-block; margin-right:16px;'>"
            f"<input type='checkbox' name='species' value='{escape(species)}' {checked}> {escape(species)}"
            "</label>"
        )
    return f"<div class='checkbox-grid'>{checkbox_rows}</div>"


def build_html_page(
    target_query: str = "",
    limit: int = 20,
    species_filters: list[str] | None = None,
    result_html: str = "",
    aliases: list[str] | None = None,
    error_message: str | None = None,
) -> str:
    aliases_text = ", ".join(aliases or [])
    species_html = build_species_checkbox_html(species_filters)

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset='utf-8'>
    <title>Antibody Target Search</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; background: linear-gradient(180deg, rgba(255,255,255,0.12), rgba(255,255,255,0.16)), url('/static/images/background01.png'); background-size: cover; background-position: center; background-attachment: fixed; color: #1a1a1a; }}
        .page {{ max-width: 1200px; margin: auto; padding: 24px; }}
        .hero {{ background: rgba(255,255,255,0.96); padding: 32px; border-radius: 22px; box-shadow: 0 20px 55px rgba(31, 74, 189, 0.16); margin-bottom: 26px; position: relative; overflow: hidden; }}
        .hero::before {{ content: ''; position: absolute; top: -40px; right: -40px; width: 260px; height: 260px; background: rgba(45,108,255,0.12); border-radius: 50%; }}
        .hero h1 {{ margin-top: 0; font-size: 2.6rem; line-height: 1.05; }}
        .hero p {{ max-width: 700px; margin-bottom: 0; font-size: 1rem; color: #374151; }}
        .hero-graphic {{ position: absolute; top: 20px; right: 24px; width: 180px; height: 180px; opacity: 0.92; }}
        .notice {{ padding: 14px 18px; border-radius: 14px; margin-bottom: 18px; }}
        .error {{ background: #ffe7e7; color: #a00; }}
        .success {{ background: #e6f7e6; color: #116611; }}
        form {{ background: #ffffff; padding: 26px 30px 22px; border-radius: 18px; box-shadow: 0 16px 32px rgba(13, 31, 69, 0.08); }}
        label {{ display: block; margin: 14px 0 8px; font-weight: 700; color: #24303d; }}
        input[type=text], input[type=number] {{ width: 100%; max-width: 560px; padding: 12px 16px; border: 1px solid #d7dae0; border-radius: 12px; font-size: 16px; }}
        button {{ padding: 14px 32px; color: white; background: #2d6cff; border: none; border-radius: 12px; cursor: pointer; font-size: 16px; font-weight: 700; }}
        button:hover {{ background: #1f52d5; }}
        .checkbox-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; margin-top: 8px; padding: 12px 12px 8px; border: 1px solid #d7dae0; border-radius: 14px; background: #fbfbfd; }}
        .checkbox-grid label {{ display: inline-flex; align-items: center; margin: 0; font-weight: 500; color: #2d3748; }}
        .checkbox-grid input {{ margin-right: 10px; accent-color: #2d6cff; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; background: white; border-radius: 14px; overflow: hidden; box-shadow: 0 12px 28px rgba(0,0,0,0.08); }}
        th, td {{ border-bottom: 1px solid #e8eaef; padding: 14px 16px; text-align: left; }}
        th {{ background: #eff4ff; font-weight: 700; color: #22356f; }}
        tr:hover td {{ background: #f8fbff; }}
        .result-card {{ margin-top: 26px; }}
        .links {{ margin-top: 18px; }}
        .meta {{ margin-top: 10px; color: #555; }}
        .api-hint {{ margin-top: 26px; font-size: 14px; color: #4b5563; }}
    </style>
</head>
<body>
    <div class='page'>
        <div class='hero'>
            <div style='display:flex; align-items:center; gap:18px;'>
                <img src='/static/images/logo.png' alt='App logo' style='height:84px; width:auto;'>
                <div>
                    <h1>Antibody Target Search</h1>
                    <p>Search therapeutic antibodies against a cancer target using Thera-SAbDab, IEDB, PLAbDab and Lens PatSeq.</p>
                </div>
            </div>
        </div>

        {f"<div class='notice error'>{escape(error_message)}</div>" if error_message else ''}
        {f"<div class='notice success'>Target aliases used: {escape(aliases_text)}</div>" if aliases_text else ''}

        <form method='post' action='/search'>
            <label for='target'>Target antigen or gene</label>
            <input type='text' id='target' name='target' value='{escape(target_query)}' required maxlength='{MAX_QUERY_LENGTH}'>

            <label for='limit'>Max results</label>
            <input type='number' id='limit' name='limit' value='{limit}' min='1' max='100'>

            <label>Species / type filters</label>
            {species_html}

            <div style='margin-top: 22px;'>
                <button type='submit'>Run search</button>
            </div>
        </form>

        {f"<div class='result-card'>{result_html}<div class='links'><a href='/download/csv'>Download CSV</a> | <a href='/download/excel'>Download Excel</a></div></div>" if result_html else ''}

        <div class='api-hint'>For JSON results use <code>/api/search?target=PD1&amp;limit=20&amp;species=Human,Humanized</code>.</div>
    </div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(build_html_page())


@app.post("/search", response_class=HTMLResponse)
def search_form(
    target: str = Form(...),
    limit: int = Form(20),
    species: list[str] = Form([]),
) -> HTMLResponse:
    if not is_safe_target_query(target):
        return HTMLResponse(build_html_page(target_query=target, error_message="Unsupported target query."))

    species_filters = normalize_species_filters(species)

    try:
        rows, aliases = run_search(target, limit, species_filters)
    except Exception as error:
        return HTMLResponse(build_html_page(target_query=target, species_filters=species_filters, error_message=str(error)))

    table_html = build_result_table_html(rows)
    save_output_files(rows, OUTPUT_DIR)
    return HTMLResponse(build_html_page(target_query=target, limit=limit, species_filters=species_filters, result_html=table_html, aliases=aliases))


@app.get("/api/search", response_class=JSONResponse)
def api_search(
    target: str = Query(...),
    limit: int = Query(20, gt=0, lt=101),
    species: str = Query(""),
) -> Any:
    if not is_safe_target_query(target):
        raise HTTPException(status_code=400, detail="Unsupported target query.")

    species_filters = [value.strip() for value in species.split(",") if value.strip()]
    species_filters = normalize_species_filters(species_filters)

    try:
        rows, aliases = run_search(target, limit, species_filters)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    return {"target": target, "aliases": aliases, "results": rows}


@app.get("/download/{file_type}")
def download_file(file_type: str) -> FileResponse:
    if file_type == "csv":
        path = OUTPUT_DIR / "antibody_results.csv"
        media_type = "text/csv"
    elif file_type == "excel":
        path = OUTPUT_DIR / "antibody_results.xlsx"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        raise HTTPException(status_code=404, detail="File not found.")

    if not path.exists():
        raise HTTPException(status_code=404, detail="Result file not available. Run a search first.")

    return FileResponse(path, media_type=media_type, filename=path.name)
