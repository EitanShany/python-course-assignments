"""Fast QA tests for the Day09 diabetes project."""

import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from Day09 import (
    data_download,
    data_utils,
    gui,
    predict_example,
    train_model,
    visualize,
)


FEATURES = train_model.COLUMN_NAMES[:-1]


def sample_values():
    return {
        "Pregnancies": 2,
        "Glucose": 120,
        "BloodPressure": 70,
        "SkinThickness": 20,
        "Insulin": 85,
        "BMI": 30.5,
        "DiabetesPedigreeFunction": 0.55,
        "Age": 45,
    }


def alternative_sample_values():
    return {
        "Pregnancies": 6,
        "Glucose": 165,
        "BloodPressure": 82,
        "SkinThickness": 32,
        "Insulin": 140,
        "BMI": 36.2,
        "DiabetesPedigreeFunction": 0.82,
        "Age": 58,
    }


def dataset_rows(outcomes=(0, 1)):
    rows = []
    for index, outcome in enumerate(outcomes):
        values = sample_values()
        values["Glucose"] += index * 10
        values["BMI"] += index
        values["Outcome"] = outcome
        rows.append(values)
    return pd.DataFrame(rows, columns=train_model.COLUMN_NAMES)


def training_rows(offset=0):
    rows = []
    for index in range(40):
        values = sample_values() if index % 2 == 0 else alternative_sample_values()
        values = values.copy()
        values["Glucose"] += offset + index
        values["BMI"] += index / 10
        values["Outcome"] = index % 2
        rows.append(values)
    return pd.DataFrame(rows, columns=train_model.COLUMN_NAMES)


def valid_download_content(glucose=120, bmi=30.5):
    rows = []
    for index in range(data_download.EXPECTED_ROWS):
        outcome = index % 2
        rows.append(f"1,{glucose},70,20,85,{bmi},0.55,45,{outcome}")
    return ("\n".join(rows) + "\n").encode("utf-8")


class FakeModel:
    def predict_proba(self, sample):
        return np.array([[0.25, 0.75]])

    def predict(self, sample):
        return np.array([1])


class AlternativeFakeModel:
    def predict_proba(self, sample):
        return np.array([[0.8, 0.2]])

    def predict(self, sample):
        return np.array([0])


class FakePlotClassifier:
    def __init__(self, *args, **kwargs):
        self.fitted = False

    def fit(self, features, target):
        self.fitted = True
        return self

    def predict(self, features):
        return np.zeros(len(features), dtype=int)


class SeparationModel:
    def predict_proba(self, sample):
        glucose = sample["Glucose"].to_numpy(dtype=float)
        probabilities = np.clip((glucose - 80) / 120, 0.05, 0.95)
        return np.column_stack([1 - probabilities, probabilities])

    def predict(self, sample):
        return (self.predict_proba(sample)[:, 1] >= 0.5).astype(int)


def fake_gui_for_json(raw_text, model=None):
    instance = SimpleNamespace(
        json_text=Mock(),
        model=model or FakeModel(),
        result_label=Mock(),
        extra_examples=pd.DataFrame(columns=FEATURES),
        refresh_all=Mock(),
        train_model_alert=Mock(),
    )
    instance.json_text.get.return_value = raw_text
    return instance


