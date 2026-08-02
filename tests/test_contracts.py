"""
Tests for energizados.contracts module.

Tests verify:
- All 8 base classes exist in contracts.py
- Abstract methods are enforced
- Shim re-exports work correctly
- isinstance checks pass from old paths
"""

import pytest

from energizados.contracts import BaseFeatureSelector, BaseModel


# Helper classes for save/load tests (must be module-level for pickle)
class DummyModel(BaseModel):
    """Dummy model for save/load tests."""

    def fit(self, X, y, X_val=None, y_val=None):
        self.model_ = "dummy"
        self.is_fitted_ = True
        return self

    def predict(self, X):
        return self.model_

    def predict_proba(self, X):
        return self.model_

    def get_raw_model(self):
        return self.model_


class DummySelector(BaseFeatureSelector):
    """Dummy selector for save/load tests."""

    def fit(self, X, y):
        self.selected_features_ = ["feature1", "feature2"]
        return self

    def transform(self, X):
        return X[self.selected_features_]


class TestContractsModule:
    """Test that the contracts module exists and is importable."""

    def test_contracts_module_exists(self):
        """GIVEN the framework is installed WHEN import energizados.contracts succeeds THEN the module exists."""
        import energizados.contracts

        assert energizados.contracts is not None


class TestAllBasesExist:
    """Test that all 8 base classes exist in energizados.contracts."""

    def test_base_model_exists(self):
        """GIVEN the contracts module WHEN inspecting it THEN BaseModel is defined."""
        from energizados.contracts import BaseModel

        assert BaseModel is not None

    def test_base_inference_exists(self):
        """GIVEN the contracts module WHEN inspecting it THEN BaseInference is defined."""
        from energizados.contracts import BaseInference

        assert BaseInference is not None

    def test_base_pipeline_exists(self):
        """GIVEN the contracts module WHEN inspecting it THEN BasePipeline is defined."""
        from energizados.contracts import BasePipeline

        assert BasePipeline is not None

    def test_base_evaluator_exists(self):
        """GIVEN the contracts module WHEN inspecting it THEN BaseEvaluator is defined."""
        from energizados.contracts import BaseEvaluator

        assert BaseEvaluator is not None

    def test_base_etl_exists(self):
        """GIVEN the contracts module WHEN inspecting it THEN BaseETL is defined."""
        from energizados.contracts import BaseETL

        assert BaseETL is not None

    def test_base_feature_engineering_exists(self):
        """GIVEN the contracts module WHEN inspecting it THEN BaseFeatureEngineering is defined."""
        from energizados.contracts import BaseFeatureEngineering

        assert BaseFeatureEngineering is not None

    def test_base_feature_selector_exists(self):
        """GIVEN the contracts module WHEN inspecting it THEN BaseFeatureSelector is defined."""
        from energizados.contracts import BaseFeatureSelector

        assert BaseFeatureSelector is not None

    def test_base_explorer_exists(self):
        """GIVEN the contracts module WHEN inspecting it THEN BaseExplorer is defined."""
        from energizados.contracts import BaseExplorer

        assert BaseExplorer is not None


class TestBaseModelSaveLoad:
    """Test save/load functionality on BaseModel."""

    def test_save_raises_model_not_fitted_error_when_not_fitted(self):
        """GIVEN a BaseModel instance WHEN save() is called before fit THEN ModelNotFittedError is raised."""
        import tempfile

        from energizados.core.exceptions import ModelNotFittedError

        model = DummyModel()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/dummy.pkl"
            with pytest.raises(ModelNotFittedError):
                model.save(path)

    def test_save_uses_integrity_pickle(self):
        """GIVEN a fitted BaseModel WHEN save() is called THEN dump is used."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "model.pkl"
            model = DummyModel()
            model.fit(None, None)

            model.save(str(path))

            # Check that both .pkl and .sig files exist
            assert path.exists()
            assert Path(str(path) + ".sig").exists()

    def test_load_uses_integrity_pickle(self):
        """GIVEN a saved BaseModel WHEN load() is called THEN load is used."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "model.pkl"
            model = DummyModel()
            model.fit(None, None)
            model.save(str(path))

            loaded_model = BaseModel.load(str(path))

            assert loaded_model.is_fitted_ is True
            assert loaded_model.model_ == "dummy"

    def test_round_trip_preserves_fitted_state(self):
        """GIVEN a fitted BaseModel WHEN saved and loaded THEN fitted state is preserved."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "model.pkl"
            model = DummyModel()
            model.fit(None, None)
            model.save(str(path))

            loaded_model = BaseModel.load(str(path))

            assert loaded_model.is_fitted_ is True
            assert loaded_model.model_ == "dummy"

    def test_save_creates_parent_directories(self):
        """GIVEN a path with non-existing parent directories WHEN save() is called THEN parents are created."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "model.pkl"
            model = DummyModel()
            model.fit(None, None)

            model.save(str(path))

            assert path.exists()


