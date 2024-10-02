from navigate.tools.decorators import FeatureList
from navigate.model.features.feature_related_functions import (
    VastAnnotator,
    TestFeature
)


@FeatureList
def vast_annotator():
    return [
        {"name": VastAnnotator},
    ]

@FeatureList
def test_feature():
    return [{"name": TestFeature}]