import numpy as np
import fnmatch
import glob
import os
from .exceptions import (
        InitialTimeNotFound,
        ValidTimesNotFound,
        PressuresNotFound)
from forest import (
        db,
        gridded_forecast,
        ghrsstl4,
        unified_model,
        eida50,
        rdt,
        intake_loader,
        saf,
)


class Navigator:
    def __init__(self, config):
        # TODO: Once the idea of a "Group" exists we can avoid using the
        # config and defer the sub-navigator creation to each of the
        # groups. This will remove the need for the `_from_group` helper
        # and the logic in FileSystemNavigator.from_file_type().
        # Also, it'd be good to switch the identification of groups from
        # using the `pattern` to using the `label`. In general, not every
        # group would have a `pattern`.
        # e.g.
        # self._navigators = {group.label: group.navigator for group in ...}
        self._navigators = {group.label: self._from_group(group)
                           for group in config.file_groups}

    @classmethod
    def _from_group(cls, group):
        if group.locator == 'database':
            database = db.get_database(group.database_path)
            glob_patterns = {group.label: group.pattern}
            navigator = db.Navigator(database, glob_patterns)
        else:
            navigator = FileSystemNavigator._from_group(group)
        return navigator

    def variables(self, label):
        navigator = self._navigators[label]
        return navigator.variables(label)

    def initial_times(self, label, variable=None):
        navigator = self._navigators[label]
        return navigator.initial_times(label, variable=variable)

    def valid_times(self, label, variable, initial_time):
        navigator = self._navigators[label]
        return navigator.valid_times(label, variable, initial_time)

    def pressures(self, label, variable, initial_time):
        navigator = self._navigators[label]
        return navigator.pressures(label, variable, initial_time)


class FileSystemNavigator:
    """Navigates collections of file(s)

    .. note:: This is a naive implementation designed
              to support basic command line file usage
    """
    def __init__(self, paths, coordinates=None):
        self.paths = paths
        if coordinates is None:
            coordinates = unified_model.Coordinates()
        self.coordinates = coordinates

    @classmethod
    def _from_group(cls, group):
        paths = cls._expand_paths(group.pattern)
        return cls.from_file_type(paths, group.file_type)

    @classmethod
    def from_file_type(cls, paths, file_type):
        if file_type.lower() == "rdt":
            coordinates = rdt.Coordinates()
        elif file_type.lower() == "eida50":
            coordinates = eida50.Coordinates()
        elif file_type.lower() == 'griddedforecast':
            # XXX This needs a "Group" object ... not "paths"
            return gridded_forecast.Navigator(paths)
        elif file_type.lower() == 'intake':
            return intake_loader.Navigator()
        elif file_type.lower() == 'ghrsstl4':
            return ghrsstl4.Navigator(paths)
        elif file_type.lower() == "unified_model":
            coordinates = unified_model.Coordinates()
        elif file_type.lower() == "saf":
            coordinates = saf.Coordinates()
        else:
            raise Exception("Unrecognised file type: '{}'".format(file_type))
        return cls(paths, coordinates)

    @classmethod
    def _expand_paths(cls, pattern):
        return glob.glob(os.path.expanduser(pattern))

    def variables(self, pattern):
        paths = fnmatch.filter(self.paths, pattern)
        names = []
        for path in paths:
            names += self.coordinates.variables(path)
        return list(sorted(set(names)))

    def initial_times(self, pattern, variable=None):
        paths = fnmatch.filter(self.paths, pattern)
        times = []
        for path in paths:
            try:
                time = self.coordinates.initial_time(path)
                if time is None:
                    continue
                times.append(time)
            except InitialTimeNotFound:
                pass
        return list(sorted(set(times)))

    def valid_times(self, pattern, variable, initial_time):
        paths = fnmatch.filter(self.paths, pattern)
        arrays = []
        for path in paths:
            try:
                array = self.coordinates.valid_times(path, variable)
                if array is None:
                    continue
                arrays.append(array)
            except ValidTimesNotFound:
                pass
        if len(arrays) == 0:
            return []
        return np.unique(np.concatenate(arrays))

    def pressures(self, pattern, variable, initial_time):
        paths = fnmatch.filter(self.paths, pattern)
        arrays = []
        for path in paths:
            try:
                array = self.coordinates.pressures(path, variable)
                if array is None:
                    continue
                arrays.append(array)
            except PressuresNotFound:
                pass
        if len(arrays) == 0:
            return []
        return np.unique(np.concatenate(arrays))
