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
            )
