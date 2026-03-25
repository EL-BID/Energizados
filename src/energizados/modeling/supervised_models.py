"""
This module contains implementations of supervised models used in the machine learning project.

The implemented models are:

- LGBMModel: Implements a Gradient Boosting model with LightGBM.
- CATModel: Implements a Gradient Boosting model with CatBoost.
- NNModel: Implements a Neural Network model.

Each model has methods for training and making predictions.

Note: This module requires LightGBM for gradient boosting models. CatBoost is an optional
dependency required only for CATModel (install with: pip install energizados[catboost]).
TensorFlow is only required for neural network models (NNModel and LSTMNNModel)
(install with: pip install energizados[tensorflow]).

"""

import logging
import re

import numpy as np
from imblearn.combine import SMOTETomek
from imblearn.over_sampling import RandomOverSampler
from imblearn.pipeline import Pipeline, make_pipeline
from imblearn.under_sampling import RandomUnderSampler
from lightgbm import LGBMClassifier, early_stopping, log_evaluation
from scipy.stats import randint as sp_randint
from scipy.stats import uniform as sp_uniform
from sklearn.model_selection import RandomizedSearchCV, train_test_split
from sklearn.preprocessing import MinMaxScaler

from energizados.preprocessing.preprocessing import MinMaxScalerRow

logger = logging.getLogger(__name__)


def _sanitize_feature_names(df):
    """Remove special JSON characters from column names for LightGBM compatibility.

    LightGBM does not support special JSON characters in feature names:
    { } [ ] : , "

    Args:
        df: DataFrame with potentially problematic column names.

    Returns:
        DataFrame with sanitized column names.
    """
    df = df.copy()
    pattern = r'[{}\[\]:,"]'
    df.columns = [re.sub(pattern, "_", str(col)) for col in df.columns]
    return df