class Day09QATests(unittest.TestCase):
    def test_project_modules_import(self):
        self.assertTrue(callable(data_download.download))
        self.assertTrue(callable(train_model.train))
        self.assertTrue(callable(visualize.plot_population))
        self.assertTrue(hasattr(gui, "DiabetesGUI"))

    def test_load_data_uses_expected_columns(self):
        data = dataset_rows()
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "diabetes.csv"
            data.to_csv(csv_path, index=False, header=False)

            with patch.object(train_model, "DATA_PATH", csv_path):
                loaded = train_model.load_data()

        self.assertEqual(list(loaded.columns), train_model.COLUMN_NAMES)
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded["Outcome"].tolist(), [0, 1])

    def test_load_data_keeps_dataset_with_one_available_outcome(self):
        data = dataset_rows(outcomes=(0, 0, 0))
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "partial_outcomes.csv"
            data.to_csv(csv_path, index=False, header=False)

            with patch.object(train_model, "DATA_PATH", csv_path):
                loaded = train_model.load_data()

        self.assertEqual(len(loaded), 3)
        self.assertEqual(set(loaded["Outcome"]), {0})

    def test_visualize_load_data_uses_alternative_values(self):
        data = dataset_rows(outcomes=(1, 0, 1))
        data.loc[:, "Glucose"] = [95, 145, 180]
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "visualize.csv"
            data.to_csv(csv_path, index=False, header=False)

            with patch.object(visualize, "DATA_PATH", csv_path):
                loaded = visualize.load_data()

        self.assertEqual(loaded["Glucose"].tolist(), [95, 145, 180])
        self.assertEqual(loaded["Outcome"].tolist(), [1, 0, 1])

    def test_predict_json_accepts_complete_numeric_sample(self):
        fake_gui = fake_gui_for_json(json.dumps(sample_values()))

        gui.DiabetesGUI.predict_json(fake_gui)

        self.assertEqual(len(fake_gui.extra_examples), 1)
        fake_gui.result_label.config.assert_called_once()
        fake_gui.refresh_all.assert_called_once()
        fake_gui.train_model_alert.assert_not_called()

    def test_predict_json_accepts_alternative_numeric_sample(self):
        fake_gui = fake_gui_for_json(
            json.dumps(alternative_sample_values()),
            model=AlternativeFakeModel(),
        )

        gui.DiabetesGUI.predict_json(fake_gui)

        self.assertEqual(fake_gui.extra_examples.iloc[0]["Glucose"], 165)
        result_text = fake_gui.result_label.config.call_args.kwargs["text"]
        self.assertIn("0.200", result_text)
        fake_gui.refresh_all.assert_called_once()

    def test_predict_json_rejects_missing_fields(self):
        incomplete = sample_values()
        incomplete.pop("BMI")
        fake_gui = fake_gui_for_json(json.dumps(incomplete))

        with patch.object(gui.messagebox, "showerror") as showerror:
            gui.DiabetesGUI.predict_json(fake_gui)

        showerror.assert_called_once()
        self.assertIn("BMI", showerror.call_args.args[1])
        self.assertTrue(fake_gui.extra_examples.empty)
        fake_gui.refresh_all.assert_not_called()

    def test_predict_json_rejects_multiple_missing_fields(self):
        incomplete = alternative_sample_values()
        incomplete.pop("Age")
        incomplete.pop("Insulin")
        fake_gui = fake_gui_for_json(json.dumps(incomplete))

        with patch.object(gui.messagebox, "showerror") as showerror:
            gui.DiabetesGUI.predict_json(fake_gui)

        message = showerror.call_args.args[1]
        self.assertIn("Age", message)
        self.assertIn("Insulin", message)
        self.assertTrue(fake_gui.extra_examples.empty)

    def test_predict_json_rejects_invalid_json(self):
        fake_gui = fake_gui_for_json('{"Glucose": 120')

        with patch.object(gui.messagebox, "showerror") as showerror:
            gui.DiabetesGUI.predict_json(fake_gui)

        showerror.assert_called_once()
        self.assertTrue(fake_gui.extra_examples.empty)
        fake_gui.refresh_all.assert_not_called()

    def test_predict_json_rejects_second_invalid_json_format(self):
        fake_gui = fake_gui_for_json("[1, 2,")

        with patch.object(gui.messagebox, "showerror") as showerror:
            gui.DiabetesGUI.predict_json(fake_gui)

        showerror.assert_called_once()
        self.assertTrue(fake_gui.extra_examples.empty)

    def test_predict_json_rejects_first_non_object_json(self):
        fake_gui = fake_gui_for_json(json.dumps([1, 2, 3]))

        with patch.object(gui.messagebox, "showerror") as showerror:
            gui.DiabetesGUI.predict_json(fake_gui)

        self.assertIn("JSON object", showerror.call_args.args[1])
        self.assertTrue(fake_gui.extra_examples.empty)

    def test_predict_json_rejects_second_non_object_json(self):
        fake_gui = fake_gui_for_json(json.dumps("not an object"))

        with patch.object(gui.messagebox, "showerror") as showerror:
            gui.DiabetesGUI.predict_json(fake_gui)

        self.assertIn("JSON object", showerror.call_args.args[1])
        fake_gui.refresh_all.assert_not_called()

    def test_predict_json_rejects_first_empty_input(self):
        fake_gui = fake_gui_for_json("")

        with patch.object(gui.messagebox, "showwarning") as showwarning:
            gui.DiabetesGUI.predict_json(fake_gui)

        showwarning.assert_called_once()
        fake_gui.refresh_all.assert_not_called()

    def test_predict_json_rejects_second_empty_input(self):
        fake_gui = fake_gui_for_json("   \n")

        with patch.object(gui.messagebox, "showwarning") as showwarning:
            gui.DiabetesGUI.predict_json(fake_gui)

        showwarning.assert_called_once()
        self.assertTrue(fake_gui.extra_examples.empty)

    def test_predict_json_handles_first_missing_model(self):
        fake_gui = fake_gui_for_json(json.dumps(sample_values()))
        fake_gui.model = None

        gui.DiabetesGUI.predict_json(fake_gui)

        fake_gui.train_model_alert.assert_called_once()
        fake_gui.refresh_all.assert_not_called()

    def test_predict_json_handles_second_missing_model(self):
        fake_gui = fake_gui_for_json(json.dumps(alternative_sample_values()))
        fake_gui.model = None

        gui.DiabetesGUI.predict_json(fake_gui)

        fake_gui.train_model_alert.assert_called_once()
        self.assertTrue(fake_gui.extra_examples.empty)

    def test_manual_sample_rejects_non_numeric_value(self):
        entries = {name: Mock() for name in FEATURES}
        for entry in entries.values():
            entry.get.return_value = "10"
        entries["Glucose"].get.return_value = "not-a-number"
        fake_gui = SimpleNamespace(
            entries=entries,
            extra_examples=pd.DataFrame(columns=FEATURES),
            refresh_all=Mock(),
        )

        with patch.object(gui.messagebox, "showwarning") as showwarning:
            gui.DiabetesGUI.add_sample(fake_gui)

        showwarning.assert_called_once()
        self.assertTrue(fake_gui.extra_examples.empty)
        fake_gui.refresh_all.assert_not_called()

    def test_manual_sample_rejects_empty_numeric_field(self):
        entries = {name: Mock() for name in FEATURES}
        for entry in entries.values():
            entry.get.return_value = "25"
        entries["Age"].get.return_value = ""
        fake_gui = SimpleNamespace(
            entries=entries,
            extra_examples=pd.DataFrame(columns=FEATURES),
            refresh_all=Mock(),
        )

        with patch.object(gui.messagebox, "showwarning") as showwarning:
            gui.DiabetesGUI.add_sample(fake_gui)

        showwarning.assert_called_once()
        self.assertTrue(fake_gui.extra_examples.empty)

    def test_scatter_supports_only_one_outcome_group(self):
        fake_gui = SimpleNamespace(
            data=dataset_rows(outcomes=(0, 0, 0)),
            extra_examples=pd.DataFrame(columns=FEATURES),
            open_large_scatter=Mock(),
        )
        figure = Figure()

        gui.DiabetesGUI.draw_scatter(fake_gui, figure, "Glucose", "BMI")

        axes = figure.axes[0]
        self.assertEqual(len(axes.collections), 1)
        self.assertEqual(axes.get_xlabel(), "Glucose")
        self.assertEqual(axes.get_ylabel(), "BMI")

    def test_scatter_supports_alternative_single_outcome_group(self):
        data = dataset_rows(outcomes=(1, 1))
        fake_gui = SimpleNamespace(
            data=data,
            extra_examples=pd.DataFrame(
                [alternative_sample_values()],
                columns=FEATURES,
            ),
            open_large_scatter=Mock(),
        )
        figure = Figure()

        gui.DiabetesGUI.draw_scatter(fake_gui, figure, "Glucose", "Age")

        axes = figure.axes[0]
        self.assertEqual(len(axes.collections), 2)
        self.assertEqual(axes.get_ylabel(), "Age")

    def test_boxplot_supports_only_zero_outcome(self):
        fake_gui = SimpleNamespace(
            data=dataset_rows(outcomes=(0, 0, 0)),
            box_plot_type=SimpleNamespace(get=lambda: "Boxplot"),
            open_large_plot=Mock(),
            outcome_plot_data=Mock(),
        )
        fake_gui.outcome_plot_data.side_effect = (
            lambda feature: gui.DiabetesGUI.outcome_plot_data(fake_gui, feature)
        )
        figure = Figure()

        gui.DiabetesGUI.draw_boxplot(fake_gui, figure, "Glucose")

        self.assertEqual(
            [label.get_text() for label in figure.axes[0].get_xticklabels()],
            ["Healthy"],
        )

    def test_boxplot_supports_only_one_outcome(self):
        fake_gui = SimpleNamespace(
            data=dataset_rows(outcomes=(1, 1, 1)),
            box_plot_type=SimpleNamespace(get=lambda: "Boxplot"),
            open_large_plot=Mock(),
            outcome_plot_data=Mock(),
        )
        fake_gui.outcome_plot_data.side_effect = (
            lambda feature: gui.DiabetesGUI.outcome_plot_data(fake_gui, feature)
        )
        figure = Figure()

        gui.DiabetesGUI.draw_boxplot(fake_gui, figure, "BMI")

        self.assertEqual(
            [label.get_text() for label in figure.axes[0].get_xticklabels()],
            ["Diabetes"],
        )

    def test_risk_distribution_shows_both_populations(self):
        fake_gui = SimpleNamespace(
            data=training_rows(offset=0),
            model=SeparationModel(),
            model_evaluation_data=Mock(),
        )
        fake_gui.model_evaluation_data.side_effect = (
            lambda: gui.DiabetesGUI.model_evaluation_data(fake_gui)
        )
        figure = Figure()

        gui.DiabetesGUI.draw_risk_distribution(fake_gui, figure)

        legend_labels = [
            text.get_text()
            for text in figure.axes[0].get_legend().get_texts()
        ]
        self.assertIn("Healthy", legend_labels)
        self.assertIn("Diabetes", legend_labels)

    def test_risk_distribution_supports_single_population(self):
        fake_gui = SimpleNamespace(
            data=training_rows(offset=5),
            model=SeparationModel(),
            model_evaluation_data=Mock(),
        )
        fake_gui.model_evaluation_data.return_value = (
            np.zeros(8, dtype=int),
            np.linspace(0.1, 0.4, 8),
        )
        figure = Figure()

        gui.DiabetesGUI.draw_risk_distribution(fake_gui, figure)

        legend_labels = [
            text.get_text()
            for text in figure.axes[0].get_legend().get_texts()
        ]
        self.assertIn("Healthy", legend_labels)
        self.assertNotIn("Diabetes", legend_labels)

    def test_roc_curve_reports_auc_for_two_populations(self):
        fake_gui = SimpleNamespace(
            data=training_rows(offset=10),
            model=SeparationModel(),
            model_evaluation_data=Mock(),
        )
        fake_gui.model_evaluation_data.side_effect = (
            lambda: gui.DiabetesGUI.model_evaluation_data(fake_gui)
        )
        figure = Figure()

        gui.DiabetesGUI.draw_roc_curve(fake_gui, figure)

        legend_text = figure.axes[0].get_legend().get_texts()[0].get_text()
        self.assertIn("AUC =", legend_text)

    def test_roc_curve_explains_single_population_limit(self):
        fake_gui = SimpleNamespace(
            data=training_rows(offset=15),
            model=SeparationModel(),
            model_evaluation_data=Mock(),
        )
        fake_gui.model_evaluation_data.return_value = (
            np.ones(8, dtype=int),
            np.linspace(0.6, 0.9, 8),
        )
        figure = Figure()

        gui.DiabetesGUI.draw_roc_curve(fake_gui, figure)

        self.assertTrue(figure.axes[0].texts)

    def test_clear_first_set_of_extra_examples(self):
        fake_gui = SimpleNamespace(
            extra_examples=pd.DataFrame([sample_values()], columns=FEATURES),
            file_predictions=pd.DataFrame(
                [{"Prediction": "Healthy", "DiabetesProbability": 0.2}]
            ),
            update_prediction_table=Mock(),
            refresh_all=Mock(),
        )

        gui.DiabetesGUI.clear_extra_examples(fake_gui)

        self.assertTrue(fake_gui.extra_examples.empty)
        self.assertTrue(fake_gui.file_predictions.empty)
        fake_gui.update_prediction_table.assert_called_once()
        fake_gui.refresh_all.assert_called_once()

    def test_clear_second_set_of_extra_examples(self):
        fake_gui = SimpleNamespace(
            extra_examples=pd.DataFrame(
                [sample_values(), alternative_sample_values()],
                columns=FEATURES,
            ),
            file_predictions=pd.DataFrame(
                [
                    {"Prediction": "Healthy", "DiabetesProbability": 0.2},
                    {"Prediction": "Diabetes", "DiabetesProbability": 0.8},
                ]
            ),
            update_prediction_table=Mock(),
            refresh_all=Mock(),
        )

        gui.DiabetesGUI.clear_extra_examples(fake_gui)

        self.assertEqual(list(fake_gui.extra_examples.columns), FEATURES)
        self.assertTrue(fake_gui.file_predictions.empty)
        fake_gui.update_prediction_table.assert_called_once()
        fake_gui.refresh_all.assert_called_once()

    def test_load_first_valid_samples_csv(self):
        self._assert_load_samples_file(
            pd.DataFrame([sample_values()], columns=FEATURES)
        )

    def test_load_second_valid_samples_csv(self):
        self._assert_load_samples_file(
            pd.DataFrame(
                [sample_values(), alternative_sample_values()],
                columns=FEATURES,
            )
        )

    def _assert_load_samples_file(self, loaded_data):
        fake_gui = SimpleNamespace(
            extra_examples=pd.DataFrame(columns=FEATURES),
            file_predictions=pd.DataFrame(
                columns=["Prediction", "DiabetesProbability"]
            ),
            model=SeparationModel(),
            update_prediction_table=Mock(),
            refresh_all=Mock(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "samples.csv"
            loaded_data.to_csv(csv_path, index=False)
            with (
                patch.object(
                    gui.filedialog,
                    "askopenfilename",
                    return_value=str(csv_path),
                ),
                patch.object(gui.messagebox, "showinfo") as showinfo,
            ):
                gui.DiabetesGUI.load_samples_file(fake_gui)

        self.assertEqual(len(fake_gui.extra_examples), len(loaded_data))
        self.assertEqual(len(fake_gui.file_predictions), len(loaded_data))
        self.assertTrue(
            set(fake_gui.file_predictions["Prediction"]).issubset(
                {"Healthy", "Diabetes"}
            )
        )
        fake_gui.update_prediction_table.assert_called_once()
        showinfo.assert_called_once()
        fake_gui.refresh_all.assert_called_once()

    def test_load_first_unreadable_samples_csv(self):
        self._assert_unreadable_samples_file(OSError("file is locked"))

    def test_load_second_unreadable_samples_csv(self):
        self._assert_unreadable_samples_file(ValueError("invalid CSV"))

    def _assert_unreadable_samples_file(self, error):
        fake_gui = SimpleNamespace(
            extra_examples=pd.DataFrame(columns=FEATURES),
            file_predictions=pd.DataFrame(
                columns=["Prediction", "DiabetesProbability"]
            ),
            model=SeparationModel(),
            update_prediction_table=Mock(),
            refresh_all=Mock(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "bad.csv"
            csv_path.write_text("bad,data", encoding="utf-8")
            with (
                patch.object(
                    gui.filedialog,
                    "askopenfilename",
                    return_value=str(csv_path),
                ),
                patch.object(gui.pd, "read_csv", side_effect=error),
                patch.object(gui.messagebox, "showerror") as showerror,
            ):
                gui.DiabetesGUI.load_samples_file(fake_gui)

        showerror.assert_called_once()
        self.assertTrue(fake_gui.extra_examples.empty)
        self.assertTrue(fake_gui.file_predictions.empty)
        fake_gui.update_prediction_table.assert_not_called()
        fake_gui.refresh_all.assert_not_called()

    def test_load_model_returns_first_saved_model(self):
        expected_model = FakeModel()
        model_path = Mock()
        model_path.exists.return_value = True
        with (
            patch.object(gui, "MODEL_PATH", model_path),
            patch.object(gui.joblib, "load", return_value=expected_model),
        ):
            loaded_model = gui.DiabetesGUI.load_model(SimpleNamespace())

        self.assertIs(loaded_model, expected_model)

    def test_load_model_returns_second_saved_model(self):
        expected_model = AlternativeFakeModel()
        model_path = Mock()
        model_path.exists.return_value = True
        with (
            patch.object(gui, "MODEL_PATH", model_path),
            patch.object(gui.joblib, "load", return_value=expected_model),
        ):
            loaded_model = gui.DiabetesGUI.load_model(SimpleNamespace())

        self.assertIs(loaded_model, expected_model)

    def test_download_validation_accepts_expected_dataset(self):
        content = valid_download_content()

        validated = data_download.validate_dataset(content)

        self.assertEqual(validated, content)

    def test_download_validation_accepts_alternative_expected_dataset(self):
        content = valid_download_content(glucose=175, bmi=41.2)

        validated = data_download.validate_dataset(content)

        self.assertIn(b",175,", validated)
        self.assertIn(b",41.2,", validated)

    def test_download_validation_rejects_partial_dataset(self):
        partial_content = b"1,120,70,20,85,30.5,0.55,45,0\n"

        with self.assertRaisesRegex(ValueError, "Expected 768 rows"):
            data_download.validate_dataset(partial_content)

    def test_download_validation_rejects_second_partial_dataset(self):
        partial_content = b"\n".join(valid_download_content().splitlines()[:767])

        with self.assertRaisesRegex(ValueError, "received 767"):
            data_download.validate_dataset(partial_content)

    def test_download_validation_rejects_non_numeric_data(self):
        content = valid_download_content().replace(b",120,", b",invalid,", 1)

        with self.assertRaisesRegex(ValueError, "non-numeric"):
            data_download.validate_dataset(content)

    def test_download_validation_rejects_second_non_numeric_column(self):
        content = valid_download_content().replace(b",30.5,", b",missing,", 1)

        with self.assertRaisesRegex(ValueError, "non-numeric"):
            data_download.validate_dataset(content)

    def test_feature_validation_rejects_negative_value(self):
        values = sample_values()
        values["Age"] = -1

        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            data_utils.sample_from_mapping(values)

    def test_feature_validation_rejects_non_finite_value(self):
        values = alternative_sample_values()
        values["BMI"] = float("nan")

        with self.assertRaisesRegex(ValueError, "finite numbers"):
            data_utils.sample_from_mapping(values)

    def test_training_creates_model_for_first_dataset(self):
        self._assert_training_creates_model(training_rows(offset=0))

    def test_training_creates_model_for_alternative_dataset(self):
        self._assert_training_creates_model(training_rows(offset=25))

    def _assert_training_creates_model(self, data):
        with tempfile.TemporaryDirectory() as temp_dir:
            models_dir = Path(temp_dir)
            output = io.StringIO()
            with (
                patch.object(train_model, "load_data", return_value=data),
                patch.object(train_model, "MODELS_DIR", models_dir),
                redirect_stdout(output),
            ):
                train_model.train()

            model_path = models_dir / "classifier.joblib"
            self.assertTrue(model_path.exists())
            model = train_model.joblib.load(model_path)
            probabilities = model.predict_proba(data[FEATURES].head(2))

        self.assertEqual(probabilities.shape, (2, 2))
        self.assertIn("Classifier Accuracy", output.getvalue())

    def test_prediction_example_reports_high_risk_model(self):
        self._assert_prediction_example(
            model=FakeModel(),
            data=training_rows(offset=0),
            expected_probability="0.750",
            expected_label="1",
        )

    def test_prediction_example_reports_low_risk_model(self):
        self._assert_prediction_example(
            model=AlternativeFakeModel(),
            data=training_rows(offset=30),
            expected_probability="0.200",
            expected_label="0",
        )

    def _assert_prediction_example(
        self,
        model,
        data,
        expected_probability,
        expected_label,
    ):
        output = io.StringIO()
        with (
            patch.object(predict_example, "load_model", return_value=model),
            patch.object(predict_example, "load_dataset", return_value=data),
            redirect_stdout(output),
        ):
            predict_example.example()

        text = output.getvalue()
        self.assertIn(expected_probability, text)
        self.assertIn(data_utils.outcome_label(expected_label), text)

    def test_download_saves_first_valid_response(self):
        self._assert_download_saves_content(
            valid_download_content(),
            include_content_length=True,
        )

    def test_download_saves_alternative_valid_response(self):
        self._assert_download_saves_content(
            valid_download_content(glucose=155, bmi=34.8),
            include_content_length=False,
        )

    def _assert_download_saves_content(self, content, include_content_length):
        response = Mock()
        response.url = data_download.URL
        response.content = content
        response.iter_content.return_value = [content]
        response.headers = (
            {"Content-Length": str(len(content))}
            if include_content_length
            else {}
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "data"
            output_path = output_dir / "pima-indians-diabetes.csv"
            with (
                patch.object(data_download, "OUT_DIR", output_dir),
                patch.object(data_download, "OUT_PATH", output_path),
                patch.object(data_download.requests, "get", return_value=response),
                patch("builtins.print"),
            ):
                saved_path = data_download.download()

            self.assertEqual(saved_path, output_path)
            self.assertEqual(output_path.read_bytes(), content)
            response.raise_for_status.assert_called_once()

    def test_visualization_saves_first_population_plot(self):
        self._assert_visualization_saves_plot(training_rows(offset=0))

    def test_visualization_saves_alternative_population_plot(self):
        self._assert_visualization_saves_plot(training_rows(offset=40))

    def _assert_visualization_saves_plot(self, data):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            with (
                patch.object(visualize, "BASE", base),
                patch.object(visualize, "load_data", return_value=data),
                patch.object(
                    visualize,
                    "RandomForestClassifier",
                    FakePlotClassifier,
                ),
                patch.object(visualize.plt, "show"),
                patch("builtins.print"),
            ):
                visualize.plot_population()

            image_path = base / "diabetes_population.png"
            self.assertTrue(image_path.exists())
            self.assertGreater(image_path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
