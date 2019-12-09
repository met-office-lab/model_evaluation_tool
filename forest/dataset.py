"""User interface"""
import bokeh.models
import bokeh.layouts
from forest import redux
from forest.observe import Observable
from forest.db import set_value


SET_DATASET = "SET_DATASET"


def set_label(label):
    return {"kind": SET_DATASET, "payload": {"label": label}}


def set_labels(labels):
    return {"kind": SET_DATASET, "payload": {"labels": labels}}


def reducer(state, action):
    kind = action["kind"]
    if kind == SET_DATASET:
        state.update(action["payload"])
    return state


@redux.middleware
def middleware(store, next_dispatch, action):
    kind = action["kind"]
    if (kind == SET_DATASET) and ("label" in action["payload"]):
        # NOTE: Temporary fix to support components dependent on pattern
        if "patterns" in store.state:
            for label, pattern in store.state["patterns"]:
                if label == action["payload"]["label"]:
                    next_dispatch(set_value("pattern", pattern))
                    break
    next_dispatch(action)


class DatasetUI(Observable):
    """User interface to select dataset(s)"""
    def __init__(self):
        self.dropdown = bokeh.models.Dropdown(
                label="Dataset",
                width=350)
        self.dropdown.on_change("value", self.callback)
        self.layout = bokeh.layouts.column(self.dropdown)
        super().__init__()

    def callback(self, attr, old, new):
        self.notify(set_label(new))

    def render(self, state):
        """Configure dropdown menus"""
        assert isinstance(state, dict), "Only support dict"
        if "label" in state:
            self.dropdown.label = state["label"]
        if "labels" in state:
            self.dropdown.menu = [(str(l), str(l)) for l in state["labels"]]
