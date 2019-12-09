import pytest
import unittest
import unittest.mock
import datetime as dt
import numpy as np
from forest import db, redux, rx


def test_reducer_immutable_state():
    state = {"pressure": 1000}
    next_state = db.reducer(state, db.set_value("pressure", 950))
    assert state["pressure"] == 1000
    assert next_state["pressure"] == 950


def test_convert_datetime64_array_to_strings():
    times = np.array(
            [dt.datetime(2019, 1, 1), dt.datetime(2019, 1, 2)],
            dtype="datetime64[s]")
    result = db.stamps(times)
    expect = ["2019-01-01 00:00:00", "2019-01-02 00:00:00"]
    assert expect == result


def test_type_system_middleware():
    times = np.array(
            [dt.datetime(2019, 1, 1), dt.datetime(2019, 1, 2)],
            dtype="datetime64[s]")
    converter = db.Converter({"valid_times": db.stamps})
    store = redux.Store(db.reducer, middlewares=[converter])
    store.dispatch(db.set_value("valid_times", times))
    result = store.state
    expect = {
        "valid_times": ["2019-01-01 00:00:00", "2019-01-02 00:00:00"]
    }
    assert expect == result


@pytest.fixture()
def database():
    obj = db.Database.connect(":memory:")
    yield obj
    obj.close()


def test_variables(database):
    database.insert_file_name("file.nc", "2019-01-01 00:00:00")
    database.insert_time("file.nc", "variable", "2019-01-01 12:00:00", 0)
    assert database.variables() == ["variable"]


def test_pressures(database):
    database.insert_file_name("file.nc", "2019-01-01 00:00:00")
    database.insert_pressure("file.nc", "air_temperature", 1000, 0)
    database.insert_pressure("file.nc", "relative_humidity", 750, 0)
    assert database.pressures(variable="relative_humidity") == [750]


def test_valid_times(database):
    database.insert_file_name("file.nc", "2019-01-01 00:00:00")
    database.insert_time("file.nc", "air_temperature", "2019-01-01 12:00:00", 0)
    database.insert_time("file.nc", "relative_humidity", "2019-01-01 13:00:00", 0)
    assert database.valid_times(variable="relative_humidity") == ["2019-01-01 13:00:00"]


def test_initial_times(database):
    database.insert_file_name("a.nc", "2019-01-01 00:00:00")
    database.insert_file_name("b.nc", "2019-01-02 00:00:00")
    assert database.initial_times(pattern="b.nc") == ["2019-01-02 00:00:00"]


def test_navigator(database):
    mapping = {"Label": "*a.nc"}

    # Database (in-memory) to simulate navigation
    file_name = "a.nc"
    database.insert_file_name(file_name, "2019-01-01 00:00:00")
    variables = {
            "air_temperature": {
                "time": ["2019-01-01 03:00:00", "2019-01-01 06:00:00"],
                "pressure": [1000, 950]},
            "relative_humidity": {
                "time": ["2019-01-01 03:15:00"],
                "pressure": [500]},
    }
    for variable, dims in variables.items():
        for time in dims["time"]:
            database.insert_time(file_name, variable, time, 0)
        for pressure in dims["pressure"]:
            database.insert_pressure(file_name, variable, pressure, 0)

    file_name = "b.nc"
    database.insert_file_name(file_name, "2019-01-01 00:00:00")
    database.insert_time(file_name, "mslp", "2019-01-02 12:00:00", 0)

    navigator = db.Navigator(database, mapping)

    # Navigation middleware API
    assert navigator.variables("Label") == ["air_temperature", "relative_humidity"]
    assert navigator.initial_times("Label") == ["2019-01-01 00:00:00"]
    assert navigator.valid_times(
            "Label", "air_temperature", "2019-01-01 00:00:00") == [
            "2019-01-01 03:00:00", "2019-01-01 06:00:00"]
    assert navigator.valid_times(
            "Label", "air_temperature", "2019-01-01 06:00:00") == []
    assert set(navigator.pressures(
        "Label", "air_temperature", "2019-01-01 00:00:00")) == set([1000., 950.])
    assert set(navigator.pressures(
        "Label", "air_temperature", "2019-01-01 06:00:00")) == set([])


def test_state_change_given_dropdown_message(database):
    navigator = db.Navigator(database, {})
    store = redux.Store(db.reducer, middlewares=[db.Middleware(navigator)])
    store.dispatch(db.set_value("pressure", "1000"))
    assert store.state["pressure"] == 1000.


