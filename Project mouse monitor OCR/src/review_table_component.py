"""Custom Streamlit review table with Excel-like keyboard navigation."""

from typing import Any

import pandas as pd
import streamlit as st


_REVIEW_TABLE = st.components.v2.component(
    "mouse_monitor_review_table",
    html="""
    <div id="root"></div>
    """,
    css="""
    #root {
      width: 100%;
      font-family: sans-serif;
    }
    .review-table-shell {
      border: 1px solid rgba(49, 51, 63, 0.2);
      border-radius: 8px;
      overflow: auto;
      max-height: 65vh;
      background: white;
    }
    .review-table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 0.92rem;
    }
    .review-table thead th {
      position: sticky;
      top: 0;
      z-index: 2;
      background: #f6f7fb;
      border-bottom: 1px solid rgba(49, 51, 63, 0.18);
      text-align: left;
      padding: 0.5rem 0.55rem;
      font-weight: 600;
      white-space: nowrap;
    }
    .review-table td {
      border-bottom: 1px solid rgba(49, 51, 63, 0.1);
      padding: 0.3rem 0.35rem;
      vertical-align: top;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .review-table td.readonly-cell {
      white-space: nowrap;
    }
    .review-table td.wrap-cell {
      white-space: normal;
      line-height: 1.35;
    }
    .review-input {
      width: 100%;
      min-width: 0;
      box-sizing: border-box;
      border: 1px solid rgba(49, 51, 63, 0.2);
      border-radius: 4px;
      padding: 0.36rem 0.42rem;
      background: white;
      color: inherit;
      font: inherit;
    }
    .review-input:focus {
      outline: 2px solid rgba(52, 102, 246, 0.22);
      border-color: rgba(52, 102, 246, 0.55);
    }
    .review-table tbody tr:hover td {
      background: rgba(49, 51, 63, 0.02);
    }
    .review-table tbody tr:hover td .review-input {
      background: inherit;
    }
    .column-source_image { width: 12rem; }
    .column-cage_number { width: 5rem; }
    .column-mouse_id { width: 7rem; }
    .column-ear_marking { width: 7rem; }
    .column-W, .column-L, .column-Weight { width: 6rem; }
    .column-warnings { width: 22rem; }
    .column-requires_manual_review { width: 7rem; }
    """,
    js="""
    export default function (component) {
      const { parentElement, data, setStateValue } = component
      const root = parentElement.querySelector("#root")
      if (!root) return

      const state =
        parentElement.__reviewTableState ??
        (parentElement.__reviewTableState = {
          rows: [],
          rowsJson: "",
          sequenceStartColumn: null,
          keyboardSequenceActive: false,
        })

      const editableColumns = Array.isArray(data?.editable_columns)
        ? data.editable_columns
        : []
      const visibleColumns = Array.isArray(data?.visible_columns)
        ? data.visible_columns
        : []
      const columnLabels = data?.column_labels ?? {}
      const cellBackgrounds = Array.isArray(data?.cell_backgrounds)
        ? data.cell_backgrounds
        : []
      const incomingRows = Array.isArray(data?.rows) ? data.rows : []
      const incomingRowsJson = JSON.stringify(incomingRows)

      if (state.rowsJson !== incomingRowsJson) {
        state.rows = JSON.parse(incomingRowsJson)
        state.rowsJson = incomingRowsJson
        render()
      } else if (!root.firstChild) {
        render()
      }

      function emitRows() {
        state.rowsJson = JSON.stringify(state.rows)
        setStateValue("rows", state.rows)
      }

      function normalizeDisplayValue(columnKey, value) {
        if (value === null || value === undefined) {
          return ""
        }
        if (["W", "L", "Weight"].includes(columnKey)) {
          const numericValue =
            typeof value === "number" ? value : Number.parseFloat(String(value))
          return Number.isFinite(numericValue) ? numericValue.toFixed(2) : String(value)
        }
        if (columnKey === "requires_manual_review") {
          return value ? "Yes" : ""
        }
        return String(value)
      }

      function normalizeNumericText(rawValue) {
        const trimmed = String(rawValue ?? "").trim()
        if (!trimmed) {
          return ""
        }
        const normalized = trimmed.replace(",", ".")
        if (!/^-?(?:\\d+|\\d+\\.\\d*|\\.\\d+)$/.test(normalized)) {
          return null
        }
        const parsed = Number.parseFloat(normalized)
        return Number.isFinite(parsed) ? parsed.toFixed(2) : null
      }

      function setRowValue(rowIndex, columnKey, displayValue) {
        if (!state.rows[rowIndex]) return
        state.rows[rowIndex][columnKey] =
          displayValue === "" ? null : displayValue
      }

      function focusCell(rowIndex, columnKey) {
        const selector =
          `[data-row-index="${rowIndex}"][data-column-key="${columnKey}"]`
        const target = root.querySelector(selector)
        if (!target) return
        target.focus()
        if (typeof target.select === "function") {
          target.select()
        }
      }

      function nextEditableColumn(currentColumnKey, direction) {
        const currentIndex = editableColumns.indexOf(currentColumnKey)
        if (currentIndex === -1) {
          return null
        }
        const targetIndex = currentIndex + direction
        if (targetIndex < 0 || targetIndex >= editableColumns.length) {
          return null
        }
        return editableColumns[targetIndex]
      }

      function handleKeyboardMove(event, rowIndex, columnKey) {
        if (event.key === "Tab") {
          event.preventDefault()
          state.keyboardSequenceActive = true
          if (!state.sequenceStartColumn) {
            state.sequenceStartColumn = columnKey
          }
          const direction = event.shiftKey ? -1 : 1
          const nextColumn = nextEditableColumn(columnKey, direction)
          if (nextColumn) {
            focusCell(rowIndex, nextColumn)
            return
          }
          const nextRowIndex = rowIndex + direction
          if (nextRowIndex < 0 || nextRowIndex >= state.rows.length) {
            return
          }
          const fallbackColumn =
            direction > 0
              ? state.sequenceStartColumn ?? editableColumns[0]
              : state.sequenceStartColumn ?? editableColumns.at(-1)
          focusCell(nextRowIndex, fallbackColumn)
          return
        }

        if (event.key === "Enter") {
          event.preventDefault()
          state.keyboardSequenceActive = true
          if (!state.sequenceStartColumn) {
            state.sequenceStartColumn = columnKey
          }
          const nextRowIndex = rowIndex + 1
          if (nextRowIndex >= state.rows.length) {
            return
          }
          focusCell(nextRowIndex, state.sequenceStartColumn)
        }
      }

      function render() {
        root.innerHTML = ""

        const shell = document.createElement("div")
        shell.className = "review-table-shell"

        const table = document.createElement("table")
        table.className = "review-table"

        const thead = document.createElement("thead")
        const headerRow = document.createElement("tr")
        visibleColumns.forEach(columnKey => {
          const th = document.createElement("th")
          th.className = `column-${columnKey}`
          th.textContent = columnLabels[columnKey] ?? columnKey
          headerRow.appendChild(th)
        })
        thead.appendChild(headerRow)
        table.appendChild(thead)

        const tbody = document.createElement("tbody")
        state.rows.forEach((row, rowIndex) => {
          const tr = document.createElement("tr")
          const backgroundMap = cellBackgrounds[rowIndex] ?? {}

          visibleColumns.forEach(columnKey => {
            const td = document.createElement("td")
            td.className = `column-${columnKey} ${
              columnKey === "warnings" ? "wrap-cell" : "readonly-cell"
            }`
            if (backgroundMap[columnKey]) {
              td.style.backgroundColor = backgroundMap[columnKey]
            }

            if (editableColumns.includes(columnKey)) {
              const input = document.createElement("input")
              input.className = "review-input"
              input.type = columnKey === "mouse_id" ? "text" : "text"
              input.inputMode = columnKey === "mouse_id" ? "text" : "decimal"
              input.value = normalizeDisplayValue(columnKey, row[columnKey])
              input.dataset.rowIndex = String(rowIndex)
              input.dataset.columnKey = columnKey
              input.dataset.previousValue = input.value
              if (backgroundMap[columnKey]) {
                input.style.backgroundColor = backgroundMap[columnKey]
              }

              input.addEventListener("focus", () => {
                if (!state.keyboardSequenceActive) {
                  state.sequenceStartColumn = columnKey
                }
                input.dataset.previousValue = input.value
              })
              input.addEventListener("mousedown", () => {
                state.sequenceStartColumn = columnKey
                state.keyboardSequenceActive = false
              })
              input.addEventListener("input", () => {
                setRowValue(rowIndex, columnKey, input.value)
                emitRows()
              })
              input.addEventListener("blur", () => {
                if (columnKey === "mouse_id") {
                  const trimmed = input.value.trim()
                  input.value = trimmed
                  setRowValue(rowIndex, columnKey, trimmed)
                  emitRows()
                  input.dataset.previousValue = input.value
                  return
                }

                const normalized = normalizeNumericText(input.value)
                if (normalized === null) {
                  input.value = input.dataset.previousValue ?? ""
                } else {
                  input.value = normalized
                }
                setRowValue(rowIndex, columnKey, input.value)
                emitRows()
                input.dataset.previousValue = input.value
              })
              input.addEventListener("keydown", event => {
                handleKeyboardMove(event, rowIndex, columnKey)
              })

              td.appendChild(input)
            } else {
              td.textContent = normalizeDisplayValue(columnKey, row[columnKey])
            }

            tr.appendChild(td)
          })

          tbody.appendChild(tr)
        })

        table.appendChild(tbody)
        shell.appendChild(table)
        root.appendChild(shell)
      }
    }
    """,
)


