import pytest
import unittest
import unittest.mock
import cftime
import datetime as dt
import numpy as np
import forest.db.control
from forest import db, redux, rx


def test_reducer_immutable_state():
    """Ensure copy.deepcopy is used to create a new state"""
    previous_state = {"key": ["value"]}
    next_state = db.reducer(previous_state, {"kind": "ANY"})
    previous_state["key"].append("extra")
    assert next_state["key"] == ["value"]


class TestDatabaseMiddleware(unittest.TestCase):
    def setUp(self):
        self.database = db.Database.connect(":memory:")
        self.controls = db.Controls(self.database)
        self.store = redux.Store(db.reducer, middlewares=[self.controls])

    def tearDown(self):
        self.database.close()

    def test_state_change_given_dropdown_message(self):
        action = db.set_value("pressure", "1000")
        self.store.dispatch(action)
        result = self.store.state
        expect = {"pressure": 1000.}
        self.assertEqual(expect, result)

    def test_set_initial_time(self):
        initial = dt.datetime(2019, 1, 1)
        valid = dt.datetime(2019, 1, 1, 3)
        self.database.insert_file_name("file.nc", initial)
        self.database.insert_time("file.nc", "variable", valid, 0)
        action = db.set_value("initial_time", "2019-01-01 00:00:00")
        initial_state={
            "pattern": "file.nc",
            "variable": "variable"}
        store = redux.Store(
            db.reducer,
            initial_state=initial_state,
            middlewares=[self.controls])
        store.dispatch(action)
        result = store.state
        expect = {
            "pattern": "file.nc",
            "variable": "variable",
            "initial_time": str(initial),
            "valid_times": [str(valid)]
        }
        self.assertEqual(expect, result)

    def test_set_pattern(self):
        initial = dt.datetime(2019, 1, 1)
        valid = dt.datetime(2019, 1, 1, 3)
        self.database.insert_file_name("file.nc", initial)
        self.database.insert_time("file.nc", "variable", valid, 0)
        action = db.set_value("pattern", "file.nc")
        self.store.dispatch(action)
        result = self.store.state
        expect = {
            "pattern": "file.nc",
            "variables": ["variable"],
            "initial_times": [str(initial)]
        }
        self.assertEqual(expect, result)


def test_dimension_view_on_select():
    listener = unittest.mock.Mock()
    view = forest.db.control.DimensionView("item", "items")
    view.add_subscriber(listener)
    view.views["select"].on_select(None, None, "token")
    listener.assert_called_once_with(db.set_value("item", "token"))


def test_dimension_view_on_next():
    listener = unittest.mock.Mock()
    view = forest.db.control.DimensionView("item", "items")
    view.add_subscriber(listener)
    view.on_next()
    listener.assert_called_once_with(db.next_value("item", "items"))


def test_dimension_view_on_previous():
    listener = unittest.mock.Mock()
    view = forest.db.control.DimensionView("item", "items")
    view.add_subscriber(listener)
    view.on_previous()
    listener.assert_called_once_with(db.previous_value("item", "items"))


@pytest.fixture
def database():
    in_memory_database = db.Database.connect(":memory:")
    yield in_memory_database
    in_memory_database.close()


def test_middleware_next_pressure_given_pressures_returns_first_element():
    pressure = 950
    store = redux.Store(
        db.reducer,
        initial_state={"pressures": [pressure]},
        middlewares=[db.next_previous])
    action = forest.db.control.next_value("pressure", "pressures")
    store.dispatch(action)
    result = store.state
    expect = {
        "pressure": pressure,
        "pressures": [pressure]
    }
    assert expect == result


def test_middleware_next_pressure_given_pressures_none():
    store = redux.Store(
        db.reducer,
        middlewares=[
            db.InverseCoordinate("pressure"),
            db.next_previous,
        ])
    action = forest.db.control.next_value("pressure", "pressures")
    store.dispatch(action)
    assert store.state == {}


def test_middleware_next_pressure_given_current_pressure():
    pressure = 950
    pressures = [1000, 950, 800]
    store = redux.Store(
        db.reducer,
        initial_state={
            "pressure": pressure,
            "pressures": pressures
        },
        middlewares=[
            db.InverseCoordinate("pressure"),
            db.next_previous
        ])
    action = forest.db.control.next_value("pressure", "pressures")
    store.dispatch(action)
    assert store.state["pressure"] == 800


def test_dimension_view_on_next_action():
    listener = unittest.mock.Mock()
    view = forest.db.control.DimensionView("pressure", "pressures")
    view.add_subscriber(listener)
    view.on_next()
    expect = db.next_value("pressure", "pressures")
    listener.assert_called_once_with(expect)


def test_dimension_view_render_given_pressure():
    state = {"pressure": 1000, "pressures": [1000]}
    view = forest.db.control.DimensionView(
            "pressure", "pressures",
            formatter=forest.db.control.format_hpa)
    view.render(state)
    assert view.views["select"].select.value == "1000hPa"


