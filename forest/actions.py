"""Collection of actions"""
from dataclasses import dataclass, field, asdict
from forest.colors import (
    set_palette_name,
    set_user_high
)
from forest.layers import (
    save_layer
)


@dataclass
class Action:
    kind: str
    payload: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


HTML_LOADED = "BOKEH_HTML_LOADED"
NO_ACTION = "NO_ACTION"
SET_BORDERS_VISIBLE = "SET_BORDERS_VISIBLE"
SET_BORDERS_LINE_COLOR = "SET_BORDERS_LINE_COLOR"
SET_STATE = "SET_STATE"
UPDATE_STATE = "UPDATE_STATE"
STARTUP_COMPLETE = "STARTUP_COMPLETE"


def startup_complete():
    return Action(STARTUP_COMPLETE)


def no_action():
    return {"kind": NO_ACTION}


def set_borders_visible(flag):
    return Action(SET_BORDERS_VISIBLE, flag)


def set_borders_line_color(color):
    return Action(SET_BORDERS_LINE_COLOR, color)


def set_state(state):
    return Action(SET_STATE, state)


def update_state(state):
    return Action(UPDATE_STATE, state)


def html_loaded():
    return Action(HTML_LOADED)


def set_valid_times(times):
    return Action("SET_VALUE", {"key": "valid_times", "value": times})


def set_valid_time(time):
    return Action("SET_VALUE", {"key": "valid_time", "value": time})
