import unittest
import os
import datetime as dt
import forest.aws
import forest.data
import iris
import netCDF4
import numpy as np
import warnings


class FakeLoader(object):
    def file_exists(self, path):
        return True


class TestFormat(unittest.TestCase):
    def test_format(self):
        config = "config"
        result = "{}_{{:%Y%m%d}}.nc".format(config)
        expect = "config_{:%Y%m%d}.nc"
        self.assertEqual(result, expect)


class TestGetAvailableDatasets(unittest.TestCase):
    @unittest.skip("too complicated to test")
    def test_get_available_datasets(self):
        file_loader = None
        dataset_template = {}
        model_run_times = [dt.datetime(2018, 8, 17, tzinfo=dt.timezone.utc)]
        result = forest.data.get_available_datasets(file_loader,
                                                    dataset_template,
                                                    model_run_times)
        expect = {'20180817T0000Z': {}}
        self.assertEqual(result, expect)

    def test_get_model_run_times(self):
        period_start = dt.datetime(2018, 8, 17)
        num_days = 1
        model_period = 24
        result = forest.data.get_model_run_times(period_start,
                                                 num_days,
                                                 model_period)
        expect = [dt.datetime(2018, 8, 17, tzinfo=dt.timezone.utc)]
        self.assertEqual(result, expect)

    def test_format_model_run_time(self):
        model_run_time = dt.datetime(2018, 8, 17, tzinfo=dt.timezone.utc)
        result = forest.data.format_model_run_time(model_run_time)
        expect = '20180817T0000Z'
        self.assertEqual(result, expect)

    def test_get_var_lookup_ga6_keys(self):
        config = "ga6"
        lookup = forest.data.get_var_lookup(config)
        result = sorted(lookup.keys())
        expect = [
            'air_temperature',
            'cloud_fraction',
            'mslp',
            'precipitation',
            'relative_humidity',
            'wet_bulb_potential_temp',
            'x_wind',
            'x_winds_upper',
            'y_wind',
            'y_winds_upper'
        ]
        self.assertEqual(result, expect)

    def test_config_file_given_ga6_returns_existing_file(self):
        config = "ga6"
        result = forest.data.config_file(config)
        self.assertTrue(os.path.exists(result))


