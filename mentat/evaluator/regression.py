from .base import Evaluator
from ..exception import ParameterException

import numpy as np


class RegressionEvaluator(Evaluator):
    prediction = None

    def __init__(self):
        super().__init__()

    def fit(self, data):
        self.prediction = data
        return self

    def get_metric(self, metric):
        if metric == "opposite_mse":
            return self.opposite_mse()
        else:
            raise ParameterException("metric {:s} unsupported.".format(metric))

    def opposite_mse(self):
        return -np.mean(np.power(self.prediction.data["predict_value"] - self.prediction.response().ravel(), 2))