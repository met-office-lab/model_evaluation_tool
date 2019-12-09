import unittest
from forest import (
        db,
        images)


class TestInitialState(unittest.TestCase):
    def setUp(self):
        self.database = db.Database.connect(":memory:")

    def tearDown(self):
        self.database.close()

    def make_database(self):
        structure = [
            ("file_0.nc", "2019-01-01 00:00:00", [
                ("air_temperature", {
                    "time": ["2019-01-01 01:00:02"],
                    "pressure": [750]
                }),
                ("relative_humidity", {
                    "time": ["2019-01-01 01:30:00"],
                    "pressure": [850]
                })
            ]),
            ("file_1.nc", "2019-01-01 12:00:00", [
                ("air_temperature", {
                    "time": [
                        "2019-01-01 12:00:02",
                        "2019-01-01 13:00:02"
                    ],
                    "pressure": [1000, 950]
                })
            ])
        ]
        for path, initial_time, variables in structure:
            self.database.insert_file_name(path, initial_time)
            for variable, attrs in variables:
                self.database.insert_variable(path, variable)
                for i, t in enumerate(attrs["time"]):
                    self.database.insert_time(path, variable, t, i)
                for i, p in enumerate(attrs["pressure"]):
                    self.database.insert_pressure(path, variable, p, i)

    def test_initial_state_given_pattern(self):
        path = "file.nc"
        variable = "relative_humidity"
        self.database.insert_variable(path, variable)
        navigator = db.Navigator(self.database, {"label": "*.nc"})
        state = db.initial_state(navigator, "label")
        result = state["variable"]
        expect = variable
        self.assertEqual(expect, result)

    def test_initial_state(self):
        self.make_database()
        navigator = db.Navigator(self.database, {"label": "*.nc"})
        state = db.initial_state(navigator, "label")
        self.assertEqual(state["initial_times"], [
            "2019-01-01 00:00:00",
            "2019-01-01 12:00:00",
        ])
        self.assertEqual(state["initial_time"], "2019-01-01 12:00:00")
        self.assertEqual(state["valid_times"], [
            "2019-01-01 12:00:02",
            "2019-01-01 13:00:02"
        ])
        self.assertEqual(state["valid_time"], "2019-01-01 12:00:02")
        self.assertEqual(state["pressures"], [
            1000,
            950
        ])
        self.assertEqual(state["pressure"], 1000)


class TestImageControls(unittest.TestCase):
    def test_image_controls_show(self):
        menu = [("A", "a"), ("B", "b")]
        controls = images.Controls(menu)
        controls.select("A")
        self.assertEqual(controls.groups[0].active, [0])
        self.assertEqual(controls.dropdowns[0].value, "a")