def test_dimension_view_render_sets_pressure_levels():
    pressures = [1000, 950, 850]
    state = {"pressures": pressures}
    view = forest.db.control.DimensionView(
            "pressure", "pressures",
            formatter=forest.db.control.format_hpa)
    view.render(state)
    assert view.views["select"].select.options[0] == forest.db.control.UNAVAILABLE
    assert view.views["select"].select.options[1:] == ["1000hPa", "950hPa", "850hPa"]


def test_dimension_view_render_valid_times():
    state = {"valid_times": [dt.datetime(2019, 1, 1, 3)]}
    view = forest.db.control.DimensionView("valid_time", "valid_times")
    view.render(state)
    assert view.views["select"].select.options[0] == forest.db.control.UNAVAILABLE
    assert view.views["select"].select.options[1:] == ["2019-01-01 03:00:00"]


def test_dimension_view_render_variables():
    state = {"variables": ["mslp"]}
    view = forest.db.control.DimensionView("variable", "variables")
    view.render(state)
    assert view.views["select"].select.options[0] == forest.db.control.UNAVAILABLE
    assert view.views["select"].select.options[1:] == ["mslp"]


def test_dimension_view_render_initial_times():
    initial_times = ["2019-01-01 12:00:00", "2019-01-01 00:00:00"]
    state = {"initial_times": initial_times}
    view = forest.db.control.DimensionView("initial_time", "initial_times")
    view.render(state)
    assert view.views["select"].select.options[0] == forest.db.control.UNAVAILABLE
    assert view.views["select"].select.options[1:] == initial_times


def test_hpa_given_small_pressures():
    assert db.ControlView.hpa(0.001) == "0.001hPa"


@pytest.mark.parametrize("state,expect", [
    ({}, True),
    ({"items": []}, True),
    ({"items": ["value"]}, False),
])
def test_dimension_view_disabled(state, expect):
    view = forest.db.control.DimensionView("item", "items")
    view.render(state)
    assert view.views["select"].select.disabled == expect
    assert view.buttons["next"].disabled == expect
    assert view.buttons["previous"].disabled == expect


@pytest.mark.parametrize("state,expect", [
    ({}, True),
    ({"items": []}, True),
    ({"items": ["value"]}, False),
])
def test_dimension_no_buttons_view_disabled(state, expect):
    view = forest.db.control.DimensionView("item", "items", next_previous=False)
    view.render(state)
    assert view.views["select"].select.disabled == expect


class TestNextPrevious(unittest.TestCase):
    def setUp(self):
        self.initial_times = [
            "2019-01-02 00:00:00",
            "2019-01-01 00:00:00",
            "2019-01-04 00:00:00",
            "2019-01-03 00:00:00",
        ]

    def test_middleware_converts_next_value_to_set_value(self):
        store = redux.Store(
            db.reducer,
            initial_state={"k": 2, "ks": [1, 2, 3]})
        action = db.next_value("k", "ks")
        result = list(db.next_previous(store, action))
        self.assertEqual(result, [db.set_value("k", 3)])

    def test_next_value_action_creator(self):
        result = db.next_value("initial_time", "initial_times")
        expect = {
            "kind": "NEXT_VALUE",
            "payload": {
                "item_key": "initial_time",
                "items_key": "initial_times"
            }
        }
        self.assertEqual(expect, result)

    def test_previous_value_action_creator(self):
        result = db.previous_value("initial_time", "initial_times")
        expect = {
            "kind": "PREVIOUS_VALUE",
            "payload": {
                "item_key": "initial_time",
                "items_key": "initial_times"
            }
        }
        self.assertEqual(expect, result)

    def test_set_value_action_creator(self):
        result = db.set_value("K", "V")
        expect = {
            "kind": "SET_VALUE",
            "payload": dict(key="K", value="V")
        }
        self.assertEqual(expect, result)

    def test_next_given_none_selects_latest_time(self):
        action = db.next_value("initial_time", "initial_times")
        state = dict(initial_times=self.initial_times)
        store = redux.Store(
            db.reducer,
            initial_state=state,
            middlewares=[db.next_previous])
        store.dispatch(action)
        result = store.state
        expect = dict(
            initial_time="2019-01-04 00:00:00",
            initial_times=self.initial_times)
        self.assertEqual(expect, result)

    def test_reducer_given_set_value_action_adds_key_value(self):
        action = db.set_value("name", "value")
        state = {"previous": "constant"}
        result = db.reducer(state, action)
        expect = {
            "previous": "constant",
            "name": "value"
        }
        self.assertEqual(expect, result)

    def test_reducer_next_given_time_moves_forward_in_time(self):
        initial_times = [
            "2019-01-01 00:00:00",
            "2019-01-01 02:00:00",
            "2019-01-01 01:00:00"
        ]
        action = db.next_value("initial_time", "initial_times")
        state = {
            "initial_time": "2019-01-01 00:00:00",
            "initial_times": initial_times
        }
        store = redux.Store(
            db.reducer,
            initial_state=state,
            middlewares=[db.next_previous])
        store.dispatch(action)
        result = store.state
        expect = {
            "initial_time": "2019-01-01 01:00:00",
            "initial_times": initial_times
        }
        self.assertEqual(expect, result)

    def test_previous_given_none_selects_earliest_time(self):
        action = db.previous_value("initial_time", "initial_times")
        state = {"initial_times": self.initial_times}
        store = redux.Store(
            db.reducer,
            initial_state=state,
            middlewares=[db.next_previous])
        store.dispatch(action)
        result = store.state
        expect = {
            "initial_time": "2019-01-01 00:00:00",
            "initial_times": self.initial_times
        }
        self.assertEqual(expect, result)

    def test_previous_item_given_first_item_returns_last_item(self):
        result = db.control.previous_item([0, 1, 2], 0)
        expect = 2
        self.assertEqual(expect, result)


