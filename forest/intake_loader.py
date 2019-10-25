import intake
from datetime import datetime
from collections import namedtuple
import bokeh
import numpy
import iris
import functools

from forest import geo, gridded_forecast

URL = 'https://raw.githubusercontent.com/NCAR/intake-esm-datastore/master/catalogs/pangeo-cmip6.json'
HALO_SIZE = 7


@functools.lru_cache(maxsize=16)
def _load_from_intake(
        experiment_id,
        table_id,
        grid_label,
        variable_id,
        institution_id,
        activity_id,
        parent_source_id,
        member_id):
    collection = intake.open_esm_datastore(URL)
    print('opening catalogue')
    cat = collection.search(
        experiment_id=experiment_id,
        table_id=table_id,
        grid_label=grid_label,
        institution_id=institution_id,
        member_id=member_id,
        variable_id=variable_id)
    print('downloading data')
    dset_dict = cat.to_dataset_dict(
        zarr_kwargs={'consolidated': True, 'decode_times': False},
        cdf_kwargs={'chunks': {}, 'decode_times': False})
    ds_label = f'{activity_id}.{institution_id}.{parent_source_id}.{experiment_id}.{table_id}.{grid_label}'
    xr = dset_dict[ds_label]
    print(xr[variable_id])
    cube = xr[variable_id].to_iris()
    return cube[0]  # drop member dimension


class IntakeView(object):
    def __init__(self, loader, color_mapper):
        self.loader = loader
        self.color_mapper = color_mapper
        self.source = bokeh.models.ColumnDataSource({
            "x": [],
            "y": [],
            "dw": [],
            "dh": [],
            "image": []})

    def render(self, state):
        self.source.data = self.loader.image(state)

    def add_figure(self, figure):
        renderer = figure.image(
            x="x",
            y="y",
            dw="dw",
            dh="dh",
            image="image",
            source=self.source,
            color_mapper=self.color_mapper)
        tool = bokeh.models.HoverTool(
            renderers=[renderer],
            tooltips=[
                ("Name", "@name"),
                ("Value", "@image @units"),
                ('Valid', '@valid{%F %H:%M}'),
                ("Level", "@level"),
                ("Experiment", "@experiment"),
                ("Institution", "@institution"),
                ("Member", "@memberid")
            ],
            formatters={
                'valid': 'datetime',
            })
        figure.add_tools(tool)
        return renderer


class IntakeLoader:
    def __init__(self):
        self.experiment_id = 'ssp585'
        self.table_id = 'Amon'
        self.grid_label = 'gn'
        self.variable_id = 'ta'
        self.institution_id = 'NCAR'
        self.activity_id = 'ScenarioMIP'
        self.parent_source_id = 'CESM2'
        self.member_id = 'r2i1p1f1'
        self._label = f'{self.experiment_id}_{self.institution_id}_{self.member_id}'
        self._cube = _load_from_intake(experiment_id=self.experiment_id,
                                       table_id=self.table_id,
                                       grid_label=self.grid_label,
                                       variable_id=self.variable_id,
                                       institution_id=self.institution_id,
                                       activity_id=self.activity_id,
                                       parent_source_id=self.parent_source_id,
                                       member_id=self.member_id)
        self._cube.coord('air_pressure').convert_units('hPa')

    def image(self, state):
        cube = self._cube
        reference_time = datetime.now()  # temporary
        variable = state.variable,
        init_time = state.initial_time
        valid_time = state.valid_time
        pressure = state.pressure

        selected_time = gridded_forecast._to_datetime(valid_time)

        def time_comp(select_time, time_cell):  #
            data_time = gridded_forecast._to_datetime(time_cell.point)
            try:
                if abs((select_time - data_time).days) < 2:
                    return True
            except ValueError:
                pass
            return False

        def lat_filter(lat):
            return -85.0 < lat < 85.0

        if cube is None or state.initial_time is None:
            data = gridded_forecast.empty_image()
        else:
            cube_cropped = cube.extract(
                iris.Constraint(latitude=lat_filter,
                                air_pressure=pressure,
                                time=functools.partial(time_comp,
                                                       selected_time)))
            lat_pts = cube_cropped.coord('latitude').points
            long_pts = cube_cropped.coord('longitude').points - 180.0
            cube_data_cropped = cube_cropped.data
            cube_width = int(cube_data_cropped.shape[1] / 2)
            cube_data_cropped = numpy.concatenate(
                [cube_data_cropped[:, cube_width:],
                 cube_data_cropped[:, :cube_width]], axis=1)

            data = geo.stretch_image(long_pts, lat_pts, cube_data_cropped)
            data['image'] = [numpy.ma.masked_array(data['image'][0],
                                                   mask=numpy.isnan(
                                                       data['image'][0]))]
            data.update(gridded_forecast.coordinates(state.valid_time,
                                                     state.initial_time,
                                                     state.pressures,
                                                     state.pressure))
            data.update({
                'name': [self._label],
                'units': [str(cube.units)],
                'experiment': [self.experiment_id],
                'institution': [self.institution_id],
                'memberid': [self.member_id]

            })
        return data


class Navigator:
    def __init__(self):
        self.experiment_id = 'ssp585'
        self.table_id = 'Amon'
        self.grid_label = 'gn'
        self.variable_id = 'ta'
        self.institution_id = 'NCAR'
        self.activity_id = 'ScenarioMIP'
        self.parent_source_id = 'CESM2'
        self.member_id = 'r2i1p1f1'
        self._label = f'{self.experiment_id}_{self.institution_id}_{self.member_id}'
        self._cube = _load_from_intake(experiment_id=self.experiment_id,
                                       table_id=self.table_id,
                                       grid_label=self.grid_label,
                                       variable_id=self.variable_id,
                                       institution_id=self.institution_id,
                                       activity_id=self.activity_id,
                                       parent_source_id=self.parent_source_id,
                                       member_id=self.member_id)
        self._cube.coord('air_pressure').convert_units('hPa')

    def variables(self, pattern):
        return ['air_temperature']

    def initial_times(self, pattern, variable=None):
        cube = self._cube
        for cell in cube.coord('time').cells():
            init_time = gridded_forecast._to_datetime(cell.point)
            return [init_time]

    def valid_times(self, pattern, variable, initial_time):
        cube = self._cube
        valid_times = [gridded_forecast._to_datetime(cell.point) for cell in
                       cube.coord('time').cells()]
        return valid_times

    def pressures(self, pattern, variable, initial_time):
        cube = self._cube
        pressures = []
        try:
            pressures = [cell.point for cell in
                         cube.coord('air_pressure').cells()]
        except iris.exceptions.CoordinateNotFoundError:
            pass
        return pressures


if __name__ == '__main__':
    State = namedtuple('State',
                       field_names=['variable', 'initial_time', 'valid_time',
                                    'pressures', 'pressure'])
    state = State('temperature', datetime.now(), datetime.now(), [1, 2, 3], 1)

    dummy_loader = IntakeLoader()

    dummy_image = dummy_loader.image(state)

    print(dummy_image)

    print('PART 2')
    navigator = Navigator()
    print(navigator.variables())
    print(navigator.pressures())
    print(navigator.valid_times())
    print(navigator.initial_times())