class LGBMModel:
    """LightGBM classifier with imbalanced-learn sampling support.

    Wraps LGBMClassifier in an imblearn pipeline with optional
    RandomUnderSampler or RandomOverSampler and optional hyperparameter search.
    """

    def __init__(
        self,
        cols_for_model,
        hyperparams,
        search_hip=False,
        sampling_th=0.5,
        sampling_method="undersample",
        n_iter=60,
        cv=3,
        class_weight=None,
    ):
        """
        Initializes the LGBMModel.

        Args:
            cols_for_model (list): The columns to be used for modeling.
            hyperparams: The hyperparameters for the LGBMClassifier.
            search_hip (bool): Flag indicating whether to perform hyperparameter search.
            sampling_th (float): The sampling threshold.
            sampling_method (str): The sampling method ('over' or 'under').
            n_iter (int): Number of iterations for RandomizedSearchCV.
            cv (int): Number of cross-validation folds for RandomizedSearchCV.
        """
        self.cols_for_model = cols_for_model
        self.sampling_th = sampling_th
        self.sampling_method = sampling_method
        self.search_hip = search_hip
        self.hyperparams = hyperparams
        self.n_iter = n_iter
        self.cv = cv
        self.class_weight = class_weight

    def build_pipeline_preproceso_model(self):
        """Build an imblearn pipeline with LGBMClassifier and optional sampler.

        Returns:
            imblearn.pipeline.Pipeline: Pipeline with optional sampler followed by
                LGBMClassifier.
        """
        lgbm_model_search = LGBMClassifier(
            random_state=314,
            metric="None",
            n_estimators=1000,
            verbosity=-1,
            class_weight=self.class_weight,
        )
        if self.class_weight is not None:
            return make_pipeline(lgbm_model_search)
        if self.sampling_method == "oversample":
            over = RandomOverSampler(sampling_strategy=self.sampling_th, random_state=40)
            return make_pipeline(over, lgbm_model_search)
        elif self.sampling_method == "undersample":
            under = RandomUnderSampler(sampling_strategy=self.sampling_th, random_state=40)
            return make_pipeline(under, lgbm_model_search)
        elif self.sampling_method == "smotetomek":
            smt = SMOTETomek(sampling_strategy=self.sampling_th, random_state=40)
            return make_pipeline(smt, lgbm_model_search)
        else:
            return make_pipeline(lgbm_model_search)

    def train(self, df_train, y_train, df_val=None, y_val=None):
        """Train the LightGBM pipeline.

        If no validation set is provided, 10% of the training data is reserved
        for early stopping. Optionally performs hyperparameter search first.

        Args:
            df_train: Training feature DataFrame.
            y_train: Training target Series.
            df_val: Validation feature DataFrame (optional).
            y_val: Validation target Series (optional).

        Returns:
            imblearn.pipeline.Pipeline: Fitted pipeline with sampler and LGBMClassifier.
        """
        if df_val is None:
            df_train, df_val, y_train, y_val = train_test_split(
                df_train, y_train, test_size=0.1, random_state=42
            )

        X_train = df_train[self.cols_for_model].copy()
        X_val = df_val[self.cols_for_model].copy()

        X_train = _sanitize_feature_names(X_train)
        X_val = _sanitize_feature_names(X_val)

        pipe_preproceso_model = self.build_pipeline_preproceso_model()

        if self.search_hip:
            self.best_score_, self.hyperparams = self.find_hyp_lgbm_model(
                X_train, y_train, X_val, y_val, pipe_preproceso_model
            )

        params = self.hyperparams
        import logging as _logging

        _lgbm_verbose = _logging.getLogger().level <= _logging.INFO
        fit_params = {
            "eval_metric": ["auc"],
            "eval_set": [(X_val, y_val)],
            "eval_names": ["valid"],
            "callbacks": [
                early_stopping(stopping_rounds=30, first_metric_only=True, verbose=_lgbm_verbose),
                log_evaluation(0),
            ],
            "categorical_feature": "auto",
            "feature_name": "auto",
        }
        new_fit_params = {"lgbmclassifier__" + key: fit_params[key] for key in fit_params}
        # Prefix raw YAML params with step name; search_hip returns already-prefixed best_params_
        prefixed_params = {
            (k if "__" in k else f"lgbmclassifier__{k}"): v for k, v in params.items()
        }
        pipe_preproceso_model.set_params(**prefixed_params)
        pipe_preproceso_model.fit(X_train, y_train, **new_fit_params)

        return pipe_preproceso_model

    def find_hyp_lgbm_model(self, X_train, y_train, X_val, y_val, imba_pipeline):
        """Run RandomizedSearchCV to find optimal LightGBM hyperparameters.

        Args:
            X_train: Training feature DataFrame.
            y_train: Training target Series.
            X_val: Validation feature DataFrame (not used in CV phase to avoid leakage).
            y_val: Validation target Series (not used in CV phase to avoid leakage).
            imba_pipeline: imblearn pipeline containing the LGBMClassifier.

        Returns:
            tuple: (best_score, best_params) from the randomized search.
        """
        X_train = _sanitize_feature_names(X_train)
        search_fit_params = {
            "categorical_feature": "auto",
            "feature_name": "auto",
        }

        param_test = {
            "num_leaves": sp_randint(6, 50),
            "max_bin": sp_randint(60, 255),
            "max_depth": sp_randint(5, 20),
            "min_child_samples": sp_randint(100, 500),
            "min_child_weight": [1e-5, 1e-3, 1e-2, 1e-1, 1, 1e1, 1e2, 1e3, 1e4],
            "subsample": sp_uniform(loc=0.2, scale=0.8),
            "colsample_bytree": sp_uniform(loc=0.4, scale=0.6),
            "reg_alpha": [0, 1e-1, 1, 2, 5, 7, 10, 50, 100],
            "reg_lambda": [0, 1e-5, 1e-3, 1e-2, 1e-1, 1, 5, 10, 20, 50, 100],
            "scale_pos_weight": [1, 5, 20, 100],
            #             'is_unbalance':[True,False],
            "learning_rate": sp_uniform(loc=0.01, scale=0.1),
            "subsample_freq": sp_randint(5, 20),
        }

        new_params = {"lgbmclassifier__" + key: param_test[key] for key in param_test}
        new_fit_params = {
            "lgbmclassifier__" + key: search_fit_params[key] for key in search_fit_params
        }

        random_imba = RandomizedSearchCV(
            estimator=imba_pipeline,
            param_distributions=new_params,
            cv=self.cv,
            #                            scoring = 'average_precision',
            scoring="roc_auc",
            n_jobs=-1,
            n_iter=self.n_iter,
            refit=True,
            random_state=314,
        )
        random_imba.fit(X_train, y_train, **new_fit_params)
        logger.info(
            "\nBest score reached: {} with params: {} ".format(
                random_imba.best_score_, random_imba.best_params_
            )
        )
        return random_imba.best_score_, random_imba.best_params_