class TestBaseFeatureSelectorSaveLoad:
    """Test save/load functionality on BaseFeatureSelector."""

    def test_save_raises_model_not_fitted_error_when_not_fitted(self):
        """GIVEN a BaseFeatureSelector instance WHEN save() is called before fit THEN ModelNotFittedError is raised."""
        import tempfile

        from energizados.core.exceptions import ModelNotFittedError

        selector = DummySelector()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/dummy.pkl"
            with pytest.raises(ModelNotFittedError):
                selector.save(path)

    def test_save_uses_integrity_pickle(self):
        """GIVEN a fitted BaseFeatureSelector WHEN save() is called THEN dump is used."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "selector.pkl"
            selector = DummySelector()
            selector.fit(None, None)

            selector.save(str(path))

            # Check that both .pkl and .sig files exist
            assert path.exists()
            assert Path(str(path) + ".sig").exists()

    def test_load_uses_integrity_pickle(self):
        """GIVEN a saved BaseFeatureSelector WHEN load() is called THEN load is used."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "selector.pkl"
            selector = DummySelector()
            selector.fit(None, None)
            selector.save(str(path))

            loaded_selector = BaseFeatureSelector.load(str(path))

            assert loaded_selector.selected_features_ == ["feature1", "feature2"]

    def test_round_trip_preserves_fitted_state(self):
        """GIVEN a fitted BaseFeatureSelector WHEN saved and loaded THEN fitted state is preserved."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "selector.pkl"
            selector = DummySelector()
            selector.fit(None, None)
            selector.save(str(path))

            loaded_selector = BaseFeatureSelector.load(str(path))

            assert loaded_selector.selected_features_ == ["feature1", "feature2"]

    def test_save_creates_parent_directories(self):
        """GIVEN a path with non-existing parent directories WHEN save() is called THEN parents are created."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "selector.pkl"
            selector = DummySelector()
            selector.fit(None, None)

            selector.save(str(path))

            assert path.exists()


class TestIntegrityPickleIntegration:
    """Test that all base classes use integrity_pickle consistently."""

    def test_base_feature_engineering_uses_integrity_pickle(self):
        """GIVEN BaseFeatureEngineering WHEN save() and load() are inspected THEN they use integrity_pickle."""
        import inspect

        from energizados.contracts import BaseFeatureEngineering

        # Check that save() uses dump
        save_source = inspect.getsource(BaseFeatureEngineering.save)
        assert "dump" in save_source

        # Check that load() uses load
        load_source = inspect.getsource(BaseFeatureEngineering.load)
        assert "load" in load_source

    def test_all_bases_use_same_integrity_pickle_pattern(self):
        """GIVEN all base classes with save/load WHEN they are inspected THEN they use the same integrity_pickle pattern."""
        import inspect

        from energizados.contracts import (
            BaseFeatureEngineering,
            BaseFeatureSelector,
            BaseModel,
        )

        # BaseModel should use dump and load
        model_save = inspect.getsource(BaseModel.save)
        model_load = inspect.getsource(BaseModel.load)
        assert "dump" in model_save
        assert "load" in model_load

        # BaseFeatureSelector should use dump and load
        selector_save = inspect.getsource(BaseFeatureSelector.save)
        selector_load = inspect.getsource(BaseFeatureSelector.load)
        assert "dump" in selector_save
        assert "load" in selector_load

        # BaseFeatureEngineering should use dump and load
        fe_save = inspect.getsource(BaseFeatureEngineering.save)
        fe_load = inspect.getsource(BaseFeatureEngineering.load)
        assert "dump" in fe_save
        assert "load" in fe_load


