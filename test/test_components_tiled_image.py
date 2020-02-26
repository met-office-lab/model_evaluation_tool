import pytest
import bokeh.plotting
import unittest.mock
import numpy as np
import datetime as dt
from forest.components import TiledImage, tiled_image
from forest.components.tiled_image import Quadtree


def test_add_figure():
    # Fake Loader API
    loader = unittest.mock.Mock()
    loader.longitudes = np.linspace(0, 1, 10)
    loader.latitudes = np.linspace(0, 1, 10)
    loader.values.return_value = np.zeros((10, 10))
    loader.locator.find.return_value = "", 0

    color_mapper = None
    state = {"valid_time": dt.datetime(2020, 1, 1)}
    figure = bokeh.plotting.figure()
    view = TiledImage(loader, color_mapper)
    view.add_figure(figure)
    view.render(state)


@pytest.mark.parametrize("map_size,view_size,expect", [
    (1, 1, 2),
    (2, 1, 3),
    (4, 2, 3),
    (2**8, 1, 10),
])
def test_level(map_size,view_size, expect):
    assert tiled_image.level(map_size, view_size) == expect


@pytest.mark.parametrize("label,tile_0,tile_1,expect", [
    ("indentical", ((0, 2), (0, 2)), ((0, 2), (0, 2)), True),
    ("right touch", ((0, 2), (0, 2)), ((2, 4), (0, 2)), False),
    ("right", ((0, 2), (0, 2)), ((3, 5), (0, 2)), False),
    ("left touch", ((0, 2), (0, 2)), ((-2, 0), (0, 2)), False),
    ("left", ((0, 2), (0, 2)), ((-3, -1), (0, 2)), False),
    ("up touch", ((0, 2), (0, 2)), ((0, 2), (2, 4)), False),
    ("up", ((0, 2), (0, 2)), ((0, 2), (3, 5)), False),
    ("down touch", ((0, 2), (0, 2)), ((0, 2), (-2, 0)), False),
    ("down", ((0, 2), (0, 2)), ((0, 2), (-3, -1)), False),
])
def test_overlap(label, tile_0, tile_1, expect):
    assert Quadtree.overlap(tile_0, tile_1) == expect


@pytest.mark.parametrize("tiles,level,expect", [
    ([], 0, []),
    ([((0, 1), (0, 1))], 0, [((0, 256), (0, 256))]),
    ([((0, 1), (0, 1))], 1, [((0, 128), (0, 128))]),
    ([((0, 1), (0, 1))], 2, [((0, 64), (0, 64))]),
    ([((2, 3), (2, 3))], 8, [((2, 3), (2, 3))]),
])
def test_search(tiles, level, expect):
    initial = ((0, 256), (0, 256))
    checker = Quadtree.checker(tiles)
    assert list(Quadtree(initial).search(checker, level)) == expect


@pytest.mark.parametrize("tiles,tile,expect", [
    ([], ((0, 1), (0, 1)), False),
    ([((0, 1), (0, 1))], ((0, 1), (0, 1)), True),
])
def test_checker(tiles, tile, expect):
    assert Quadtree.checker(tiles)(tile) == expect


def test_quadtree():
    extent = ((0, 2), (0, 2))
    result = list(Quadtree.split(extent))
    expect = [
        ((0, 1), (0, 1)),
        ((1, 2), (0, 1)),
        ((1, 2), (1, 2)),
        ((0, 1), (1, 2)),
    ]
    assert expect == result


def test_builtin_all():
    assert all([]) == True