class CATModel:
    """CatBoost classifier with imbalanced-learn sampling support.

    Wraps CatBoostClassifier in an imblearn pipeline with optional
    RandomUnderSampler or RandomOverSampler and optional hyperparameter search.
    """

    def __init__(
        self,
        cols_for_model,
        hyperparams,
        search_hip=False,
        sampling_th=0.5,
        preprocesor_num=3,
        sampling_method="undersample",
        n_iter=60,
        cv=3,
        class_weight=None,
    ):
        """Initialize CATModel.

        Args:
            cols_for_model: List of feature column names to use.
            hyperparams: CatBoost hyperparameter dict.
            search_hip: If True, run hyperparameter search before training.
            sampling_th: Sampling ratio for the sampler.
            preprocesor_num: Unused legacy parameter.
            sampling_method: Sampling strategy ('over', 'under', 'smotetomek', or other for no sampling).
            n_iter: Number of iterations for RandomizedSearchCV.
            cv: Number of cross-validation folds.
            class_weight: Class weights for CatBoost (dict like {0: 1, 1: 10} or "balanced").
        """
        self.cols_for_model = cols_for_model
        self.sampling_th = sampling_th
        self.preprocesor_num = preprocesor_num
        self.sampling_method = sampling_method
        self.search_hip = search_hip
        self.hyperparams = hyperparams
        self.n_iter = n_iter
        self.cv = cv
        self.class_weight = class_weight

    def build_pipeline_preproceso_model(self, cat_features):
        """Build an imblearn pipeline with CatBoostClassifier and optional sampler.

        Args:
            cat_features: List of categorical feature column names.

        Returns:
            imblearn.pipeline.Pipeline: Pipeline with optional sampler followed by
                CatBoostClassifier.
        """
        try:
            import catboost as cb  # Lazy import - only load when training CATModel
        except ImportError:
            raise ImportError(
                "catboost is required for CATModel. "
                "Install it with: pip install energizados[catboost]"
            )
        cb_model_search = cb.CatBoostClassifier(
            iterations=1000,
            eval_metric="AUC",
            loss_function="Logloss",
            random_seed=42,
            cat_features=cat_features,
            logging_level="Silent",
            class_weights=self.class_weight,
        )
        if self.class_weight is not None:
            return make_pipeline(cb_model_search)
        if self.sampling_method == "oversample":
            over = RandomOverSampler(sampling_strategy=self.sampling_th, random_state=40)
            return make_pipeline(over, cb_model_search)
        elif self.sampling_method == "undersample":
            under = RandomUnderSampler(sampling_strategy=self.sampling_th, random_state=40)
            return make_pipeline(under, cb_model_search)
        elif self.sampling_method == "smotetomek":
            smt = SMOTETomek(sampling_strategy=self.sampling_th, random_state=40)
            return make_pipeline(smt, cb_model_search)
        else:
            return make_pipeline(cb_model_search)

    def train(self, df_train, y_train, df_val=None, y_val=None):
        """Train the CatBoost pipeline.

        If no validation set is provided, 10% of the training data is reserved
        for early stopping. Optionally performs hyperparameter search first.

        Args:
            df_train: Training feature DataFrame.
            y_train: Training target Series.
            df_val: Validation feature DataFrame (optional).
            y_val: Validation target Series (optional).

        Returns:
            imblearn.pipeline.Pipeline: Fitted pipeline with sampler and CatBoostClassifier.
        """
        if df_val is None:
            df_train, df_val, y_train, y_val = train_test_split(
                df_train, y_train, test_size=0.1, random_state=42
            )

        cat_features = (
            df_train[self.cols_for_model]
            .select_dtypes(include=["object", "category"])
            .columns.tolist()
        )

        if self.sampling_method not in ["oversample", "undersample", "smotetomek"]:
            logger.warning(
                "sampling_method '%s' is not one of ['oversample', 'undersample', 'smotetomek']."
                " No resampling will be applied.",
                self.sampling_method,
            )

        pipe_preproceso_model = self.build_pipeline_preproceso_model(cat_features)

        if self.search_hip:
            self.best_score_, self.hyperparams = self.find_hyp_catboost_model(
                df_train[self.cols_for_model],
                y_train,
                df_val[self.cols_for_model],
                y_val,
                pipe_preproceso_model,
            )

        _catboost_logging_params = {"verbose", "logging_level", "verbose_eval", "silent"}
        params = {
            (key if key.startswith("catboostclassifier__") else "catboostclassifier__" + key): value
            for key, value in self.hyperparams.items()
            if key not in _catboost_logging_params
        }
        fit_params = {
            "eval_set": [(df_val[self.cols_for_model], y_val)],
            "early_stopping_rounds": 30,
        }
        new_fit_params = {"catboostclassifier__" + key: fit_params[key] for key in fit_params}
        pipe_preproceso_model.set_params(**params)
        pipe_preproceso_model.fit(df_train[self.cols_for_model], y_train, **new_fit_params)
        return pipe_preproceso_model

    def find_hyp_catboost_model(self, X_train, y_train, X_val, y_val, imba_catboost):
        """Run RandomizedSearchCV to find optimal CatBoost hyperparameters.

        Args:
            X_train: Training feature DataFrame.
            y_train: Training target Series.
            X_val: Validation feature DataFrame (not used in CV phase to avoid leakage).
            y_val: Validation target Series (not used in CV phase to avoid leakage).
            imba_catboost: imblearn pipeline containing the CatBoostClassifier.

        Returns:
            tuple: (best_score, best_params) from the randomized search.
        """
        # Phase 1 (search): do NOT pass eval_set so early stopping does not use the
        # held-out validation set during CV — that would leak val into hyperparameter selection.
        # The final model is retrained with eval_set in train() (Phase 2).
        param_test = {
            "depth": sp_randint(4, 16),
            #     'min_child_samples': sp_randint(100,500),
            "learning_rate": sp_uniform(loc=0.01, scale=0.1),
            "l2_leaf_reg": sp_uniform(loc=1, scale=100),
            "border_count": [50, 128, 254],
            #     'subsample': sp_uniform(loc=0.2, scale=0.8),
            "bagging_temperature": [0, 1, 10, 100],
        }

        new_params = {"catboostclassifier__" + key: param_test[key] for key in param_test}

        random_imba = RandomizedSearchCV(
            estimator=imba_catboost,
            param_distributions=new_params,
            cv=self.cv,
            scoring="roc_auc",
            n_jobs=-1,
            n_iter=self.n_iter,
            refit=True,
            random_state=314,
        )

        random_imba.fit(X_train, y_train)
        logger.info(
            "\nBest score reached: {} with params: {} ".format(
                random_imba.best_score_, random_imba.best_params_
            )
        )
        return random_imba.best_score_, random_imba.best_params_