class TestForestDataset(unittest.TestCase):
    def setUp(self):
        self.test_directory = os.path.dirname(os.path.realpath(__file__))
        self.bucket = forest.aws.S3Mount(self.test_directory)
        self.ra1t_var_lookup = forest.data.get_var_lookup("ra1t")

        # Ignore numpy FutureWarnings generated by np.issubdtype
        warnings.simplefilter(action='ignore', category=FutureWarning)

    def tearDown(self):
        warnings.resetwarnings()

    def test_get_var_lookup_mslp(self):
        config = forest.data.GA6_CONF_ID
        var_lookup = forest.data.get_var_lookup(config)
        result = var_lookup['mslp']
        expect = {
            "accumulate": False,
            "filename": "umnsaa_pverb",
            "stash_item": 222,
            "stash_name": "air_pressure_at_sea_level",
            "stash_section": 16
        }
        self.assertEqual(result, expect)

    def test_get_data_should_support_model_run_time(self):
        """Uses actual file to understand ForestDataset

        ..note:: Think about how best to unit test
                 ForestDataset.get_data()
        """
        file_name = "SEA_phi2km1p5_ra1t_20180821T0000Z.nc"
        dataset = forest.data.ForestDataset(file_name,
                                            self.bucket,
                                            self.ra1t_var_lookup)
        variable = "precipitation"
        selected_time = 426337.5
        cube = dataset.get_data(variable, selected_time)
        self.assertIsInstance(cube, iris.cube.Cube)
        self.assertEqual(cube.shape, (1350, 1200))

    def test_forest_dataset_given_minimal_file(self):
        """
        A minimal model grid and time domain to assert cube
        loaded correctly
        """
        file_name = "test-forest-dataset-given-minimal-file.nc"
        time_length = 4 + 1
        time_0_length = time_length
        time_1_length = time_length - 1
        time_2_length = time_length - 1
        longitude_length = 16
        longitude_0_length = longitude_length
        latitude_length = 12 + 1
        latitude_0_length = latitude_length - 1
        time = np.arange(time_length)
        time_0 = np.arange(time_0_length)
        time_1 = 1 + np.arange(time_1_length)
        time_2 = 1 + np.arange(time_2_length)
        time_2_bnds = to_bounds(time_2, 0.5)
        forecast_reference_time = 0.
        forecast_period = 3 * np.arange(time_length)
        forecast_period_0 = forecast_period
        forecast_period_1 = forecast_period[1:]
        forecast_period_2 = np.array([1.5 + i * 3. for i in range(time_2_length)])
        forecast_period_2_bnds = to_bounds(forecast_period_2, width=1.5)
        longitude = np.linspace(0, 90, longitude_length)
        longitude_0 = np.linspace(0, 90, longitude_0_length)
        latitude = np.linspace(0, 90, latitude_length)
        latitude_0 = np.linspace(0, 90, latitude_0_length)
        rainfall_rate = np.ones((time_2_length,
                                 latitude_0_length,
                                 longitude_0_length))
        with netCDF4.Dataset(file_name, "w") as dataset:
            define_ra1t_file(dataset, dimensions={
                                 "time": time_length,
                                 "time_0": time_0_length,
                                 "time_1": time_1_length,
                                 "time_2": time_2_length,
                                 "longitude": longitude_length,
                                 "longitude_0": longitude_0_length,
                                 "latitude": latitude_length,
                                 "latitude_0": latitude_0_length,
                             })
            dataset.variables["time"][:] = time
            dataset.variables["time_0"][:] = time_0
            dataset.variables["time_1"][:] = time_1
            dataset.variables["time_2"][:] = time_2
            dataset.variables["time_2_bnds"][:] = time_2_bnds
            dataset.variables["longitude"][:] = longitude
            dataset.variables["longitude_0"][:] = longitude_0
            dataset.variables["latitude"][:] = latitude
            dataset.variables["latitude_0"][:] = latitude_0
            dataset.variables["pressure"][:] = np.array([1000, 500, 250, 50])
            dataset.variables["forecast_reference_time"][:] = forecast_reference_time
            dataset.variables["forecast_period"][:] = forecast_period
            dataset.variables["forecast_period_0"][:] = forecast_period_0
            dataset.variables["forecast_period_1"][:] = forecast_period_1
            dataset.variables["forecast_period_2"][:] = forecast_period_2
            dataset.variables["forecast_period_2_bnds"][:] = forecast_period_2_bnds
            dataset.variables["height"][:] = 0.
            dataset.variables["stratiform_rainfall_rate"][:] = rainfall_rate

        # System under test
        dataset = forest.data.ForestDataset(file_name,
                                            self.bucket,
                                            self.ra1t_var_lookup)
        cube = dataset.get_data("precipitation", selected_time=1.)

        # Assertions
        with netCDF4.Dataset(file_name, "r") as dataset:
            expect_longitude_0 = dataset.variables["longitude_0"][:]
            expect_latitude_0 = dataset.variables["latitude_0"][:]
        self.assertEqual(cube.units, 'kg m-2 hour-1') # rainfall rate in hours
        np.testing.assert_array_equal(cube.data, 3600. * rainfall_rate[1])
        np.testing.assert_array_equal(cube.coord('time').points, [1.])
        np.testing.assert_array_almost_equal(cube.coord('longitude').points,
                                             expect_longitude_0)
        np.testing.assert_array_almost_equal(cube.coord('latitude').points,
                                             expect_latitude_0)

    def test_to_bounds(self):
        """Helper method to generate coordinate bounds"""
        result = to_bounds([0, 1, 2], width=0.5)
        expect = [[-0.5, 0.5],
                  [0.5, 1.5],
                  [1.5, 2.5]]
        np.testing.assert_array_equal(result, expect)


def to_bounds(points, width):
    """Convert a coordinate to an array describing its bounds"""
    if isinstance(points, list):
        points = np.array(points, dtype=np.float)
    bounds = np.empty((len(points), 2), dtype=points.dtype)
    bounds[:, 0] = points[:] - width
    bounds[:, 1] = points[:] + width
    return bounds


