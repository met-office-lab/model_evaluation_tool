"""Reducer"""
import copy
import forest.state
from forest import (
    actions,
    redux,
    db,
    layers,
    screen,
    tools,
    colors,
    presets,
    dimension)
from forest.components import (
    html_ready,
    tiles)


def state_reducer(state, action):
    """Set State"""
    if isinstance(action, dict):
        try:
            action = actions.Action.from_dict(action)
        except TypeError:
            # TODO: Support Action throughout codebase
            return state
    # Reduce state
    state = copy.deepcopy(state)
    if action.kind == actions.SET_STATE:
        state = copy.deepcopy(action.payload)
    elif action.kind == actions.UPDATE_STATE:
        state.update(action.payload)
    return state


def borders_reducer(state, action):
    """Configure borders, coastlines and lakes"""
    if isinstance(action, dict):
        try:
            action = actions.Action.from_dict(action)
        except TypeError:
            # TODO: Support Action throughout codebase
            return state
    # Reduce state.borders
    if isinstance(state, dict):
        state = forest.state.State.from_dict(state)
    if action.kind == actions.SET_BORDERS_VISIBLE:
        state.borders.visible = action.payload
    elif action.kind == actions.SET_BORDERS_LINE_COLOR:
        state.borders.line_color = action.payload
    return state.to_dict()


def startup_reducer(state, action):
    if isinstance(action, dict):
        try:
            action = actions.Action.from_dict(action)
        except TypeError:
            # TODO: Support Action throughout codebase
            return state
    if isinstance(state, dict):
        state = forest.state.State.from_dict(state)
    if action.kind == actions.STARTUP_COMPLETE:
        state.startup_complete = True
    return state.to_dict()


reducer = redux.combine_reducers(
            db.reducer,
            layers.reducer,
            screen.reducer,
            tools.reducer,
            colors.reducer,
            colors.limits_reducer,
            presets.reducer,
            tiles.reducer,
            dimension.reducer,
            html_ready.reducer,
            state_reducer,
            borders_reducer,
            startup_reducer)