def render_review_table(
    rows: pd.DataFrame,
    *,
    key: str,
    visible_columns: list[str],
    editable_columns: list[str],
    column_labels: dict[str, str],
    cell_backgrounds: list[dict[str, str]],
) -> pd.DataFrame:
    """Render the custom review table and return the latest edited rows."""
    serialized_rows = _serialize_rows(rows)
    component_state = st.session_state.get(key, {})
    current_rows = component_state.get("rows", serialized_rows)
    _REVIEW_TABLE(
        key=key,
        data={
            "rows": current_rows,
            "visible_columns": visible_columns,
            "editable_columns": editable_columns,
            "column_labels": column_labels,
            "cell_backgrounds": cell_backgrounds,
        },
        default={"rows": current_rows},
        on_rows_change=lambda: None,
    )
    latest_rows = st.session_state.get(key, {}).get("rows", current_rows)
    return pd.DataFrame(latest_rows, columns=list(rows.columns))


def _serialize_rows(rows: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame into JSON-safe row dictionaries."""
    serialized: list[dict[str, Any]] = []
    for _, row in rows.iterrows():
        serialized.append(
            {
                column: _serialize_value(row[column])
                for column in rows.columns
            }
        )
    return serialized


def _serialize_value(value: Any) -> Any:
    """Convert pandas scalar values to JSON-safe builtins."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value
