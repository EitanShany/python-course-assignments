"""Graphical user interface for Pima Diabetes exploration and prediction."""
import json
import os
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from sklearn.decomposition import PCA
from sklearn.metrics import auc, roc_curve
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

os.environ.setdefault(
    "NUMBA_CACHE_DIR",
    str(Path(tempfile.gettempdir()) / "day09_numba_cache"),
)
from umap import UMAP

try:
    from .data_utils import (
        COLUMN_NAMES,
        FEATURE_NAMES,
        load_dataset,
        outcome_label,
        sample_from_mapping,
        validate_feature_frame,
    )
except ImportError:
    from data_utils import (
        COLUMN_NAMES,
        FEATURE_NAMES,
        load_dataset,
        outcome_label,
        sample_from_mapping,
        validate_feature_frame,
    )

BASE = Path(__file__).parent
DATA_PATH = BASE / "data" / "pima-indians-diabetes.csv"
MODEL_PATH = BASE / "models" / "classifier.joblib"
MAX_IMPORT_ROWS = 10_000
MAX_IMPORT_BYTES = 5_000_000
SCATTER_PAIRS = [
    ("Glucose", "BMI"),
    ("Glucose", "Age"),
    ("BMI", "Age"),
]


def connect_click_handler(fig, callback):
    """Replace the previous click callback instead of stacking callbacks."""
    old_connection = getattr(fig, "_day09_click_connection", None)
    if old_connection is not None:
        fig.canvas.mpl_disconnect(old_connection)
    fig._day09_click_connection = fig.canvas.mpl_connect(
        "button_press_event",
        callback,
    )