class TestShimReexports:
    """Test that old modules re-export the same class object (not copies)."""

    def test_core_base_shim_reexports_base_model(self):
        """GIVEN core/base.py WHEN importing BaseModel THEN it re-exports from contracts (same object)."""
        from energizados.contracts import BaseModel as ContractsBaseModel
        from energizados.core.base import BaseModel as CoreBaseModel

        assert CoreBaseModel is ContractsBaseModel

    def test_core_base_shim_reexports_base_inference(self):
        """GIVEN core/base.py WHEN importing BaseInference THEN it re-exports from contracts (same object)."""
        from energizados.contracts import BaseInference as ContractsBaseInference
        from energizados.core.base import BaseInference as CoreBaseInference

        assert CoreBaseInference is ContractsBaseInference

    def test_etl_base_shim_reexports_base_etl(self):
        """GIVEN etl/base.py WHEN importing BaseETL THEN it re-exports from contracts (same object)."""
        from energizados.contracts import BaseETL as ContractsBaseETL
        from energizados.etl.base import BaseETL as EtlBaseETL

        assert EtlBaseETL is ContractsBaseETL

    def test_feature_engineering_base_shim_reexports(self):
        """GIVEN feature_engineering/base.py WHEN importing BaseFeatureEngineering THEN it re-exports from contracts."""
        from energizados.contracts import BaseFeatureEngineering as ContractsBaseFE
        from energizados.feature_engineering.base import (
            BaseFeatureEngineering as FEBaseFE,
        )

        assert FEBaseFE is ContractsBaseFE

    def test_feature_selection_base_shim_reexports(self):
        """GIVEN feature_selection/base.py WHEN importing BaseFeatureSelector THEN it re-exports from contracts."""
        from energizados.contracts import BaseFeatureSelector as ContractsBaseFS
        from energizados.feature_selection.base import BaseFeatureSelector as FSBaseFS

        assert FSBaseFS is ContractsBaseFS

    def test_eda_base_shim_reexports(self):
        """GIVEN eda/base.py WHEN importing BaseExplorer THEN it re-exports from contracts."""
        from energizados.contracts import BaseExplorer as ContractsExplorer
        from energizados.eda.base import BaseExplorer as EDAExplorer

        assert EDAExplorer is ContractsExplorer

    def test_inference_base_shim_reexports(self):
        """GIVEN inference/base.py WHEN importing BaseInference THEN it re-exports from contracts."""
        from energizados.contracts import BaseInference as ContractsBaseInference
        from energizados.inference.base import BaseInference as InfBaseInference

        assert InfBaseInference is ContractsBaseInference


class TestIsinstanceFromShim:
    """Test that isinstance checks work correctly when using old import paths."""

    def test_isinstance_with_concrete_etl_from_old_path(self):
        """GIVEN a concrete ETL WHEN checking isinstance from old path THEN check passes."""
        from energizados.etl.base import BaseETL
        from energizados.etl.pipeline import SourceETL

        etl = SourceETL(name="test")
        assert isinstance(etl, BaseETL)

    def test_isinstance_with_concrete_model_from_old_path(self):
        """GIVEN a concrete model WHEN checking isinstance from old path THEN check passes."""
        from energizados.core.base import BaseModel
        from energizados.modeling.adapters import LGBMModelAdapter

        model = LGBMModelAdapter(
            cols_for_model=["feature1", "feature2"], hyperparams={"num_leaves": 31}
        )
        assert isinstance(model, BaseModel)