def define_ra1t_file(dataset, dimensions=None):
    """Define RA1T dimensions, variables and attributes"""
    defaults = dict([('time', 41),
                     ('latitude', 1201),
                     ('longitude', 1600),
                     ('time_0', 41),
                     ('latitude_0', 1200),
                     ('longitude_0', 1600),
                     ('pressure', 4),
                     ('time_1', 40),
                     ('time_2', 40),
                     ('bnds', 2)])
    if dimensions is None:
        lengths = defaults
    else:
        lengths = dict(defaults, **dimensions)
    for key in ['time',
                'latitude',
                'longitude',
                'time_0',
                'latitude_0',
                'longitude_0',
                'pressure',
                'time_1',
                'time_2',
                'bnds']:
        dataset.createDimension(key, lengths[key])
    var = dataset.createVariable('y_wind', 'float32', ('time', 'latitude', 'longitude'))
    var.standard_name = 'y_wind'
    var.units = 'm s-1'
    var.um_stash_source = 'm01s03i226'
    var.grid_mapping = 'latitude_longitude'
    var.coordinates = 'forecast_period forecast_reference_time height'
    var = dataset.createVariable('latitude_longitude', 'int32', ())
    var.grid_mapping_name = 'latitude_longitude'
    var.longitude_of_prime_meridian = 0.0
    var.earth_radius = 6371229.0
    var = dataset.createVariable('time', 'float64', ('time',))
    var.axis = 'T'
    var.units = 'hours since 1970-01-01 00:00:00'
    var.standard_name = 'time'
    var.calendar = 'gregorian'
    var = dataset.createVariable('latitude', 'float32', ('latitude',))
    var.axis = 'Y'
    var.units = 'degrees_north'
    var.standard_name = 'latitude'
    var = dataset.createVariable('longitude', 'float32', ('longitude',))
    var.axis = 'X'
    var.units = 'degrees_east'
    var.standard_name = 'longitude'
    var = dataset.createVariable('forecast_period', 'float64', ('time',))
    var.units = 'hours'
    var.standard_name = 'forecast_period'
    var = dataset.createVariable('forecast_reference_time', 'float64', ())
    var.units = 'hours since 1970-01-01 00:00:00'
    var.standard_name = 'forecast_reference_time'
    var.calendar = 'gregorian'
    var = dataset.createVariable('height', 'float64', ())
    var.units = 'm'
    var.standard_name = 'height'
    var.positive = 'up'
    var = dataset.createVariable('air_pressure_at_sea_level', 'float32', ('time_0', 'latitude_0', 'longitude_0'))
    var.standard_name = 'air_pressure_at_sea_level'
    var.units = 'Pa'
    var.um_stash_source = 'm01s16i222'
    var.grid_mapping = 'latitude_longitude'
    var.coordinates = 'forecast_period_0 forecast_reference_time'
    var = dataset.createVariable('time_0', 'float64', ('time_0',))
    var.axis = 'T'
    var.units = 'hours since 1970-01-01 00:00:00'
    var.standard_name = 'time'
    var.calendar = 'gregorian'
    var = dataset.createVariable('latitude_0', 'float32', ('latitude_0',))
    var.axis = 'Y'
    var.units = 'degrees_north'
    var.standard_name = 'latitude'
    var = dataset.createVariable('longitude_0', 'float32', ('longitude_0',))
    var.axis = 'X'
    var.units = 'degrees_east'
    var.standard_name = 'longitude'
    var = dataset.createVariable('forecast_period_0', 'float64', ('time_0',))
    var.units = 'hours'
    var.standard_name = 'forecast_period'
    var = dataset.createVariable('y_wind_0', 'float32', ('time_0', 'pressure', 'latitude', 'longitude'))
    var.standard_name = 'y_wind'
    var.units = 'm s-1'
    var.um_stash_source = 'm01s15i202'
    var.grid_mapping = 'latitude_longitude'
    var.coordinates = 'forecast_period_0 forecast_reference_time'
    var = dataset.createVariable('pressure', 'float64', ('pressure',))
    var.axis = 'Z'
    var.units = 'hPa'
    var.long_name = 'pressure'
    var = dataset.createVariable('x_wind', 'float32', ('time_0', 'pressure', 'latitude', 'longitude'))
    var.standard_name = 'x_wind'
    var.units = 'm s-1'
    var.um_stash_source = 'm01s15i201'
    var.grid_mapping = 'latitude_longitude'
    var.coordinates = 'forecast_period_0 forecast_reference_time'
    var = dataset.createVariable('relative_humidity', 'float32', ('time_1', 'pressure', 'latitude_0', 'longitude_0'))
    var.standard_name = 'relative_humidity'
    var.units = '%'
    var.um_stash_source = 'm01s16i204'
    var.grid_mapping = 'latitude_longitude'
    var.coordinates = 'forecast_period_1 forecast_reference_time'
    var = dataset.createVariable('time_1', 'float64', ('time_1',))
    var.axis = 'T'
    var.units = 'hours since 1970-01-01 00:00:00'
    var.standard_name = 'time'
    var.calendar = 'gregorian'
    var = dataset.createVariable('forecast_period_1', 'float64', ('time_1',))
    var.units = 'hours'
    var.standard_name = 'forecast_period'
    var = dataset.createVariable('air_temperature', 'float32', ('time', 'latitude_0', 'longitude_0'))
    var.standard_name = 'air_temperature'
    var.units = 'K'
    var.um_stash_source = 'm01s03i236'
    var.grid_mapping = 'latitude_longitude'
    var.coordinates = 'forecast_period forecast_reference_time height_0'
    var = dataset.createVariable('height_0', 'float64', ())
    var.units = 'm'
    var.standard_name = 'height'
    var.positive = 'up'
    var = dataset.createVariable('x_wind_0', 'float32', ('time', 'latitude', 'longitude'))
    var.standard_name = 'x_wind'
    var.units = 'm s-1'
    var.um_stash_source = 'm01s03i225'
    var.grid_mapping = 'latitude_longitude'
    var.coordinates = 'forecast_period forecast_reference_time height'
    var = dataset.createVariable('stratiform_rainfall_rate', 'float32', ('time_2', 'latitude_0', 'longitude_0'))
    var.standard_name = 'stratiform_rainfall_rate'
    var.units = 'kg m-2 s-1'
    var.um_stash_source = 'm01s04i203'
    var.cell_methods = 'time_2: mean (interval: 1 hour)'
    var.grid_mapping = 'latitude_longitude'
    var.coordinates = 'forecast_period_2 forecast_reference_time'
    var = dataset.createVariable('time_2', 'float64', ('time_2',))
    var.axis = 'T'
    var.bounds = 'time_2_bnds'
    var.units = 'hours since 1970-01-01 00:00:00'
    var.standard_name = 'time'
    var.calendar = 'gregorian'
    dataset.createVariable('time_2_bnds', 'float64', ('time_2', 'bnds'))
    var = dataset.createVariable('forecast_period_2', 'float64', ('time_2',))
    var.bounds = 'forecast_period_2_bnds'
    var.units = 'hours'
    var.standard_name = 'forecast_period'
    dataset.createVariable('forecast_period_2_bnds', 'float64', ('time_2', 'bnds'))
    var = dataset.createVariable('wet_bulb_potential_temperature', 'float32', ('time_1', 'pressure', 'latitude_0', 'longitude_0'))
    var.long_name = 'wet_bulb_potential_temperature'
    var.units = 'K'
    var.um_stash_source = 'm01s16i205'
    var.grid_mapping = 'latitude_longitude'
    var.coordinates = 'forecast_period_1 forecast_reference_time'
    var = dataset.createVariable('cloud_area_fraction_assuming_maximum_random_overlap', 'float32', ('time', 'latitude_0', 'longitude_0'))
    var.long_name = 'cloud_area_fraction_assuming_maximum_random_overlap'
    var.units = '1'
    var.um_stash_source = 'm01s09i217'
    var.grid_mapping = 'latitude_longitude'
    var.coordinates = 'forecast_period forecast_reference_time'
    dataset.source = 'Data from Met Office Unified Model'
    dataset.um_version = '10.6'
    dataset.Conventions = 'CF-1.5'