def test_set_initial_time(database):
    # Create in-memory database
    variable = "variable"
    initial_time = dt.datetime(2019, 1, 1)
    valid_time = dt.datetime(2019, 1, 1, 3)
    database.insert_file_name("file.nc", initial_time)
    database.insert_time("file.nc", variable, valid_time, 0)

    # Create Store using middleware and navigator
    navigator = db.Navigator(database, {"Label": "file.nc"})
    middleware = db.Middleware(navigator)
    initial_state={
        "label": "Label",
        "variable": variable}
    store = redux.Store(
        db.reducer,
        initial_state=initial_state,
        middlewares=[middleware])
    action = db.set_value("initial_time", "2019-01-01 00:00:00")
    store.dispatch(action)

    assert store.state["label"] == "Label"
    assert store.state["variable"] == variable
    assert store.state["initial_time"] == str(initial_time)
    assert store.state["valid_times"] == [str(valid_time)]


def test_set_label(database):
    file_name = "file.nc"
    variable = "variable"
    initial_time = dt.datetime(2019, 1, 1)
    valid_time = dt.datetime(2019, 1, 1, 3)
    database.insert_file_name(file_name, initial_time)
    database.insert_time(file_name, variable, valid_time, 0)

    navigator = db.Navigator(database, {"Label": file_name})
    store = redux.Store(db.reducer, middlewares=[db.Middleware(navigator)])
    store.dispatch(db.set_value("label", "Label"))

    assert store.state["label"] == "Label"
    assert store.state["variables"] == [variable]
    assert store.state["initial_times"] == [str(initial_time)]


class TestMiddleware(unittest.TestCase):
    def setUp(self):
        self.database = db.Database.connect(":memory:")

    def tearDown(self):
        self.database.close()

    def test_on_variable_emits_state(self):
        value = "token"
        listener = unittest.mock.Mock()
        view = db.ControlView()
        view.subscribe(listener)
        view.on_change("variable")(None, None, value)
        listener.assert_called_once_with(db.set_value("variable", value))

    def test_next_pressure_given_pressures_returns_first_element(self):
        pressure = 950
        store = redux.Store(
            db.reducer,
            initial_state={"pressures": [pressure]},
            middlewares=[
                db.next_previous,
                db.Middleware(self.database)])
        view = db.ControlView()
        view.subscribe(store.dispatch)
        view.on_next('pressure', 'pressures')()
        result = store.state
        expect = {
            "pressure": pressure,
            "pressures": [pressure]
        }
        self.assertEqual(expect, result)

    def test_next_pressure_given_pressures_none(self):
        store = redux.Store(
            db.reducer,
            middlewares=[
                db.InverseCoordinate("pressure"),
                db.next_previous,
                db.Middleware(self.database)
            ])
        view = db.ControlView()
        view.subscribe(store.dispatch)
        view.on_next('pressure', 'pressures')()
        result = store.state
        expect = {}
        self.assertEqual(expect, result)

    def test_next_pressure_given_current_pressure(self):
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
                db.next_previous,
                db.Middleware(self.database)
            ])
        view = db.ControlView()
        view.subscribe(store.dispatch)
        view.on_next('pressure', 'pressures')()
        result = store.state["pressure"]
        expect = 800
        self.assertEqual(expect, result)