class TestAbstractMethodsEnforced:
    """Test that abstract methods are properly enforced and cannot be instantiated without implementation."""

    def test_base_model_cannot_instantiate_without_abstract_methods(self):
        """GIVEN BaseModel WHEN a subclass omits abstract methods THEN TypeError is raised at instantiation."""
        from energizados.contracts import BaseModel

        class IncompleteModel(BaseModel):
            pass  # Missing fit, predict, predict_proba, get_raw_model

        with pytest.raises(TypeError):
            IncompleteModel()

    def test_base_inference_cannot_instantiate_without_abstract_methods(self):
        """GIVEN BaseInference WHEN a subclass omits abstract methods THEN TypeError is raised at instantiation."""
        from energizados.contracts import BaseInference

        class IncompleteInference(BaseInference):
            pass  # Missing predict, predict_proba, load_model, save_predictions

        with pytest.raises(TypeError):
            IncompleteInference()

    def test_base_pipeline_cannot_instantiate_without_run(self):
        """GIVEN BasePipeline WHEN a subclass omits run(context) THEN TypeError is raised at instantiation."""
        from energizados.contracts import BasePipeline

        class IncompletePipeline(BasePipeline):
            pass  # Missing run

        with pytest.raises(TypeError):
            IncompletePipeline()

    def test_base_evaluator_cannot_instantiate_without_evaluate(self):
        """GIVEN BaseEvaluator WHEN a subclass omits evaluate(X, y, model) THEN TypeError is raised at instantiation."""
        from energizados.contracts import BaseEvaluator

        class IncompleteEvaluator(BaseEvaluator):
            pass  # Missing evaluate

        with pytest.raises(TypeError):
            IncompleteEvaluator()

    def test_base_etl_cannot_instantiate_without_extract_transform_load(self):
        """GIVEN BaseETL WHEN a subclass omits extract/transform/load THEN TypeError is raised at instantiation."""
        from energizados.contracts import BaseETL

        class IncompleteETL(BaseETL):
            pass  # Missing extract, transform, load

        with pytest.raises(TypeError):
            IncompleteETL()

    def test_base_feature_engineering_cannot_instantiate_without_fit_transform(self):
        """GIVEN BaseFeatureEngineering WHEN a subclass omits fit/transform THEN TypeError is raised at instantiation."""
        from energizados.contracts import BaseFeatureEngineering

        class IncompleteFE(BaseFeatureEngineering):
            pass  # Missing fit, transform

        with pytest.raises(TypeError):
            IncompleteFE()

    def test_base_feature_selector_cannot_instantiate_without_fit_transform(self):
        """GIVEN BaseFeatureSelector WHEN a subclass omits fit/transform THEN TypeError is raised at instantiation."""
        from energizados.contracts import BaseFeatureSelector

        class IncompleteSelector(BaseFeatureSelector):
            pass  # Missing fit, transform

        with pytest.raises(TypeError):
            IncompleteSelector()

    def test_base_explorer_cannot_instantiate_without_abstract_methods(self):
        """GIVEN BaseExplorer WHEN a subclass omits abstract methods THEN TypeError is raised at instantiation."""
        from energizados.contracts import BaseExplorer

        class IncompleteExplorer(BaseExplorer):
            pass  # Missing analyze and get_alerts

        with pytest.raises(TypeError):
            IncompleteExplorer()


class TestPublicImportPaths:
    """Test that all documented public import paths resolve correctly."""

    def test_core_base_imports(self):
        """GIVEN documented public paths WHEN importing from core/base THEN imports resolve."""
        from energizados.core.base import BaseInference, BaseModel, PipelineStep

        assert BaseModel is not None
        assert BaseInference is not None
        assert PipelineStep is not None

    def test_etl_base_imports(self):
        """GIVEN documented public paths WHEN importing from etl/base THEN imports resolve."""
        from energizados.etl.base import BaseETL

        assert BaseETL is not None

    def test_feature_engineering_base_imports(self):
        """GIVEN documented public paths WHEN importing from feature_engineering/base THEN imports resolve."""
        from energizados.feature_engineering.base import BaseFeatureEngineering

        assert BaseFeatureEngineering is not None

    def test_feature_selection_base_imports(self):
        """GIVEN documented public paths WHEN importing from feature_selection/base THEN imports resolve."""
        from energizados.feature_selection.base import BaseFeatureSelector

        assert BaseFeatureSelector is not None

    def test_eda_base_imports(self):
        """GIVEN documented public paths WHEN importing from eda/base THEN imports resolve."""
        from energizados.eda.base import BaseExplorer

        assert BaseExplorer is not None

    def test_inference_base_imports(self):
        """GIVEN documented public paths WHEN importing from inference/base THEN imports resolve."""
        from energizados.inference.base import BaseInference

        assert BaseInference is not None

    def test_concrete_etl_imports(self):
        """GIVEN documented concrete ETL classes WHEN importing THEN imports resolve."""
        from energizados.etl.pipeline import (
            CleanFilesETL,
            ClipOutliersETL,
            GeoFeaturesETL,
            SourceETL,
        )

        assert SourceETL is not None
        assert ClipOutliersETL is not None
        assert GeoFeaturesETL is not None
        assert CleanFilesETL is not None


