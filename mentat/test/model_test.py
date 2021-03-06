import logging
import unittest

import numpy as np
import os
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")

from mentat import ZDataFrame
from mentat.evaluator import ClassificationEvaluator, RegressionEvaluator
from mentat.model import DNN, LogisticRegression, LinearRegression
from mentat.pipeline import Pipeline
from mentat.preprocessor import StandardScaler, RobustScaler, Dummy
from mentat.trainer import MultiModelTrainer, TrivialTrainer, GridSearchTrainer

DATA_PATH = "../data"
logging.basicConfig(level=logging.INFO)


class ModelTest(unittest.TestCase):

    def setUp(self):
        if not hasattr(self, "initialized"):
            self.bird = ZDataFrame(
                pd.read_csv(DATA_PATH + os.path.sep + "bird.csv"),
                "type",
                ["id"],
                "multiclass"
            ).impute("mean")

            self.pelvis = ZDataFrame(
                pd.read_csv(DATA_PATH + os.path.sep + "column_2C_weka.csv"),
                "class",
                [],
                "binary"
            ).impute("mean")

            self.ghost = ZDataFrame(
                pd.read_csv(DATA_PATH + os.path.sep + "train.csv"),
                "type",
                ["id"],
                "multiclass"
            ).impute("mean")

            x = np.arange(-2 * np.pi, 2 * np.pi, .1)
            true_y = 2. + 3. * x  # np.sin(x)
            y = true_y + np.random.normal(loc=0., scale=.6, size=len(x))
            self.regression_data = ZDataFrame(
                pd.DataFrame({"x": x, "y": y}),
                "y",
            )

            self.initialized = True

    def test_grid_search_trainner(self):
        logging.info("\n\nCASE: TEST GRID-SEARCH TRAINER\n")
        # load and construct the data frame
        data = self.bird

        # number of categories(output size)
        output_size = len(data.category)

        # split the data into train(and test) data set and data set to be predicted
        train_and_test, to_be_predicted = data.split(.7)

        # construct a model(DNN)
        dnn = DNN([40, output_size], ["tanh", "identity"], softmax=True)

        # construct a pipeline contains a standard scaler and a grid search trainer.
        pipeline = Pipeline(
            {
                "preprocessor": StandardScaler(),
                "trainer": GridSearchTrainer(dnn,
                                             params={
                                                 "eta": [0.1, 0.5],
                                                 "max_epochs": [10, 20, 30],
                                                 "momentum": [0.5, 0.7, 0.9]
                                             },
                                             train_fraction=.7,
                                             evaluator=ClassificationEvaluator(),
                                             metric="accuracy")
            }
        )

        # fit the pipeline
        pipeline.fit(train_and_test)

        # metrics of the chosen(best) DNN
        eva = pipeline.get_operator("trainer").get_evaluator()
        logging.info("accuracy: {:.3f}".format(eva["accuracy"]))
        logging.info("confision_matric:\n" + str(eva["confusion_matrix"]))

        grid_metrics = pipeline.get_operator("trainer").metrics

        logging.info("grid-search metrics: \n" + "\n".join(
            list(map(lambda t: str(t[0]) + ": " + str(t[1]), list(grid_metrics.items())))))
        self.assertGreater(eva["accuracy"], 0.70, "accuracy is too low")

    def test_multi_trainer(self):
        logging.info("\n\nCASE: TEST MULTI-MODEL TRAINER\n")
        # load and construct the data frame
        data = self.bird

        # number of categories(output size)
        output_size = len(data.category)

        # split the data into train(and test) data set and data set to be predicted
        train_and_test, to_be_predicted = data.split(.7)

        # construct 3 models(DNN) with different hyper-parameters(size of hidden layer and max epochs here)
        dnns = {
            "dnn_1": DNN([60, output_size], ["relu", "identity"], softmax=True, max_epochs=60),
            "dnn_2": DNN([60, output_size], ["sigmoid", "identity"], softmax=True, max_epochs=60),
            "dnn_3": DNN([40, 40, 40, output_size], ["sigmoid", "sigmoid", "sigmoid", "identity"],
                         softmax=True, max_epochs=60),
            "dnn_4": DNN([40, 40, 40, output_size], ["tanh", "tanh", "tanh", "identity"], eta=.5,
                         softmax=True, max_epochs=60)
        }

        # construct a pipeline contains a standard scaler and a multi-model trainer(train 3 DNN parallel)
        pipeline = Pipeline(
            {
                "preprocessor": StandardScaler(),
                "trainer": MultiModelTrainer(dnns, train_fraction=.7, evaluator=ClassificationEvaluator(),
                                             metric="accuracy")
            }
        )

        # fit the pipeline
        pipeline.fit(train_and_test)

        # metrics of the chosen(best) DNN
        eva = pipeline.get_operator("trainer").get_evaluator()

        logging.info("\nValidation Metrics:")
        logging.info("Accuracy: {:.3f}".format(eva["accuracy"]))
        logging.info("Precision & Recall:\n" + str(eva["classification_report"]))
        logging.info("Confision Matrix:\n" + str(eva["confusion_matrix"]))

        multi_model_metrics = pipeline.get_operator("trainer").metrics
        logging.info("multi-model metrics: \n" + "\n".join(
            list(map(lambda t: str(t[0]) + ": " + str(t[1]), list(multi_model_metrics.items())))))
        self.assertGreater(eva["accuracy"], 0.75, "accuracy is too low")

        predict = pipeline.evaluate(to_be_predicted)
        eva = ClassificationEvaluator().fit(predict)

        logging.info("\nTest Metrics:")
        logging.info("Accuracy: {:.3f}".format(eva["accuracy"]))
        logging.info("Precision & Recall:\n" + str(eva["classification_report"]))
        logging.info("Confision Matrix:\n" + str(eva["confusion_matrix"]))

    def test_linear_regression(self):
        logging.info("\n\nCASE: TEST LINEAR REGRESSION\n")
        lr_arr = {
            "sgd_lr": LinearRegression(method="sgd", eta=0.01, decay_power=0.5, regularization=30.0, max_epochs=1000,
                                       minibatch_size=100),
            "lr": LinearRegression(method="analytic", regularization=0)
        }

        pipeline = Pipeline(
            {
                "trainer": MultiModelTrainer(lr_arr, train_fraction=.7, evaluator=RegressionEvaluator(),
                                             metric="opposite_mse")
            }
        )

        pipeline.fit(self.regression_data)

        eva = pipeline.get_operator("trainer").get_evaluator()

        logging.info("R^2: {:.3f}".format(eva["R2"]))
        logging.info("Explained Variance: {:.3f}".format(eva["explained_variance"]))
        self.assertLess(eva["mse"], .6, "mse is too high")

    def test_logistic_regression(self):
        logging.info("\n\nCASE: TEST LOGISTIC REGRESSION\n")
        pipeline = Pipeline(
            {
                "preprocessor": RobustScaler(),
                "trainer": TrivialTrainer(LogisticRegression(), train_fraction=.7, evaluator=ClassificationEvaluator())
            }
        )

        pipeline.fit(self.pelvis)

        eva = pipeline.get_operator("trainer").get_evaluator()
        logging.info("Accuracy: {:.3f}\n".format(eva["accuracy"]))
        logging.info("Classification Report:\n" + str(eva["classification_report"]))
        self.assertGreater(eva["accuracy"], .6, "accuracy is too low")

    def test_dummy_preprocessor(self):
        logging.info("\n\nCASE: TEST DUMMY PREPROCESSOR\n")

        data = self.ghost

        # number of categories(output size)
        output_size = len(data.category)

        # split the data into train(and test) data set and data set to be predicted
        train_and_test, to_be_predicted = data.split(.7)

        dnn = DNN([10, output_size], ["relu", "identity"], softmax=True, max_epochs=20)
        pipeline = Pipeline(
            {
                "scaler": RobustScaler(),
                "dummy": Dummy(),
                "trainer": TrivialTrainer(dnn, train_fraction=.7, evaluator=ClassificationEvaluator())
            }
        )

        pipeline.fit(train_and_test)

        predict = pipeline.evaluate(to_be_predicted)
        eva = ClassificationEvaluator().fit(predict)

        logging.info("\nTest Metrics:")
        logging.info("Accuracy: {:.3f}".format(eva["accuracy"]))
        logging.info("Precision & Recall:\n" + str(eva["classification_report"]))
        logging.info("Confision Matrix:\n" + str(eva["confusion_matrix"]))


if __name__ == "__main__":
    unittest.main()