@pytest.mark.parametrize("items,item,expect", [
    ([0, 1, 2], 2, 0),
    ([0, 1, 2], 2.000001, 0),
])
def test_next_item(items, item, expect):
    assert db.control.next_item(items, item) == expect


@pytest.mark.parametrize("items,item,expect", [
    ([3, 4, 5], 5, 2),
    ([3, 4, 5], 5.000001, 2),
    ([dt.datetime(2020, 1, 1)], dt.datetime(2020, 1, 1), 0)
])
def test_index(items, item, expect):
    assert db.control._index(items, item) == expect


@pytest.mark.parametrize("items,item,error", [
    ([], 0, db.control.IndexNotFound),
    ([1], 0, db.control.IndexNotFound),
])
def test_index_raises_value_error(items, item, error):
    with pytest.raises(error):
        db.control._index(items, item)



class TestPressureMiddleware(unittest.TestCase):
    def test_pressure_middleware_reverses_pressure_coordinate(self):
        pressures = [1000, 850, 500]
        state = {
            "pressure": 850,
            "pressures": pressures
        }
        store = redux.Store(
            db.reducer,
            initial_state=state,
            middlewares=[
                db.InverseCoordinate("pressure"),
                db.next_previous])
        action = db.next_value("pressure", "pressures")
        store.dispatch(action)
        result = store.state
        expect = {
            "pressure": 500,
            "pressures": pressures
        }
        self.assertEqual(expect, result)


def test_controls_middleware(database):
    middleware = forest.db.Controls(database)
    store = forest.redux.Store(forest.db.control.reducer)
    action = {"kind": "ANY"}
    assert list(middleware(store, action)) == [action]


def test_controls_middleware_given_set_variable():
    """Should set pressure level"""
    navigator = unittest.mock.Mock(spec=[
        "valid_times",
        "pressures"
    ])
    middleware = forest.db.Controls(navigator)
    # Configure Store.state
    store = forest.redux.Store(forest.db.control.reducer)
    for action in [
            forest.db.control.set_value("pattern", "*"),
            forest.db.control.set_value("initial_time", "2020-01-01 00:00:00"),
            forest.db.control.set_value("valid_time", "2020-01-01 00:00:00")]:
        store.dispatch(action)
    # Configure navigator
    valid_times = ["2020-01-01 00:00:00"]
    pressures = [950., 1000., 750.]
    navigator.valid_times.return_value = valid_times
    navigator.pressures.return_value = pressures
    action = forest.db.control.set_value("variable", "name")
    assert list(middleware(store, action)) == [
            action,
            forest.db.control.set_value("valid_times", valid_times),
            forest.db.control.set_value("pressures", list(reversed(pressures))),
            forest.db.control.set_value("pressure", 1000.),
    ]


def test_controls_middleware_given_set_variable_no_pressures():
    navigator = unittest.mock.Mock(spec=[
        "valid_times",
        "pressures"
    ])
    middleware = forest.db.Controls(navigator)
    # Configure Store.state
    store = forest.redux.Store(forest.db.control.reducer)
    for action in [
            forest.db.control.set_value("pattern", "*"),
            forest.db.control.set_value("initial_time", "2020-01-01 00:00:00"),
            forest.db.control.set_value("valid_time", "2020-01-01 00:00:00")]:
        store.dispatch(action)
    # Configure navigator
    valid_times = ["2020-01-01 00:00:00"]
    pressures = []
    navigator.valid_times.return_value = valid_times
    navigator.pressures.return_value = pressures
    action = forest.db.control.set_value("variable", "name")
    assert list(middleware(store, action)) == [
            action,
            forest.db.control.set_value("valid_times", valid_times),
            forest.db.control.set_value("pressures", []),
    ]


class TestStateStream(unittest.TestCase):
    def test_support_old_style_state(self):
        """Not all components are ready to accept dict() states"""
        listener = unittest.mock.Mock()
        store = redux.Store(db.reducer)
        old_states = (rx.Stream()
                  .listen_to(store)
                  .map(lambda x: db.State(**x)))
        old_states.add_subscriber(listener)
        store.dispatch(db.set_value("pressure", 1000))
        expect = db.State(pressure=1000)
        listener.assert_called_once_with(expect)