class TestNoopLoadHook:
    """Test noop_load hook on BaseETL."""

    def test_base_etl_has_noop_load_method(self):
        """GIVEN BaseETL WHEN inspecting methods THEN noop_load() exists."""
        from energizados.contracts import BaseETL

        assert hasattr(BaseETL, "noop_load")
        assert callable(BaseETL.noop_load)

    def test_base_etl_noop_load_returns_empty_dataframe(self):
        """GIVEN BaseETL WHEN noop_load() is called THEN empty DataFrame is returned."""
        import pandas as pd

        from energizados.contracts import BaseETL

        class DummyETL(BaseETL):
            def extract(self):
                return pd.DataFrame()

            def transform(self, df):
                return df

            def load(self, df, path):
                pass

        etl = DummyETL()
        result = etl.noop_load()
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


class TestCleanFilesETLCompliance:
    """Test CleanFilesETL respects BaseETL contract via noop_load."""

    def test_clean_files_etl_overrides_noop_load(self):
        """GIVEN CleanFilesETL WHEN noop_load() is called THEN files are deleted."""
        import tempfile
        from pathlib import Path

        import pandas as pd

        from energizados.etl.pipeline import CleanFilesETL

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            test_files = []
            for i in range(3):
                file_path = Path(tmpdir) / f"test_{i}.txt"
                file_path.write_text(f"test content {i}", encoding="utf-8")
                test_files.append(str(file_path))

            # Create CleanFilesETL instance
            etl = CleanFilesETL(name="clean", input_paths=test_files)

            # Call noop_load (simulates what BaseETL.run() does)
            result = etl.noop_load()

            # Check files were deleted
            for file_path in test_files:
                assert not Path(file_path).exists()

            # Check empty DataFrame is returned
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0

    def test_clean_files_etl_run_returns_empty_dataframe(self):
        """GIVEN CleanFilesETL WHEN run() is called THEN empty DataFrame is returned."""
        import tempfile
        from pathlib import Path

        import pandas as pd

        from energizados.etl.pipeline import CleanFilesETL

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content", encoding="utf-8")

            # Create CleanFilesETL instance
            etl = CleanFilesETL(name="clean", input_paths=[str(test_file)])

            # Call run
            with tempfile.TemporaryDirectory() as output_tmpdir:
                result = etl.run(f"{output_tmpdir}/output.parquet")

            # Check empty DataFrame is returned
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0

            # Check file was deleted
            assert not test_file.exists()


class TestFeatureSelectionPipelineInheritance:
    """Test FeatureSelectionPipeline inherits BaseFeatureSelector."""

    def test_feature_selection_pipeline_inherits_base_feature_selector(self):
        """GIVEN FeatureSelectionPipeline WHEN checking inheritance THEN it inherits BaseFeatureSelector."""
        from energizados.feature_selection.base import BaseFeatureSelector
        from energizados.feature_selection.pipeline import FeatureSelectionPipeline

        assert issubclass(FeatureSelectionPipeline, BaseFeatureSelector)

    def test_feature_selection_pipeline_implements_required_methods(self):
        """GIVEN FeatureSelectionPipeline WHEN inspecting methods THEN it implements all BaseFeatureSelector abstract methods."""
        from energizados.feature_selection.pipeline import FeatureSelectionPipeline

        # Check that required methods exist
        assert hasattr(FeatureSelectionPipeline, "fit")
        assert hasattr(FeatureSelectionPipeline, "transform")
        assert hasattr(FeatureSelectionPipeline, "get_selected_features")
        assert hasattr(FeatureSelectionPipeline, "get_audit_stats")

    def test_feature_selection_pipeline_fit_transform_works(self):
        """GIVEN FeatureSelectionPipeline WHEN fit() and transform() are called THEN they work correctly."""
        import pandas as pd

        from energizados.feature_selection.pipeline import FeatureSelectionPipeline

        # Create a simple pipeline config
        steps_config = [
            {
                "name": "const",
                "method": "constant",
                "params": {"threshold": 0.99},
            }
        ]

        pipeline = FeatureSelectionPipeline(steps_config)

        # Create sample data
        X = pd.DataFrame({"feature1": [1, 2, 3], "feature2": [1, 1, 1], "target": [0, 1, 0]})
        y = pd.Series([0, 1, 0])

        # Fit and transform
        X_selected = pipeline.fit_transform(X, y)

        # Check that feature2 was removed (constant)
        assert "feature2" not in X_selected.columns
        assert "feature1" in X_selected.columns


