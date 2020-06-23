"""Reducer"""
from forest import (
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
    animate,
    tiles)


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
            animate.reducer)