class CollapsibleSection(ttk.Frame):
    def __init__(self, parent, title, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.parent = parent
        self.title = title
        self.open = tk.BooleanVar(value=True)

        self.header = ttk.Frame(self)
        self.toggle_button = ttk.Checkbutton(
            self.header,
            text=title,
            variable=self.open,
            command=self.toggle,
            style="Toolbutton",
        )
        self.toggle_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.header.pack(fill=tk.X, pady=(8, 0))

        self.content = ttk.Frame(self)
        self.content.pack(fill=tk.BOTH, expand=True)

    def toggle(self):
        if self.open.get():
            self.content.pack(fill=tk.BOTH, expand=True)
        else:
            self.content.forget()


class DiabetesGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pima Diabetes Explorer")
        self.geometry("1200x900")
        self.extra_examples = pd.DataFrame(columns=FEATURE_NAMES)
        self.file_predictions = pd.DataFrame(
            columns=["Prediction", "DiabetesProbability"]
        )

        try:
            self.data = self.load_data()
        except (OSError, ValueError) as exc:
            messagebox.showerror("Dataset error", str(exc))
            self.destroy()
            raise SystemExit(1) from exc
        self.model = self.load_model()

        self.style = ttk.Style(self)
        self.style.configure("TLabel", font=(None, 10))
        self.style.configure("TButton", font=(None, 10))

        self.create_widgets()

    def load_data(self):
        return load_dataset(DATA_PATH)

    def load_model(self):
        if MODEL_PATH.exists():
            try:
                return joblib.load(MODEL_PATH)
            except (OSError, ValueError, EOFError, ImportError) as exc:
                messagebox.showwarning(
                    "Model error",
                    f"Could not load the saved model: {exc}",
                )
        return None

    def create_widgets(self):
        scroll_container = ttk.Frame(self)
        scroll_container.pack(fill=tk.BOTH, expand=True)

        self.scroll_canvas = tk.Canvas(
            scroll_container,
            highlightthickness=0,
        )
        scrollbar = ttk.Scrollbar(
            scroll_container,
            orient=tk.VERTICAL,
            command=self.scroll_canvas.yview,
        )
        self.scroll_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scroll_content = ttk.Frame(self.scroll_canvas)
        self.scroll_window = self.scroll_canvas.create_window(
            (0, 0),
            window=self.scroll_content,
            anchor=tk.NW,
        )
        self.scroll_content.bind(
            "<Configure>",
            self.update_scroll_region,
        )
        self.scroll_canvas.bind(
            "<Configure>",
            self.resize_scroll_content,
        )
        self.scroll_canvas.bind_all("<MouseWheel>", self.on_mouse_wheel)

        top_frame = ttk.Frame(self.scroll_content)
        top_frame.pack(fill=tk.X, padx=12, pady=8)

        explanation = (
            "הוסיפו דוגמאות חדשות ידנית או מקובץ, ואז רעננו את הגרפים.")
        ttk.Label(top_frame, text=explanation).pack(anchor=tk.W)

        self.create_example_input(top_frame)
        self.create_json_section(top_frame)

        container = ttk.Frame(self.scroll_content)
        container.pack(fill=tk.X, padx=12, pady=8)

        self.create_scatter_section(container)
        self.create_separation_section(container)
        self.create_correlation_section(container)
        self.create_pca_section(container)
        self.create_umap_section(container)
        self.create_importance_section(container)
        self.create_boxplot_section(container)
        self.create_prediction_table_section(container)

    def update_scroll_region(self, _event=None):
        self.scroll_canvas.configure(
            scrollregion=self.scroll_canvas.bbox("all"),
        )

    def resize_scroll_content(self, event):
        self.scroll_canvas.itemconfigure(
            self.scroll_window,
            width=event.width,
        )

    def on_mouse_wheel(self, event):
        if event.delta:
            self.scroll_canvas.yview_scroll(
                int(-event.delta / 120),
                "units",
            )

    def destroy(self):
        self.unbind_all("<MouseWheel>")
        super().destroy()

    def create_example_input(self, parent):
        frame = ttk.LabelFrame(parent, text="הוספת דוגמאות נוספות")
        frame.pack(fill=tk.X, pady=8)

        self.entries = {}
        for i, name in enumerate(FEATURE_NAMES):
            label = ttk.Label(frame, text=name)
            entry = ttk.Entry(frame, width=10)
            label.grid(row=0, column=i, padx=4, pady=4)
            entry.grid(row=1, column=i, padx=4, pady=4)
            self.entries[name] = entry

        add_button = ttk.Button(frame, text="הוסף דוגמה", command=self.add_sample)
        add_button.grid(row=2, column=0, columnspan=2, pady=8, sticky=tk.W)

        load_button = ttk.Button(frame, text="טען דוגמאות מקובץ CSV", command=self.load_samples_file)
        load_button.grid(row=2, column=2, columnspan=3, pady=8, sticky=tk.W)

        clear_button = ttk.Button(frame, text="נקה דוגמאות נוספות", command=self.clear_extra_examples)
        clear_button.grid(row=2, column=5, columnspan=2, pady=8, sticky=tk.W)

    def create_json_section(self, parent):
        frame = ttk.LabelFrame(parent, text="קלט JSON ומבחן מהיר")
        frame.pack(fill=tk.X, pady=8)

        json_label = ttk.Label(frame, text="JSON לדוגמה:")
        json_label.grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)

        self.json_text = tk.Text(frame, height=4, width=100)
        self.json_text.grid(row=1, column=0, columnspan=6, padx=4, pady=4)
        sample_json = {
            "Pregnancies": 2,
            "Glucose": 120,
            "BloodPressure": 70,
            "SkinThickness": 20,
            "Insulin": 85,
            "BMI": 30.5,
            "DiabetesPedigreeFunction": 0.55,
            "Age": 45,
        }
        self.json_text.insert(tk.END, json.dumps(sample_json, indent=2, ensure_ascii=False))

        ttk.Button(frame, text="חיזוי JSON", command=self.predict_json).grid(row=2, column=0, padx=4, pady=4, sticky=tk.W)
        ttk.Button(frame, text="הוסף JSON כדוגמא", command=self.add_json_sample).grid(row=2, column=1, padx=4, pady=4, sticky=tk.W)
        ttk.Button(frame, text="מבחן לחיצה אחת", command=self.one_click_sample).grid(row=2, column=2, padx=4, pady=4, sticky=tk.W)
        self.result_label = ttk.Label(frame, text="")
        self.result_label.grid(row=2, column=3, columnspan=3, sticky=tk.W, padx=4)

    def create_scatter_section(self, parent):
        section = CollapsibleSection(parent, "Scatter plots" )
        section.pack(fill=tk.BOTH, expand=True)

        text = (
            "גרפים של זוגות תכונות לפי Outcome. ניתן ללחוץ על כל גרף כדי לפתוח אותו בגדול."
        )
        ttk.Label(section.content, text=text).pack(anchor=tk.W, padx=4, pady=4)

        plots_frame = ttk.Frame(section.content)
        plots_frame.pack(fill=tk.BOTH, expand=True)

        self.scatter_canvases = []
        for i, (x, y) in enumerate(SCATTER_PAIRS):
            plot_frame = ttk.Frame(plots_frame)
            plot_frame.grid(row=0, column=i, sticky="nsew", padx=4, pady=4)
            plots_frame.columnconfigure(i, weight=1)
            fig, canvas = self.create_plot_canvas(plot_frame)
            self.scatter_canvases.append((fig, canvas, x, y))
            self.draw_scatter(fig, x, y)

        buttons_frame = ttk.Frame(section.content)
        buttons_frame.pack(fill=tk.X, pady=4)
        refresh = ttk.Button(buttons_frame, text="רענן גרפים", command=self.refresh_all)
        refresh.pack(side=tk.LEFT)
        save = ttk.Button(buttons_frame, text="שמור את כל Scatter כ־PNG", command=self.save_all_scatter)
        save.pack(side=tk.LEFT, padx=8)

    def create_correlation_section(self, parent):
        section = CollapsibleSection(parent, "Correlation heatmap")
        section.pack(fill=tk.BOTH, expand=True)
        text = "מפת קורלציה בין כל תכונה ליעד ולתכונות אחרות."
        ttk.Label(section.content, text=text).pack(anchor=tk.W, padx=4, pady=4)
        frame = ttk.Frame(section.content)
        frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        fig, self.corr_canvas = self.create_plot_canvas(frame)
        self.draw_correlation(fig)
        buttons = ttk.Frame(section.content)
        buttons.pack(fill=tk.X, pady=4)
        ttk.Button(buttons, text="שמור Heatmap", command=lambda: self.save_figure(fig, "correlation_heatmap.png")).pack(side=tk.LEFT)

    def create_separation_section(self, parent):
        section = CollapsibleSection(parent, "Model separation")
        section.pack(fill=tk.BOTH, expand=True)
        text = (
            "התפלגות הסיכון מציגה את החפיפה בין בריאים לחולי סוכרת. "
            "עקומת ROC מסכמת את יכולת ההפרדה של המודל בכל ספי ההחלטה."
        )
        ttk.Label(section.content, text=text).pack(anchor=tk.W, padx=4, pady=4)

        plots_frame = ttk.Frame(section.content)
        plots_frame.pack(fill=tk.BOTH, expand=True)
        plots_frame.columnconfigure(0, weight=1)
        plots_frame.columnconfigure(1, weight=1)

        risk_frame = ttk.Frame(plots_frame)
        risk_frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        risk_fig, self.risk_canvas = self.create_plot_canvas(risk_frame)
        self.draw_risk_distribution(risk_fig)

        roc_frame = ttk.Frame(plots_frame)
        roc_frame.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        roc_fig, self.roc_canvas = self.create_plot_canvas(roc_frame)
        self.draw_roc_curve(roc_fig)

        buttons = ttk.Frame(section.content)
        buttons.pack(fill=tk.X, pady=4)
        ttk.Button(
            buttons,
            text="שמור התפלגות סיכון",
            command=lambda: self.save_figure(
                risk_fig,
                "risk_distribution.png",
            ),
        ).pack(side=tk.LEFT)
        ttk.Button(
            buttons,
            text="שמור ROC",
            command=lambda: self.save_figure(roc_fig, "roc_curve.png"),
        ).pack(side=tk.LEFT, padx=8)

    def create_pca_section(self, parent):
        section = CollapsibleSection(parent, "PCA scatter plot")
        section.pack(fill=tk.BOTH, expand=True)
        text = "ניתוח PCA חזותי של שתי הרכיבים הראשונים עם צבע לפי Outcome."
        ttk.Label(section.content, text=text).pack(anchor=tk.W, padx=4, pady=4)
        frame = ttk.Frame(section.content)
        frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        fig, self.pca_canvas = self.create_plot_canvas(frame)
        self.draw_pca(fig)
        buttons = ttk.Frame(section.content)
        buttons.pack(fill=tk.X, pady=4)
        ttk.Button(buttons, text="שמור PCA", command=lambda: self.save_figure(fig, "pca_scatter.png")).pack(side=tk.LEFT)

    def create_umap_section(self, parent):
        section = CollapsibleSection(parent, "UMAP scatter plot")
        section.pack(fill=tk.BOTH, expand=True)
        text = (
            "UMAP projects the standardized features into two dimensions, "
            "with color based on Outcome."
        )
        ttk.Label(section.content, text=text).pack(
            anchor=tk.W,
            padx=4,
            pady=4,
        )
        frame = ttk.Frame(section.content)
        frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        fig, self.umap_canvas = self.create_plot_canvas(frame)
        self.draw_umap(fig)
        buttons = ttk.Frame(section.content)
        buttons.pack(fill=tk.X, pady=4)
        ttk.Button(
            buttons,
            text="שמור UMAP",
            command=lambda: self.save_figure(fig, "umap_scatter.png"),
        ).pack(side=tk.LEFT)

    def create_importance_section(self, parent):
        section = CollapsibleSection(parent, "Feature importance")
        section.pack(fill=tk.BOTH, expand=True)
        text = "גרף המראה את חשיבות התכונות לפי המודל."
        ttk.Label(section.content, text=text).pack(anchor=tk.W, padx=4, pady=4)
        frame = ttk.Frame(section.content)
        frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        fig, self.importance_canvas = self.create_plot_canvas(frame)
        self.draw_feature_importance(fig)
        buttons = ttk.Frame(section.content)
        buttons.pack(fill=tk.X, pady=4)
        ttk.Button(buttons, text="שמור Feature Importance", command=lambda: self.save_figure(fig, "feature_importance.png")).pack(side=tk.LEFT)

    def create_boxplot_section(self, parent):
        section = CollapsibleSection(parent, "Boxplot / Violin plot")
        section.pack(fill=tk.BOTH, expand=True)
        text = "השוואת חלוקות של תכונה אחת לפי Outcome. ניתן לבחור תצוגת Boxplot או Violin."
        ttk.Label(section.content, text=text).pack(anchor=tk.W, padx=4, pady=4)
        options_frame = ttk.Frame(section.content)
        options_frame.pack(fill=tk.X, padx=4, pady=4)
        ttk.Label(options_frame, text="בחר תכונה:").pack(side=tk.LEFT)
        self.box_feature = tk.StringVar(value="Glucose")
        opt = ttk.OptionMenu(options_frame, self.box_feature, "Glucose", *FEATURE_NAMES, command=self.refresh_boxplot)
        opt.pack(side=tk.LEFT, padx=8)
        ttk.Label(options_frame, text="סוג גרף:").pack(side=tk.LEFT, padx=(12, 0))
        self.box_plot_type = tk.StringVar(value="Boxplot")
        type_opt = ttk.OptionMenu(options_frame, self.box_plot_type, "Boxplot", "Boxplot", "Violin plot", command=self.refresh_boxplot)
        type_opt.pack(side=tk.LEFT, padx=8)
        ttk.Button(options_frame, text="רענן", command=self.refresh_boxplot).pack(side=tk.LEFT, padx=8)

        frame = ttk.Frame(section.content)
        frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        fig, self.box_canvas = self.create_plot_canvas(frame)
        self.draw_boxplot(fig, "Glucose")
        buttons = ttk.Frame(section.content)
        buttons.pack(fill=tk.X, pady=4)
        ttk.Button(buttons, text="שמור גרף", command=lambda: self.save_figure(fig, "box_violin.png")).pack(side=tk.LEFT)

    def create_prediction_table_section(self, parent):
        section = CollapsibleSection(parent, "Loaded File Predictions")
        section.pack(fill=tk.BOTH, expand=True)
        text = (
            "Predictions for CSV rows only. Manually entered and JSON "
            "examples are not included."
        )
        ttk.Label(section.content, text=text).pack(
            anchor=tk.W,
            padx=4,
            pady=4,
        )

        table_frame = ttk.Frame(section.content)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        columns = ("row", "prediction", "probability")
        self.prediction_table = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=10,
        )
        self.prediction_table.heading("row", text="Row")
        self.prediction_table.heading("prediction", text="Prediction")
        self.prediction_table.heading(
            "probability",
            text="Diabetes Probability",
        )
        self.prediction_table.column("row", width=70, anchor=tk.CENTER)
        self.prediction_table.column(
            "prediction",
            width=150,
            anchor=tk.CENTER,
        )
        self.prediction_table.column(
            "probability",
            width=180,
            anchor=tk.CENTER,
        )

        table_scrollbar = ttk.Scrollbar(
            table_frame,
            orient=tk.VERTICAL,
            command=self.prediction_table.yview,
        )
        self.prediction_table.configure(yscrollcommand=table_scrollbar.set)
        self.prediction_table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        table_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def predict_loaded_samples(self, samples):
        if self.model is None:
            return pd.DataFrame(
                {
                    "Prediction": ["Model unavailable"] * len(samples),
                    "DiabetesProbability": [np.nan] * len(samples),
                }
            )

        probabilities = self.model.predict_proba(samples)[:, 1]
        labels = self.model.predict(samples)
        return pd.DataFrame(
            {
                "Prediction": [outcome_label(label) for label in labels],
                "DiabetesProbability": probabilities,
            }
        )

    def update_prediction_table(self):
        for item_id in self.prediction_table.get_children():
            self.prediction_table.delete(item_id)

        for row_number, row in enumerate(
            self.file_predictions.itertuples(index=False),
            start=1,
        ):
            probability = (
                "N/A"
                if pd.isna(row.DiabetesProbability)
                else f"{row.DiabetesProbability:.3f}"
            )
            self.prediction_table.insert(
                "",
                tk.END,
                values=(row_number, row.Prediction, probability),
            )

    def create_plot_canvas(self, parent):
        fig = plt.Figure(figsize=(4, 3), dpi=100)
        canvas = FigureCanvasTkAgg(fig, master=parent)
        widget = canvas.get_tk_widget()
        widget.pack(fill=tk.BOTH, expand=True)
        return fig, canvas

    def draw_scatter(self, fig, x_feature, y_feature):
        fig.clf()
        ax = fig.add_subplot(111)
        groups = self.data.groupby("Outcome")
        for label, group in groups:
            ax.scatter(
                group[x_feature],
                group[y_feature],
                label=outcome_label(label),
                alpha=0.7,
                edgecolors="k",
                s=45,
            )
        if not self.extra_examples.empty:
            ax.scatter(
                self.extra_examples[x_feature],
                self.extra_examples[y_feature],
                c="black",
                marker="X",
                s=100,
                label="Additional example",
            )
        ax.set_xlabel(x_feature)
        ax.set_ylabel(y_feature)
        ax.set_title(f"{x_feature} vs {y_feature}")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
        fig.canvas.draw()
        connect_click_handler(
            fig,
            lambda event, x=x_feature, y=y_feature: self.open_large_scatter(
                event,
                x,
                y,
            ),
        )

    def draw_correlation(self, fig):
        fig.clf()
        ax = fig.add_subplot(111)
        corr = self.data.corr()
        cmap = plt.get_cmap("coolwarm")
        cax = ax.imshow(corr, cmap=cmap, vmin=-1, vmax=1)
        ax.set_xticks(range(len(corr.columns)))
        ax.set_yticks(range(len(corr.index)))
        ax.set_xticklabels(corr.columns, rotation=45, ha="right")
        ax.set_yticklabels(corr.index)
        fig.colorbar(cax, ax=ax, fraction=0.046, pad=0.04)
        ax.set_title("Correlation heatmap")
        fig.tight_layout()
        fig.canvas.draw()
        connect_click_handler(
            fig,
            lambda event: self.open_large_plot(
                self.draw_correlation_canvas,
                "correlation_heatmap",
            ),
        )

    def model_evaluation_data(self):
        if self.model is None:
            return None, None
        _, test_data = train_test_split(
            self.data,
            test_size=0.2,
            random_state=42,
            stratify=self.data["Outcome"],
        )
        probabilities = self.model.predict_proba(
            test_data[FEATURE_NAMES]
        )[:, 1]
        return test_data["Outcome"].to_numpy(), probabilities

    def draw_risk_distribution(self, fig):
        fig.clf()
        ax = fig.add_subplot(111)
        outcomes, probabilities = self.model_evaluation_data()
        if probabilities is None:
            ax.text(
                0.5,
                0.5,
                "No trained model found",
                ha="center",
                va="center",
            )
            ax.set_axis_off()
            fig.canvas.draw()
            return

        bins = np.linspace(0, 1, 21)
        for outcome, color in ((0, "tab:blue"), (1, "tab:red")):
            mask = outcomes == outcome
            if mask.any():
                ax.hist(
                    probabilities[mask],
                    bins=bins,
                    alpha=0.55,
                    density=True,
                    color=color,
                    label=outcome_label(outcome),
                )
        ax.axvline(
            0.5,
            color="black",
            linestyle="--",
            label="Decision threshold 0.5",
        )
        ax.set_xlabel("Predicted diabetes probability")
        ax.set_ylabel("Density")
        ax.set_title("Predicted Risk Distribution by Population")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.canvas.draw()

    def draw_roc_curve(self, fig):
        fig.clf()
        ax = fig.add_subplot(111)
        outcomes, probabilities = self.model_evaluation_data()
        if probabilities is None:
            ax.text(
                0.5,
                0.5,
                "No trained model found",
                ha="center",
                va="center",
            )
            ax.set_axis_off()
            fig.canvas.draw()
            return
        if len(np.unique(outcomes)) < 2:
            ax.text(
                0.5,
                0.5,
                "ROC requires data from both populations",
                ha="center",
                va="center",
            )
            ax.set_axis_off()
            fig.canvas.draw()
            return

        false_positive_rate, true_positive_rate, _ = roc_curve(
            outcomes,
            probabilities,
        )
        roc_auc = auc(false_positive_rate, true_positive_rate)
        ax.plot(
            false_positive_rate,
            true_positive_rate,
            color="tab:purple",
            linewidth=2,
            label=f"AUC = {roc_auc:.3f}",
        )
        ax.plot([0, 1], [0, 1], color="gray", linestyle="--")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.02)
        ax.set_xlabel("False Positive Rate")
        ax.set_ylabel("True Positive Rate")
        ax.set_title("ROC Curve - Model Discrimination")
        ax.legend(loc="lower right")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.canvas.draw()

    def draw_feature_importance(self, fig):
        fig.clf()
        ax = fig.add_subplot(111)
        if self.model is None:
            self.train_model_alert()
            return
        importances = pd.Series(
            self.model.feature_importances_, index=FEATURE_NAMES
        ).sort_values(ascending=True)
        importances.plot(kind="barh", ax=ax, color="skyblue")
        ax.set_title("Feature importance")
        ax.set_xlabel("Importance")
        fig.tight_layout()
        fig.canvas.draw()
        connect_click_handler(
            fig,
            lambda event: self.open_large_plot(
                self.draw_feature_importance_canvas,
                "feature_importance",
            ),
        )

    def draw_pca(self, fig):
        if self.data.empty:
            return
        fig.clf()
        ax = fig.add_subplot(111)
        X = self.data[FEATURE_NAMES]
        pca = PCA(n_components=2)
        projected = pca.fit_transform(X)
        df_pca = pd.DataFrame(projected, columns=["PC1", "PC2"])
        df_pca["Outcome"] = self.data["Outcome"].values
        for label, group in df_pca.groupby("Outcome"):
            ax.scatter(
                group["PC1"],
                group["PC2"],
                label=outcome_label(label),
                alpha=0.7,
                edgecolors="k",
                s=45,
            )
        if not self.extra_examples.empty:
            extra_proj = pca.transform(self.extra_examples[FEATURE_NAMES])
            ax.scatter(
                extra_proj[:, 0],
                extra_proj[:, 1],
                c="black",
                marker="X",
                s=100,
                label="Additional example",
            )
        ax.set_xlabel("PC1")
        ax.set_ylabel("PC2")
        ax.set_title("PCA scatter plot")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.canvas.draw()
        connect_click_handler(
            fig,
            lambda event: self.open_large_plot(
                self.draw_pca_canvas,
                "pca_scatter",
            ),
        )

    def umap_projection(self):
        features = self.data[FEATURE_NAMES]
        if len(features) < 3:
            raise ValueError("UMAP requires at least 3 dataset rows.")

        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(features)
        reducer = UMAP(
            n_components=2,
            n_neighbors=min(15, len(features) - 1),
            random_state=42,
            n_jobs=1,
        )
        projected = reducer.fit_transform(scaled_features)

        extra_projected = np.empty((0, 2))
        if not self.extra_examples.empty:
            scaled_extra = scaler.transform(
                self.extra_examples[FEATURE_NAMES]
            )
            extra_projected = reducer.transform(scaled_extra)
        return projected, extra_projected

    def draw_umap_axes(self, ax):
        try:
            projected, extra_projected = self.umap_projection()
        except ValueError as exc:
            ax.text(0.5, 0.5, str(exc), ha="center", va="center")
            ax.set_axis_off()
            return

        for label in sorted(self.data["Outcome"].unique()):
            mask = self.data["Outcome"] == label
            ax.scatter(
                projected[mask, 0],
                projected[mask, 1],
                label=outcome_label(label),
                alpha=0.7,
                edgecolors="k",
                s=45,
            )
        if len(extra_projected):
            ax.scatter(
                extra_projected[:, 0],
                extra_projected[:, 1],
                c="black",
                marker="X",
                s=100,
                label="Additional example",
            )
        ax.set_xlabel("UMAP 1")
        ax.set_ylabel("UMAP 2")
        ax.set_title("UMAP scatter plot")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

    def draw_umap(self, fig):
        fig.clf()
        ax = fig.add_subplot(111)
        self.draw_umap_axes(ax)
        fig.tight_layout()
        fig.canvas.draw()
        connect_click_handler(
            fig,
            lambda event: self.open_large_plot(
                self.draw_umap_axes,
                "umap_scatter",
            ),
        )

    def draw_boxplot(self, fig, feature):
        if self.box_plot_type.get() == "Violin plot":
            self.draw_violin(fig, feature)
            return
        fig.clf()
        ax = fig.add_subplot(111)
        values, labels = self.outcome_plot_data(feature)
        ax.boxplot(values, tick_labels=labels, patch_artist=True)
        ax.set_title(f"Boxplot for {feature}")
        ax.set_ylabel(feature)
        fig.tight_layout()
        fig.canvas.draw()
        connect_click_handler(
            fig,
            lambda event: self.open_large_plot(
                lambda large_ax: self.draw_boxplot_canvas(large_ax, feature),
                "boxplot",
            ),
        )

    def draw_violin(self, fig, feature):
        fig.clf()
        ax = fig.add_subplot(111)
        values, labels = self.outcome_plot_data(feature)
        parts = ax.violinplot(values, showmeans=True, showextrema=True)
        for pc in parts["bodies"]:
            pc.set_facecolor("skyblue")
            pc.set_edgecolor("black")
            pc.set_alpha(0.7)
        ax.set_xticks(range(1, len(labels) + 1))
        ax.set_xticklabels(labels)
        ax.set_title(f"Violin plot for {feature}")
        ax.set_ylabel(feature)
        fig.tight_layout()
        fig.canvas.draw()
        connect_click_handler(
            fig,
            lambda event: self.open_large_plot(
                lambda large_ax: self.draw_violin_canvas(large_ax, feature),
                "violin_plot",
            ),
        )

    def outcome_plot_data(self, feature):
        groups = self.data.groupby("Outcome")[feature]
        labels = [label for label in (0, 1) if label in groups.groups]
        if not labels:
            raise ValueError("No Outcome groups are available for plotting.")
        values = [groups.get_group(label) for label in labels]
        return values, [outcome_label(label) for label in labels]

    def refresh_boxplot(self, *args):
        self.draw_boxplot(self.box_canvas.figure, self.box_feature.get())

    def draw_boxplot_canvas(self, ax, feature):
        values, labels = self.outcome_plot_data(feature)
        ax.boxplot(values, tick_labels=labels, patch_artist=True)
        ax.set_title(f"Boxplot for {feature}")
        ax.set_ylabel(feature)
        ax.grid(alpha=0.3)

    def draw_violin_canvas(self, ax, feature):
        values, labels = self.outcome_plot_data(feature)
        parts = ax.violinplot(values, showmeans=True, showextrema=True)
        for pc in parts["bodies"]:
            pc.set_facecolor("skyblue")
            pc.set_edgecolor("black")
            pc.set_alpha(0.7)
        ax.set_xticks(range(1, len(labels) + 1))
        ax.set_xticklabels(labels)
        ax.set_title(f"Violin plot for {feature}")
        ax.set_ylabel(feature)
        ax.grid(alpha=0.3)

    def draw_feature_importance_canvas(self, ax):
        if self.model is None:
            self.train_model_alert()
            return
        importances = pd.Series(
            self.model.feature_importances_, index=FEATURE_NAMES
        ).sort_values(ascending=True)
        importances.plot(kind="barh", ax=ax, color="skyblue")
        ax.set_title("Feature importance")
        ax.set_xlabel("Importance")
        ax.grid(axis="x", alpha=0.3)

    def draw_correlation_canvas(self, ax):
        corr = self.data.corr()
        cmap = plt.get_cmap("coolwarm")
        cax = ax.imshow(corr, cmap=cmap, vmin=-1, vmax=1)
        ax.set_xticks(range(len(corr.columns)))
        ax.set_yticks(range(len(corr.index)))
        ax.set_xticklabels(corr.columns, rotation=45, ha="right")
        ax.set_yticklabels(corr.index)
        plt.colorbar(cax, ax=ax, fraction=0.046, pad=0.04)
        ax.set_title("Correlation heatmap")

    def draw_pca_canvas(self, ax):
        X = self.data[FEATURE_NAMES]
        pca = PCA(n_components=2)
        projected = pca.fit_transform(X)
        for label in sorted(self.data["Outcome"].unique()):
            mask = self.data["Outcome"] == label
            ax.scatter(
                projected[mask, 0],
                projected[mask, 1],
                label=outcome_label(label),
                alpha=0.7,
                edgecolors="k",
                s=45,
            )
        ax.set_xlabel("PC1")
        ax.set_ylabel("PC2")
        ax.set_title("PCA scatter plot")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

    def refresh_all(self):
        for fig, _, x, y in self.scatter_canvases:
            self.draw_scatter(fig, x, y)
        self.draw_correlation(self.corr_canvas.figure)
        self.draw_risk_distribution(self.risk_canvas.figure)
        self.draw_roc_curve(self.roc_canvas.figure)
        self.draw_pca(self.pca_canvas.figure)
        self.draw_umap(self.umap_canvas.figure)
        self.draw_feature_importance(self.importance_canvas.figure)
        self.draw_boxplot(self.box_canvas.figure, self.box_feature.get())

    def add_sample(self):
        try:
            values = {
                name: entry.get()
                for name, entry in self.entries.items()
            }
            row = sample_from_mapping(values)
        except (TypeError, ValueError) as exc:
            messagebox.showwarning("Invalid input", str(exc))
            return
        self.extra_examples = pd.concat([self.extra_examples, row], ignore_index=True)
        messagebox.showinfo("הוספה", "הדוגמה נוספה בהצלחה.")
        self.refresh_all()

    def read_json_sample(self):
        raw_text = self.json_text.get("1.0", tk.END).strip()
        if not raw_text:
            messagebox.showwarning("JSON ריק", "אנא הדבק JSON תקין בחלון הטקסט.")
            return None
        try:
            data = json.loads(raw_text)
            return sample_from_mapping(data)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            messagebox.showerror("JSON שגוי", f"לא ניתן לקרוא את הדוגמה: {exc}")
            return None

    def predict_json(self):
        sample = DiabetesGUI.read_json_sample(self)
        if sample is None:
            return
        if self.model is None:
            self.train_model_alert()
            return
        prob = self.model.predict_proba(sample)[0, 1]
        label = self.model.predict(sample)[0]
        self.result_label.config(
            text=f"חיזוי: {outcome_label(label)} | סיכוי לסוכרת: {prob:.3f}"
        )
        self.extra_examples = pd.concat([self.extra_examples, sample], ignore_index=True)
        self.refresh_all()

    def add_json_sample(self):
        sample = DiabetesGUI.read_json_sample(self)
        if sample is None:
            return
        self.extra_examples = pd.concat([self.extra_examples, sample], ignore_index=True)
        messagebox.showinfo("הוספה", "הדוגמה מ־JSON נוספה בהצלחה.")
        self.refresh_all()

    def one_click_sample(self):
        sample = {
            "Pregnancies": 3,
            "Glucose": 130,
            "BloodPressure": 78,
            "SkinThickness": 25,
            "Insulin": 90,
            "BMI": 32.0,
            "DiabetesPedigreeFunction": 0.65,
            "Age": 48,
        }
        df = sample_from_mapping(sample)
        self.extra_examples = pd.concat([self.extra_examples, df], ignore_index=True)
        if self.model is not None:
            prob = self.model.predict_proba(df)[0, 1]
            label = self.model.predict(df)[0]
            self.result_label.config(
                text=(
                    f"לחיצה אחת: {outcome_label(label)} | "
                    f"סיכוי לסוכרת: {prob:.3f}"
                )
            )
        self.refresh_all()

    def load_samples_file(self):
        path = filedialog.askopenfilename(
            title="בחר קובץ CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*")],
        )
        if not path:
            return
        try:
            csv_path = Path(path)
            if csv_path.stat().st_size > MAX_IMPORT_BYTES:
                raise ValueError("CSV file is larger than the 5 MB limit.")

            df = pd.read_csv(csv_path)
            if not set(FEATURE_NAMES).issubset(df.columns):
                df = pd.read_csv(csv_path, header=None)
                if df.shape[1] != len(FEATURE_NAMES):
                    raise ValueError(
                        f"CSV must contain exactly {len(FEATURE_NAMES)} columns."
                    )
                df.columns = FEATURE_NAMES

            if len(df) > MAX_IMPORT_ROWS:
                raise ValueError(
                    f"CSV contains more than {MAX_IMPORT_ROWS} rows."
                )
            samples = validate_feature_frame(df)
        except Exception as exc:
            messagebox.showerror("תקלה בטעינה", f"לא ניתן לקרוא את הקובץ: {exc}")
            return
        self.extra_examples = pd.concat(
            [self.extra_examples, samples],
            ignore_index=True,
        )
        predictions = DiabetesGUI.predict_loaded_samples(self, samples)
        self.file_predictions = pd.concat(
            [self.file_predictions, predictions],
            ignore_index=True,
        )
        self.update_prediction_table()
        messagebox.showinfo("טעינה", f"נוספו {len(samples)} דוגמאות נוספות.")
        self.refresh_all()

    def clear_extra_examples(self):
        self.extra_examples = pd.DataFrame(columns=FEATURE_NAMES)
        self.file_predictions = pd.DataFrame(
            columns=["Prediction", "DiabetesProbability"]
        )
        self.update_prediction_table()
        self.refresh_all()

    def open_large_scatter(self, event, x, y):
        if event.inaxes is None:
            return
        fig = plt.Figure(figsize=(8, 6), dpi=120)
        ax = fig.add_subplot(111)
        groups = self.data.groupby("Outcome")
        for label, group in groups:
            ax.scatter(
                group[x],
                group[y],
                label=outcome_label(label),
                alpha=0.7,
                edgecolors="k",
                s=60,
            )
        if not self.extra_examples.empty:
            ax.scatter(self.extra_examples[x], self.extra_examples[y], c="black", marker="X", s=120, label="Additional example")
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        ax.set_title(f"{x} vs {y}")
        ax.legend()
        ax.grid(alpha=0.3)
        self.open_popup(fig, f"{x}_vs_{y}")

    def open_large_plot(self, plot_fn, base_name):
        fig = plt.Figure(figsize=(8, 6), dpi=120)
        ax = fig.add_subplot(111)
        plot_fn(ax)
        self.open_popup(fig, base_name)

    def open_popup(self, fig, base_name):
        popup = tk.Toplevel(self)
        popup.title(f"Large view - {base_name}")
        canvas = FigureCanvasTkAgg(fig, master=popup)
        widget = canvas.get_tk_widget()
        widget.pack(fill=tk.BOTH, expand=True)
        toolbar = ttk.Frame(popup)
        toolbar.pack(fill=tk.X)
        ttk.Button(toolbar, text="שמור PNG", command=lambda: self.save_figure(fig, f"{base_name}.png")).pack(side=tk.LEFT, padx=4, pady=4)
        ttk.Button(toolbar, text="סגור", command=popup.destroy).pack(side=tk.RIGHT, padx=4, pady=4)
        canvas.draw()

    def save_figure(self, fig, default_name):
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=default_name,
            filetypes=[("PNG image", "*.png")],
        )
        if not path:
            return
        fig.savefig(path, dpi=150, bbox_inches="tight")
        self.clipboard_clear()
        self.clipboard_append(path)
        messagebox.showinfo("נשמר", f"הגרף נשמר כ־PNG ובחרת בנתיב להעתקה:\n{path}")

    def save_all_scatter(self):
        for fig, _, x, y in self.scatter_canvases:
            self.save_figure(fig, f"scatter_{x}_{y}.png")

    def train_model_alert(self):
        messagebox.showwarning(
            "מודל לא קיים",
            "לא נמצא מודל מאומן. נא הריצו python Day09/train_model.py לפני פתיחת GUI.",
        )


if __name__ == "__main__":
    app = DiabetesGUI()
    app.mainloop()
