import pytest
import unittest.mock
from forest import dataset, db, redux


@pytest.mark.parametrize("state,action,expect", [
    ({}, dataset.set_label("Label"), {"label": "Label"}),
    ({}, dataset.set_labels(["A", "B"]), {"labels": ["A", "B"]})
])
def test_reducer(state, action, expect):
    result = dataset.reducer(state, action)
    assert result == expect


def test_middleware():
    # NOTE: This middleware is not needed if pattern is no longer
    #       used as the primary key
    store = redux.Store(
            redux.combine_reducers(
                db.reducer,
                dataset.reducer),
            initial_state={
                "patterns": [("label", "*.nc")]
            },
            middlewares=[dataset.middleware])
    store.dispatch(dataset.set_label("label"))
    assert store.state == {
            "label": "label",
            "pattern": "*.nc",
            "patterns": [("label", "*.nc")]}


def test_dataset_ui_emits_set_label():
    listener = unittest.mock.Mock()
    ui = dataset.DatasetUI()
    ui.subscribe(listener)
    ui.callback(None, None, "Label")
    listener.assert_called_once_with(dataset.set_label("Label"))


@pytest.mark.parametrize("state,label", [
    ({}, "Dataset"),
    ({"label": "Label"}, "Label"),
])
def test_render_label(state, label):
    ui = dataset.DatasetUI()
    ui.render(state)
    assert ui.dropdown.label == label


@pytest.mark.parametrize("state,menu", [
    ({}, []),
    ({"labels": ["A", "B"]}, [("A", "A"), ("B", "B")]),
])
def test_render_menu(state, menu):
    ui = dataset.DatasetUI()
    ui.render(state)
    assert ui.dropdown.menu == menu