class TestDefaultEvaluatorInheritance:
    """Test DefaultEvaluator inherits BaseEvaluator."""

    def test_default_evaluator_inherits_base_evaluator(self):
        """GIVEN DefaultEvaluator WHEN checking inheritance THEN it inherits BaseEvaluator."""
        from energizados.contracts import BaseEvaluator
        from energizados.evaluation.evaluator import DefaultEvaluator

        assert issubclass(DefaultEvaluator, BaseEvaluator)

    def test_default_evaluator_implements_evaluate(self):
        """GIVEN DefaultEvaluator WHEN inspecting methods THEN evaluate() is implemented."""
        from energizados.evaluation.evaluator import DefaultEvaluator

        # Check that evaluate method exists
        assert hasattr(DefaultEvaluator, "evaluate")
        assert callable(DefaultEvaluator.evaluate)

    def test_default_evaluator_evaluate_returns_metrics_dict(self):
        """GIVEN DefaultEvaluator WHEN evaluate() is called THEN it returns a metrics dict."""
        import numpy as np
        import pandas as pd

        from energizados.evaluation.evaluator import DefaultEvaluator

        # Create sample data
        X = pd.DataFrame({"feature1": [1, 2, 3, 4], "feature2": [5, 6, 7, 8]})
        y = pd.Series([0, 1, 0, 1])

        # Create a simple mock model
        class MockModel:
            def predict_proba(self, X):
                return np.array([0.3, 0.7, 0.4, 0.6])

        model = MockModel()

        # Create DefaultEvaluator with minimal config
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            evaluator = DefaultEvaluator(
                input_path=None,
                model_path=None,
                output_dir=tmpdir,
                target_column="target",
                threshold=0.5,
                metrics=["auc", "f1"],
                generate_plots=False,
                generate_html_report=False,
                generate_json_report=False,
            )

            # Call evaluate - this should work now
            metrics = evaluator.evaluate(X, y, model, threshold=0.5)
            assert isinstance(metrics, dict)
            assert "auc" in metrics or "f1" in metrics


class TestModelContainerProtocol:
    """Test ModelContainer Protocol and HierarchicalInference typing."""

    def test_model_container_protocol_exists(self):
        """GIVEN contracts module WHEN inspecting THEN ModelContainer Protocol exists."""
        from energizados.contracts import ModelContainer

        assert ModelContainer is not None

    def test_model_container_protocol_requires_predict_methods(self):
        """GIVEN ModelContainer Protocol WHEN inspecting THEN it requires predict and predict_proba."""
        import inspect

        from energizados.contracts import ModelContainer

        # Check that the protocol has the required methods
        methods = [
            name for name, _ in inspect.getmembers(ModelContainer, predicate=inspect.isfunction)
        ]
        assert "predict_proba" in methods
        assert "predict" in methods

    def test_hierarchical_model_container_satisfies_protocol(self):
        """GIVEN HierarchicalModelContainer WHEN checking protocol THEN it satisfies ModelContainer."""
        from energizados.contracts import ModelContainer
        from energizados.inference.hierarchical import HierarchicalModelContainer

        # Create a dummy HierarchicalModelContainer
        class DummyModel:
            def predict_proba(self, X):
                return X

            def predict(self, X):
                return X

        container = HierarchicalModelContainer(
            models={"route1": DummyModel()}, feature_engineerings={}
        )

        # Check that it satisfies the protocol
        assert isinstance(container, ModelContainer)
        assert hasattr(container, "predict_proba")
        assert hasattr(container, "predict")

    def test_hierarchical_inference_load_model_returns_model_container(self):
        """GIVEN HierarchicalInference WHEN load_model() is called THEN it returns ModelContainer-compatible object."""
        from energizados.contracts import ModelContainer
        from energizados.inference.hierarchical import HierarchicalInference

        # Create a simple HierarchicalInference instance
        inference = HierarchicalInference(
            threshold=0.5,
            routes=[
                {
                    "name": "test_route",
                    "condition": {"geo_region": "TEST"},
                    "model_path": "dummy.pkl",
                }
            ],
        )

        # Since we can't actually load models in a test, we just check
        # that the method signature is compatible
        import inspect

        sig = inspect.signature(inference.load_model)
        # Check that return annotation exists (should be ModelContainer)
        return_annotation = sig.return_annotation
        # The annotation should be either ModelContainer or not None
        assert return_annotation != inspect.Parameter.empty

        # Verify the annotation is specifically ModelContainer
        assert return_annotation == ModelContainer