class NNModel:
    """Feedforward neural network model for binary classification.

    Builds a Dense network that concatenates scaled categorical features with
    row-wise Min-Max scaled consumption sequences. Uses TensorFlow/Keras.
    """

    def __init__(
        self,
        features_names,
        spents_names,
        search_hip=False,
        sampling_th=0.5,
        preprocesor_num=3,
        sampling_method="undersample",
    ):
        """
        Class for a feedforward neural network model.

        Args:
        - features_names: list of feature names.
        - spents_names: list of consumption names.
        - search_hip: boolean indicating whether to search for hyperparameters (optional).
        - sampling_th: sampling threshold for the sampling method (optional).
        - preprocesor_num: preprocessor number to use (optional).
        - sampling_method: sampling method to use ('over' or 'under') (optional).
        """
        self.features_names = features_names
        self.spents_names = spents_names
        self.sampling_th = sampling_th
        self.preprocesor_num = preprocesor_num
        self.sampling_method = sampling_method
        self.search_hip = search_hip
        #             self.hyperparams = hyperparams

        self.EPOCHS = 1000
        self.BATCH_SIZE = 2048

    def build_pipeline_preproceso(self):
        """Build pipelines for feature scaling and optional resampling.

        Returns:
            tuple: (pipe_features, pipe_spent, random_sampler) where pipe_features
                applies MinMaxScaler to categorical features, pipe_spent applies
                MinMaxScalerRow to consumption sequences, and random_sampler is an
                imblearn sampler or None if no sampling is requested.
        """
        # Data arriving here is already preprocessed by the framework's DefaultFeatureEngineering
        pipe_features = Pipeline([("scaler", MinMaxScaler())])

        pipe_spent = Pipeline([("scaler", MinMaxScalerRow())])

        if self.sampling_method == "oversample":
            ramdom_s = RandomOverSampler(sampling_strategy=self.sampling_th, random_state=40)
        elif self.sampling_method == "undersample":
            ramdom_s = RandomUnderSampler(sampling_strategy=self.sampling_th, random_state=40)
        elif self.sampling_method == "smotetomek":
            ramdom_s = SMOTETomek(sampling_strategy=self.sampling_th, random_state=40)
        else:
            ramdom_s = None

        return pipe_features, pipe_spent, ramdom_s

    def train(self, df_train, y_train, df_val=None, y_val=None):
        """Train the feedforward neural network.

        Scales features and consumption, optionally resamples for class balance,
        then trains with early stopping on validation precision-recall AUC.

        Args:
            df_train: Training feature DataFrame.
            y_train: Training target Series.
            df_val: Validation feature DataFrame (optional).
            y_val: Validation target Series (optional).

        Returns:
            tuple: (keras_model, pipe_features, pipe_spent)
        """
        if df_val is None:
            df_train, df_val, y_train, y_val = train_test_split(
                df_train, y_train, test_size=0.1, random_state=42
            )

        pipe_features, pipe_spent, ramdom_s = self.build_pipeline_preproceso()

        X_train_features = pipe_features.fit_transform(df_train[self.features_names], y_train)
        X_train_spents = pipe_spent.fit_transform(df_train[self.spents_names], y_train)

        X_val_features = pipe_features.transform(df_val[self.features_names])
        X_val_spents = pipe_spent.transform(df_val[self.spents_names])

        X_train_features = np.concatenate([X_train_features, X_train_spents], axis=1)
        X_val_features = np.concatenate([X_val_features, X_val_spents], axis=1)

        if ramdom_s is not None:
            X_resample, y_resample = ramdom_s.fit_resample(X_train_features, y_train)
        else:
            X_resample, y_resample = X_train_features, y_train

        rnn_final_model = self.train_rnn_model(
            X_resample, y_resample, X_val_features, y_val, output_bias=None
        )
        return rnn_final_model, pipe_features, pipe_spent

    def train_rnn_model(self, X_train, y_train, X_val, y_val, output_bias=None):
        """Build and train the Keras feedforward neural network.

        Architecture: Dense(512) → Dense(64) → Dense(32) → Dense(16) → Dense(1, sigmoid).
        Early stopping on val_prc with patience=50.

        Args:
            X_train: Preprocessed training feature matrix.
            y_train: Training target array.
            X_val: Preprocessed validation feature matrix.
            y_val: Validation target array.
            output_bias: Optional initial bias for the output layer.

        Returns:
            tf.keras.Model: Trained Keras model.
        """
        import tensorflow as tf  # Lazy import - only load when training NN

        y_train = np.asarray(y_train)
        y_val = np.asarray(y_val)
        METRICS = [
            tf.keras.metrics.AUC(name="auc"),
            tf.keras.metrics.AUC(name="prc", curve="PR"),
        ]
        early_stopping = tf.keras.callbacks.EarlyStopping(
            monitor="val_prc", verbose=1, patience=50, mode="max", restore_best_weights=True
        )

        if output_bias is not None:
            output_bias = tf.keras.initializers.Constant(output_bias)

        model = tf.keras.Sequential(
            [
                tf.keras.layers.Dense(
                    512,
                    #                           kernel_regularizer=tf.keras.regularizers.l2(0.0001),
                    activation="relu",
                    input_shape=(X_train.shape[-1],),
                ),
                #     tf.keras.layers.Dropout(0.5),
                tf.keras.layers.Dense(
                    64,
                    #                           kernel_regularizer=tf.keras.regularizers.l2(0.0001),
                    activation="relu",
                ),
                #     tf.keras.layers.Dropout(0.5),
                tf.keras.layers.Dense(
                    32,
                    #                           kernel_regularizer=tf.keras.regularizers.l2(0.0001),
                    activation="relu",
                ),
                #     tf.keras.layers.Dropout(0.5),
                tf.keras.layers.Dense(
                    16,
                    #                           kernel_regularizer=tf.keras.regularizers.l2(0.0001),
                    activation="relu",
                ),
                #     tf.keras.layers.Dropout(0.5),
                tf.keras.layers.Dense(1, activation="sigmoid", bias_initializer=output_bias),
            ]
        )

        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
            loss=tf.keras.losses.BinaryCrossentropy(),
            metrics=METRICS,
        )

        _ = model.fit(
            X_train,
            y_train,
            batch_size=self.BATCH_SIZE,
            epochs=self.EPOCHS,
            callbacks=[early_stopping],
            validation_data=(X_val, y_val),
            verbose=0,
        )
        return model


