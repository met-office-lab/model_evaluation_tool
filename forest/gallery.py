"""Gallery design pattern"""
from collections import defaultdict
from functools import partial
import forest.state
from forest.reusable_pool import ReusablePool
from forest.scaling_group import ScalingGroup


class Gallery:
    """View orchestration layer"""
    def __init__(self, scaling_groups):
        self.scaling_groups = scaling_groups

    @classmethod
    def map_view(cls, datasets, factory_class):
        """MapView orchestration"""
        groups = {}
        for label, dataset in datasets.items():
            if hasattr(dataset, "map_view"):
                factory = factory_class(dataset)
                groups[label] = ScalingGroup(ReusablePool(factory))
        return cls(groups)

    @classmethod
    def profile_view(cls, datasets, figure):
        return cls._view(datasets, figure, "profile_view")

    @classmethod
    def series_view(cls, datasets, figure):
        return cls._view(datasets, figure, "series_view")

    @classmethod
    def _view(cls, datasets, figure, method_name):
        groups = {}
        for label, dataset in datasets.items():
            if not hasattr(dataset, method_name):
                continue
            factory = partial(getattr(dataset, method_name), figure)
            groups[label] = ScalingGroup(ReusablePool(factory))
        return cls(groups)

    def connect(self, store):
        store.add_subscriber(self.render)

    def render(self, state):
        if isinstance(state, dict):
            state = forest.state.State.from_dict(state)

        # Group layers by dataset
        layers = defaultdict(list)
        for uid, settings in sorted(state.layers.index.items()):
            if "dataset" in settings:
                key = settings["dataset"]
                layers[key].append(uid)

        # Apply layer settings to views
        for key, scaling_group in self.scaling_groups.items():
            uids = layers[key]
            scaling_group.scale_to(len(uids))
            for view, uid in zip(scaling_group.instances, uids):
                view.render_id(state, uid)
