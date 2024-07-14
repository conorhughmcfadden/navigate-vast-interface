from navigate.tools.decorators import FeatureList
from navigate.model.features.feature_related_functions import (
    VastAnnotator,
)


@FeatureList

def vast_annotator():
    return [
        {"name": VastAnnotator},
    ]
