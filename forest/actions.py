"""Collection of actions"""
from forest.db.control import (
    set_valid_time
)
from forest.colors import (
    set_palette_name,
    set_user_high
)
from forest.layers import (
    save_layer
)


NO_ACTION = "NO_ACTION"


def no_action():
    return {"kind": NO_ACTION}


SET_ENCODED_TIMES = "FOREST_ACTION_SET_ENCODED_TIMES"


def set_encoded_times(encoded_times):
    return {"kind": SET_ENCODED_TIMES, "payload": encoded_times}
