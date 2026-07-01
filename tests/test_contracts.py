"""
Tests for energizados.contracts module.

Tests verify:
- All 8 base classes exist in contracts.py
- Abstract methods are enforced
- Shim re-exports work correctly
- isinstance checks pass from old paths
"""

import pytest


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
