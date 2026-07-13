"""Project-level constants for ImmunoFlow Discovery Analyzer."""

REQUIRED_EXCEL_SHEETS = [
    "Experiment_Info",
    "Acquisition_Processing",
    "Panel_Definition",
    "Plate_Map",
    "Gating_Workflow",
    "Marker_Gates",
    "Exploratory_Search",
    "Planned_Comparisons",
]

REQUIRED_COLUMNS = {
    "Panel_Definition": [
        "Parameter_in_FCS",
        "Fluorophore",
        "Marker",
        "Marker_role",
    ],
    "Plate_Map": [
        "Well",
        "Sample_ID",
        "Subject_ID",
        "Treatment",
        "Tissue",
        "Replicate",
        "FCS_File",
    ],
    "Gating_Workflow": [
        "Gate_Name",
        "Parent_Gate",
        "Gate_Type",
        "X_Parameter",
        "Y_Parameter",
        "Analysis_Role",
    ],
    "Marker_Gates": [
        "Marker",
        "Positive_Gate_Name",
        "Negative_Gate_Name",
        "Parent_Population",
        "Gate_Source",
    ],
    "Exploratory_Search": [
        "Search_ID",
        "Starting_Population",
        "Compare_Groups",
        "Reference_Group",
        "Minimum_Events",
    ],
    "Planned_Comparisons": [
        "Comparison_ID",
        "Population",
        "Parent_Population",
        "Treatment_Group",
        "Reference_Group",
        "Metric",
    ],
}

LOW_EVENT_COUNT_THRESHOLD = 1000
