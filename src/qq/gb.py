from pathlib import Path

import numpy as np
import pandas as pd

from qq.constants import GB_FEATURES, GB_LANGUAGES, GB_MV_FEATURES, GB_PARAMS, LANGUOIDS

# TODO: Work in progress


class Grambank:
    def __init__(
        self,
        languoids_path: Path = LANGUOIDS,
        features_path: Path = GB_FEATURES,
        languages_path: Path = GB_LANGUAGES,
        parameters_path: Path = GB_PARAMS,
    ) -> None:
        self.languoids = pd.read_csv(languoids_path)
        self.features = self._pre_process_features(pd.read_csv(features_path))
        self.languages = pd.read_csv(languages_path)
        self.parameters = pd.read_csv(parameters_path)

        self.iso2glot = {
            row["iso639P3code"]: row["id"]
            # TODO: don't do this, make proper in final filtering method
            for _, row in self.languoids[self.languoids["id"].isin(self.features["Lang_ID"])].iterrows()
        }
        self.glot2iso = {v: k for k, v in self.iso2glot.items()}
        self.feature2name = {row["ID"]: row["Name"] for _, row in self.parameters.iterrows()}
        self.name2feature = {v: k for k, v in self.feature2name.items()}

    def get_features(self, glot_codes: set[str]):
        return self.features[self.features["Lang_ID"].isin(glot_codes)]

    def get_concepts(self, glotto_code: str):
        features = self.features[self.features["Lang_ID"] == glotto_code].iloc[0, 1:].tolist()
        # TODO: do this at the preprocessing stage and make sure only 1s and 0s are included here
        return np.array([{"1": 1, "0": 0}.get(f, np.nan) for f in features])

    @staticmethod
    def _pre_process_features(
        features: pd.DataFrame,
        multi_value_features: list[str] = GB_MV_FEATURES,  # TODO: make these multi value features data driven
    ):
        # TODO: figure out where to filter out the languages based on feature coverage
        # as I don't think we can use '?' as a concept.

        # Already preprocessed.
        if len(features[features.isin(GB_MV_FEATURES)]) == 0:
            return features

        # Binarize multivalue features
        # This method is taken from https://github.com/esther2000/typdiv-sampling
        for feat in multi_value_features:
            if feat not in features.columns:
                continue
            features[f"{feat}_1"] = (features[f"{feat}"] == "1").astype(int).astype(str)  # label 1
            features[f"{feat}_2"] = (features[f"{feat}"] == "2").astype(int).astype(str)  # label 2

            # label 3 (both)
            features.loc[features[feat] == "3", f"{feat}_1"] = "1"
            features.loc[features[feat] == "3", f"{feat}_2"] = "1"

            # label 0 (none)
            features.loc[features[feat] == "0", f"{feat}_1"] = "0"
            features.loc[features[feat] == "0", f"{feat}_2"] = "0"

            # if original value was '?', put this back
            features.loc[features[feat] == "?", f"{feat}_1"] = "?"
            features.loc[features[feat] == "?", f"{feat}_2"] = "?"

            # if original value was 'no_cov', put this back
            features.loc[features[feat] == "no_cov", f"{feat}_1"] = "no_cov"
            features.loc[features[feat] == "no_cov", f"{feat}_2"] = "no_cov"

        # remove original multi-value feature columns
        features = features.drop(columns=multi_value_features, errors="ignore")
        return features

    @staticmethod
    def _pre_process_languoids(languoids: pd.DataFrame):
        """Filter out macrolanguages (e.g. Central pacific linkage)"""
        # Filter out macro languages
        # Filter out
        return languoids[languoids["child_language_count"] > 0]["id"]
