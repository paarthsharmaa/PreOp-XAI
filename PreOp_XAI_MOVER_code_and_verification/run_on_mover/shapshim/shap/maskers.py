import numpy as np


class Independent:
    def __init__(self, data, max_samples=100):
        self.data = np.asarray(data, dtype=float)
        if len(self.data) > max_samples:
            raise ValueError("Background larger than max_samples is not used in this study.")
