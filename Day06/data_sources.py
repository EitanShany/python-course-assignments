"""Website access functions for the Day06 antibody assignment."""

from __future__ import annotations

import csv
import io
import re
import ssl
import urllib.request
from pathlib import Path

from Bio import Entrez
from openpyxl import load_workbook


THERASABDAB_CSV_URL = (
    "https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/static/downloads/"
    "TheraSAbDab_SeqStruc_OnlineDownload.csv"
)

Entrez.email = "student@example.com"
Entrez.tool = "python-course-antibody-analysis"
Entrez.max_tries = 1
Entrez.sleep_between_tries = 0

ALIAS_OUTPUT_FILE = Path(__file__).with_name("target_aliases.txt")


def open_url(request: urllib.request.Request, timeout: int = 30):
    """Open a URL, with a certificate fallback for course lab computers."""
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.URLError as error:
        if "CERTIFICATE_VERIFY_FAILED" not in str(error):
            raise

        insecure_context = ssl._create_unverified_context()
        return urllib.request.urlopen(request, timeout=timeout, context=insecure_context)


def download_therasabdab_table() -> list[dict[str, str]]:
    """Download and parse the public Thera-SAbDab antibody CSV table."""
    request = urllib.request.Request(
        THERASABDAB_CSV_URL,
        headers={"User-Agent": "python-course-antibody-analysis/1.0"},
    )

    with open_url(request, timeout=30) as response:
        csv_text = response.read().decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(csv_text))
    return list(reader)


def load_csv_table(file_path: Path) -> list[dict[str, str]]:
    """Load antibody data from a local CSV file."""
    with file_path.open(newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        return list(reader)


def load_excel_table(file_path: Path) -> list[dict[str, str]]:
    """Load antibody data from a local Excel file."""
    workbook = load_workbook(file_path, read_only=True, data_only=True)
    try:
        worksheet = workbook.active
        rows = list(worksheet.iter_rows(values_only=True))
        if not rows:
            return []

        headers = [str(header) if header is not None else "" for header in rows[0]]
        table_rows: list[dict[str, str]] = []
        for row in rows[1:]:
            table_rows.append(
                {
                    headers[index]: "" if value is None else str(value)
                    for index, value in enumerate(row)
                    if index < len(headers) and headers[index]
                }
            )
        return table_rows
    finally:
        workbook.close()


def load_antibody_table(file_path: Path | None = None) -> list[dict[str, str]]:
    """Load antibody rows from a local CSV/XLSX file or download Thera-SAbDab."""
    if file_path is None:
        return download_therasabdab_table()

    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return load_csv_table(file_path)
    if suffix in {".xlsx", ".xlsm"}:
        return load_excel_table(file_path)
    raise ValueError("Input file must be a CSV or XLSX file.")


def count_pubmed_references(antibody_name: str) -> int:
    """Count PubMed papers mentioning an antibody name using Biopython."""
    search_term = f'"{antibody_name}"[Title/Abstract]'

    insecure_context = ssl._create_unverified_context()
    previous_urlopen = Entrez.urlopen
    Entrez.urlopen = lambda request: urllib.request.urlopen(
        request,
        context=insecure_context,
    )
    try:
        with Entrez.esearch(
            db="pubmed",
            term=search_term,
            retmode="xml",
            retmax=0,
        ) as handle:
            record = Entrez.read(handle)
    finally:
        Entrez.urlopen = previous_urlopen

    return int(record["Count"])


def read_entrez_record(search_function, **kwargs):
    """Run a Biopython Entrez request with SSL handling for course computers."""
    insecure_context = ssl._create_unverified_context()
    previous_urlopen = Entrez.urlopen
    Entrez.urlopen = lambda request: urllib.request.urlopen(
        request,
        context=insecure_context,
    )
    try:
        with search_function(**kwargs) as handle:
            return Entrez.read(handle)
    finally:
        Entrez.urlopen = previous_urlopen


def fetch_ncbi_gene_aliases(
    target_query: str,
    seed_aliases: list[str] | None = None,
    max_genes: int = 5,
) -> list[str]:
    """Fetch human gene aliases from NCBI Gene using Biopython."""
    seed_aliases = seed_aliases or [target_query]
    search_term = f'("{target_query}"[All Fields]) AND "Homo sapiens"[Organism]'
    search_record = read_entrez_record(
        Entrez.esearch,
        db="gene",
        term=search_term,
        retmode="xml",
        retmax=max_genes,
    )

    gene_ids = search_record.get("IdList", [])
    if not gene_ids:
        return seed_aliases

    summary_record = read_entrez_record(
        Entrez.esummary,
        db="gene",
        id=",".join(gene_ids),
        retmode="xml",
    )

    aliases: list[str] = [target_query]
    for document in summary_record["DocumentSummarySet"]["DocumentSummary"]:
        if not document_matches_seed_aliases(document, seed_aliases):
            continue
        for field in ("Name", "Description", "OtherAliases", "OtherDesignations"):
            value = str(document.get(field, ""))
            if not value:
                continue
            for alias in value.replace("|", ",").split(","):
                alias = alias.strip()
                if alias:
                    aliases.append(alias)

    aliases = list(dict.fromkeys(aliases))
    return aliases or seed_aliases


def write_target_aliases(target_query: str, aliases: list[str]) -> Path:
    """Save aliases used for the current search to a text file."""
    with ALIAS_OUTPUT_FILE.open("w", encoding="utf-8") as alias_file:
        alias_file.write(f"Target query: {target_query}\n")
        alias_file.write("Aliases used for search:\n")
        for alias in aliases:
            alias_file.write(f"- {alias}\n")
    return ALIAS_OUTPUT_FILE


def normalize_alias(value: str) -> str:
    """Normalize alias text before comparing NCBI Gene records."""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def document_matches_seed_aliases(document, seed_aliases: list[str]) -> bool:
    """Keep only NCBI Gene records that match the user's target or known aliases."""
    normalized_seeds = {normalize_alias(alias) for alias in seed_aliases if alias}
    document_values = []
    for field in ("Name", "Description", "OtherAliases", "OtherDesignations"):
        value = str(document.get(field, ""))
        document_values.extend(value.replace("|", ",").split(","))

    normalized_values = {normalize_alias(value.strip()) for value in document_values if value.strip()}
    return bool(normalized_seeds & normalized_values)