class LSTMNNModel:
    """LSTM neural network model for binary classification with sequential consumption data.

    Combines an LSTM branch processing row-wise scaled consumption sequences with a Dense
    branch processing categorical features. Uses TensorFlow/Keras with early stopping on
    validation precision-recall AUC.
    """

    def __init__(
        self,
        features_names,
        spents_names,
        search_hip=False,
        sampling_th=0.5,
        preprocesor_num=3,
        sampling_method="undersample",
    ):
        """
        Class for an LSTM neural network model.

        Args:
        - features_names: list of feature names.
        - spents_names: list of spending names.
        - search_hip: boolean indicating whether to search for hyperparameters (optional).
        - sampling_th: sampling threshold (optional).
        - preprocesor_num: preprocessor number to use (optional).
        - sampling_method: sampling method to use (optional).
        """
        self.features_names = features_names
        self.spents_names = spents_names
        self.sampling_th = sampling_th
        self.preprocesor_num = preprocesor_num
        self.sampling_method = sampling_method
        self.search_hip = search_hip
        #             self.hyperparams = hyperparams
        self.periodo = 12
        self.EPOCHS = 1000
        self.BATCH_SIZE = 2048

    def build_pipeline_preproceso(self):
        """Build pipelines for feature scaling and optional resampling.

        Returns:
            tuple: (pipe_features, pipe_spent, random_sampler) where pipe_features applies
                MinMaxScaler to categorical features, pipe_spent applies MinMaxScalerRow to
                consumption sequences, and random_sampler is an imblearn sampler or None.
        """
        # Data arriving here is already preprocessed by the framework's DefaultFeatureEngineering
        pipe_features = Pipeline([("scaler", MinMaxScaler())])

        pipe_spent = Pipeline([("scaler", MinMaxScalerRow())])

        if self.sampling_method == "oversample":
            ramdom_s = RandomOverSampler(sampling_strategy=self.sampling_th, random_state=40)
        elif self.sampling_method == "undersample":
            ramdom_s = RandomUnderSampler(sampling_strategy=self.sampling_th, random_state=40)
        elif self.sampling_method == "smotetomek":
            ramdom_s = SMOTETomek(sampling_strategy=self.sampling_th, random_state=40)
        else:
            ramdom_s = None

        return pipe_features, pipe_spent, ramdom_s

    def train(self, df_train, y_train, df_val=None, y_val=None):
        """Train the LSTM neural network.

        Scales features and consumption, optionally resamples for class balance, reshapes
        consumption sequences to (samples, periodo, 1) for LSTM input, then trains with
        early stopping on validation precision-recall AUC.

        Args:
            df_train: Training feature DataFrame.
            y_train: Training target Series.
            df_val: Validation feature DataFrame (optional).
            y_val: Validation target Series (optional).

        Returns:
            tuple: (keras_model, pipe_features, pipe_spent)
        """
        if df_val is None:
            df_train, df_val, y_train, y_val = train_test_split(
                df_train, y_train, test_size=0.1, random_state=42
            )

        pipe_features, pipe_spent, ramdom_s = self.build_pipeline_preproceso()

        X_train_features = pipe_features.fit_transform(df_train[self.features_names], y_train)
        X_train_spents = pipe_spent.fit_transform(df_train[self.spents_names], y_train)

        X_val_features = pipe_features.transform(df_val[self.features_names])
        X_val_spents = pipe_spent.transform(df_val[self.spents_names])

        # Convert to numpy arrays if needed (sklearn may return DataFrames)
        if hasattr(X_train_features, "values"):
            X_train_features = X_train_features.values
        if hasattr(X_train_spents, "values"):
            X_train_spents = X_train_spents.values
        if hasattr(X_val_features, "values"):
            X_val_features = X_val_features.values
        if hasattr(X_val_spents, "values"):
            X_val_spents = X_val_spents.values

        X_val_spents = X_val_spents.reshape((X_val_spents.shape[0], self.periodo, 1))

        X_train_features = np.concatenate([X_train_spents, X_train_features], axis=1)
        if ramdom_s is not None:
            X_resample, y_resample = ramdom_s.fit_resample(X_train_features, y_train)
        else:
            X_resample, y_resample = X_train_features, y_train

        X_resample_features = X_resample[:, self.periodo :]
        X_resample_spents = X_resample[:, : self.periodo]
        X_resample_spents = X_resample_spents.reshape((X_resample_spents.shape[0], self.periodo, 1))

        lstm_rnn_final_model = self.train_lstm_rnn_model(
            X_resample_spents, X_resample_features, y_resample, X_val_spents, X_val_features, y_val
        )
        return lstm_rnn_final_model, pipe_features, pipe_spent

    def train_lstm_rnn_model(
        self,
        X_train_spents,
        X_train_features,
        y_train,
        X_val_spents,
        X_val_features,
        y_val,
        output_bias=None,
    ):
        """Build and train the Keras LSTM model.

        Architecture: LSTM(128) on consumption → Concatenate with features → Dense(64) →
        Dropout(0.5) → Dense(32) → Dropout(0.5) → Dense(16) → Dropout(0.5) → Dense(1, sigmoid).
        Early stopping on val_prc with patience=50.

        Args:
            X_train_spents: Consumption sequences shaped (samples, periodo, 1).
            X_train_features: Preprocessed training feature matrix.
            y_train: Training target array.
            X_val_spents: Validation consumption sequences shaped (samples, periodo, 1).
            X_val_features: Preprocessed validation feature matrix.
            y_val: Validation target array.
            output_bias: Optional initial bias for the output layer.

        Returns:
            tf.keras.Model: Trained Keras model with two inputs (spents, features).
        """
        import tensorflow as tf  # Lazy import - only load when training LSTM

        y_train = np.asarray(y_train)
        y_val = np.asarray(y_val)
        METRICS = [
            tf.keras.metrics.AUC(name="auc"),
            tf.keras.metrics.AUC(name="prc", curve="PR"),
        ]
        early_stopping = tf.keras.callbacks.EarlyStopping(
            monitor="val_prc", verbose=1, patience=50, mode="max", restore_best_weights=True
        )

        if output_bias is not None:
            output_bias = tf.keras.initializers.Constant(output_bias)

        spents_inputs = tf.keras.Input(shape=X_train_spents.shape[1:])
        x = tf.keras.layers.LSTM(128, activation="relu")(spents_inputs)
        features_inputs = tf.keras.Input(shape=(int(X_train_features.shape[1]),))

        concat = tf.keras.layers.Concatenate()([features_inputs, x])
        x = tf.keras.layers.Dense(64, activation="relu")(concat)
        x = tf.keras.layers.Dropout(0.5)(x)
        x = tf.keras.layers.Dense(32, activation="relu")(x)
        x = tf.keras.layers.Dropout(0.5)(x)
        x = tf.keras.layers.Dense(16, activation="relu")(x)
        x = tf.keras.layers.Dropout(0.5)(x)
        outputs = tf.keras.layers.Dense(1, activation="sigmoid", bias_initializer=output_bias)(x)

        model = tf.keras.models.Model([spents_inputs, features_inputs], outputs)

        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
            loss=tf.keras.losses.BinaryCrossentropy(),
            metrics=METRICS,
        )

        _ = model.fit(
            [X_train_spents, X_train_features],
            y_train,
            validation_data=([X_val_spents, X_val_features], y_val),
            batch_size=self.BATCH_SIZE,
            epochs=self.EPOCHS,
            #           steps_per_epoch= steps_per_epoch,
            callbacks=[early_stopping],
            verbose=0,
            #           class_weight=class_weight
        )
        return model
