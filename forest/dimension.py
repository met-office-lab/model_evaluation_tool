"""Dimension information relating to datasets"""
import copy
from forest.actions import SET_ENCODED_TIMES


SET_VARIABLES = "DIMENSION_SET_VARIABLES"


def set_variables(label, values):
    """Action to set variables related to dataset"""
    return {"kind": SET_VARIABLES,
            "payload": {"label": label, "values": values}}


def reducer(state, action):
    """Encode dimension information into state"""
    state = copy.deepcopy(state)
    kind = action["kind"]
    if kind == SET_VARIABLES:
        node = state
        for key in ("dimension", action["payload"]["label"]):
            node[key] = node.get(key, {})
            node = node[key]
        node["variables"] = action["payload"]["values"]
    elif kind == SET_ENCODED_TIMES:
        # TODO: Find a better place in the state to store RL encoded times
        state["encoded"] = action["payload"]
    return state