class TestControlView(unittest.TestCase):
    def setUp(self):
        self.view = db.ControlView()

    def test_on_click_emits_action(self):
        listener = unittest.mock.Mock()
        self.view.subscribe(listener)
        self.view.on_next("pressure", "pressures")()
        expect = db.next_value("pressure", "pressures")
        listener.assert_called_once_with(expect)

    def test_render_given_no_variables_disables_dropdown(self):
        self.view.render({"variables": []})
        result = self.view.dropdowns["variable"].disabled
        expect = True
        self.assertEqual(expect, result)

    def test_render_given_pressure(self):
        state = {
            "pressures": [1000],
            "pressure": 1000
        }
        self.view.render(state)
        result = self.view.dropdowns["pressure"].label
        expect = "1000hPa"
        self.assertEqual(expect, result)

    def test_render_sets_pressure_levels(self):
        pressures = [1000, 950, 850]
        self.view.render({"pressures": pressures})
        result = self.view.dropdowns["pressure"].menu
        expect = ["1000hPa", "950hPa", "850hPa"]
        self.assert_label_equal(expect, result)

    def test_render_given_initial_time_populates_valid_time_menu(self):
        state = {"valid_times": [dt.datetime(2019, 1, 1, 3)]}
        self.view.render(state)
        result = self.view.dropdowns["valid_time"].menu
        expect = ["2019-01-01 03:00:00"]
        self.assert_label_equal(expect, result)

    def test_render_state_configures_variable_menu(self):
        self.view.render({"variables": ["mslp"]})
        result = self.view.dropdowns["variable"].menu
        expect = ["mslp"]
        self.assert_label_equal(expect, result)
        self.assert_value_equal(expect, result)

    def test_render_state_configures_initial_time_menu(self):
        initial_times = ["2019-01-01 12:00:00", "2019-01-01 00:00:00"]
        state = {"initial_times": initial_times}
        self.view.render(state)
        result = self.view.dropdowns["initial_time"].menu
        expect = initial_times
        self.assert_label_equal(expect, result)

    def assert_label_equal(self, expect, result):
        result = [l for l, _ in result]
        self.assertEqual(expect, result)

    def assert_value_equal(self, expect, result):
        result = [v for _, v in result]
        self.assertEqual(expect, result)

    def test_render_initial_times_disables_buttons(self):
        key = "initial_time"
        self.view.render({})
        self.assertEqual(self.view.dropdowns[key].disabled, True)
        self.assertEqual(self.view.buttons[key]["next"].disabled, True)
        self.assertEqual(self.view.buttons[key]["previous"].disabled, True)

    def test_hpa_given_small_pressures(self):
        result = db.ControlView.hpa(0.001)
        expect = "0.001hPa"
        self.assertEqual(expect, result)

    def test_render_variables_given_null_state_disables_dropdown(self):
        self.view.render({})
        result = self.view.dropdowns["variable"].disabled
        expect = True
        self.assertEqual(expect, result)

    def test_render_initial_times_enables_buttons(self):
        key = "initial_time"
        self.view.render({"initial_times": ["2019-01-01 00:00:00"]})
        self.assertEqual(self.view.dropdowns[key].disabled, False)
        self.assertEqual(self.view.buttons[key]["next"].disabled, False)
        self.assertEqual(self.view.buttons[key]["previous"].disabled, False)

    def test_render_valid_times_given_null_state_disables_buttons(self):
        self.check_disabled("valid_time", {}, True)

    def test_render_valid_times_given_empty_list_disables_buttons(self):
        self.check_disabled("valid_time", {"valid_times": []}, True)

    def test_render_valid_times_given_values_enables_buttons(self):
        state = {"valid_times": ["2019-01-01 00:00:00"]}
        self.check_disabled("valid_time", state, False)

    def test_render_pressures_given_null_state_disables_buttons(self):
        self.check_disabled("pressure", {}, True)

    def test_render_pressures_given_empty_list_disables_buttons(self):
        self.check_disabled("pressure", {"pressures": []}, True)

    def test_render_pressures_given_values_enables_buttons(self):
        self.check_disabled("pressure", {"pressures": [1000.00000001]}, False)

    def check_disabled(self, key, state, expect):
        self.view.render(state)
        self.assertEqual(self.view.dropdowns[key].disabled, expect)
        self.assertEqual(self.view.buttons[key]["next"].disabled, expect)
        self.assertEqual(self.view.buttons[key]["previous"].disabled, expect)


class TestNextPrevious(unittest.TestCase):
    def setUp(self):
        self.initial_times = [
            "2019-01-02 00:00:00",
            "2019-01-01 00:00:00",
            "2019-01-04 00:00:00",
            "2019-01-03 00:00:00",
        ]

    def test_middleware_converts_next_value_to_set_value(self):
        log = db.Log()
        state = {
            "k": 2,
            "ks": [1, 2, 3]
        }
        store = redux.Store(
            db.reducer,
            initial_state=state,
            middlewares=[
                db.next_previous,
                log])
        store.dispatch(db.next_value("k", "ks"))
        result = store.state
        expect = {
            "k": 3,
            "ks": [1, 2, 3]
        }
        self.assertEqual(expect, result)
        self.assertEqual(log.actions, [db.set_value("k", 3)])

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

    def test_next_item_given_last_item_returns_first_item(self):
        result = db.control.next_item([0, 1, 2], 2)
        expect = 0
        self.assertEqual(expect, result)

    def test_previous_item_given_first_item_returns_last_item(self):
        result = db.control.previous_item([0, 1, 2], 0)
        expect = 2
        self.assertEqual(expect, result)


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


class TestStateStream(unittest.TestCase):
    def test_support_old_style_state(self):
        """Not all components are ready to accept dict() states"""
        listener = unittest.mock.Mock()
        store = redux.Store(db.reducer)
        old_states = (rx.Stream()
                  .listen_to(store)
                  .map(lambda x: db.State(**x)))
        old_states.subscribe(listener)
        store.dispatch(db.set_value("pressure", 1000))
        expect = db.State(pressure=1000)
        listener.assert_called_once_with(expect)
