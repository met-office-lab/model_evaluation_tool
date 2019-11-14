"""
Configure application
---------------------

This module implements parsers and data structures
needed to configure the application. It supports
richer settings than those that can be easily
represented on the command line by leveraging file formats
such as YAML and JSON that are widely used to configure
applications.

.. autoclass:: Config
   :members:

.. autoclass:: FileGroup
   :members:

.. autofunction:: load_config

.. autofunction:: from_files

"""
import os
import typing
import yaml
from forest.export import export


__all__ = []


class DriverSpec(typing.NamedTuple):
    name: str
    settings: dict = {}


class DatasetSpec(typing.NamedTuple):
    label: str
    driver: DriverSpec


class Config(object):
    """Configuration data structure

    This high-level object represents the application configuration.
    It is file format agnostic but has helper methods to initialise
    itself from disk or memory.

    .. note:: This class is intended to provide the top-level
              configuration with low-level details implemented
              by specialist classes, e.g. :class:`FileGroup`
              which contains meta-data for files

    :param data: native Python data structure representing application
                 settings
    """
    def __init__(self, data):
        self.data = data

    def __repr__(self):
        return "{}({})".format(
                self.__class__.__name__,
                self.data)

    @property
    def specs(self):
        return self._specs(self.data)

    @staticmethod
    def _specs(data):
        if "datasets" not in data:
            return []
        datasets = data["datasets"]
        labels = [ds["label"] for ds in datasets]
        drivers = [ds["driver"] for ds in datasets]
        return [
                DatasetSpec(label,
                    DriverSpec(driver["name"], driver["settings"]))
                for label, driver in zip(labels, drivers)]

    @property
    def patterns(self):
        if "files" in self.data:
            return [(f["label"], f["pattern"])
                    for f in self.data["files"]]
        return []

    @classmethod
    def load(cls, path):
        """Parse settings from either YAML or JSON file on disk

        The configuration can be controlled elegantly
        through a text file. Groups of files can
        be specified in a list.

        .. note:: Relative or absolute directories are
                  declared through the use of a leading /

        .. code-block:: yaml

            files:
                - label: Trial
                  pattern: "*.nc"
                  directory: trial/output
                - label: Control
                  pattern: "*.nc"
                  directory: control/output
                - label: RDT
                  pattern: "*.json"
                  directory: /satellite/rdt/json
                  file_type: rdt

        :param path: JSON/YAML file to load
        :returns: instance of :class:`Config`
        """
        with open(path) as stream:
            try:
                # PyYaml 5.1 onwards
                data = yaml.full_load(stream)
            except AttributeError:
                data = yaml.load(stream)
        return cls(data)

    @classmethod
    def from_files(cls, files, file_type="unified_model"):
        """Configure using list of file names and a file type

        :param files: list of file names
        :param file_type: keyword to apply to all files
        :returns: instance of :class:`Config`
        """
        return cls({
            "files": [dict(pattern=f, label=f, file_type=file_type)
                for f in files]})

    @property
    def file_groups(self):
        return [FileGroup(**data)
                for data in self.data["files"]]


class FileGroup(object):
    """Meta-data needed to describe group of files

    To describe a collection of related files extra
    meta-data is needed. For example, the type of data
    contained within the files or how data is catalogued
    and searched.

    :param label: decription used by buttons and tooltips
    :param pattern: wildcard pattern used by either SQL or glob
    :param locator: keyword describing search method (default: 'file_system')
    :param file_type: keyword describing file contents (default: 'unified_model')
    :param directory: leaf/absolute directory where file(s) are stored (default: None)
    """
    def __init__(self,
            label,
            pattern,
            locator="file_system",
            file_type="unified_model",
            directory=None):
        self.label = label
        self.pattern = pattern
        self.locator = locator
        self.file_type = file_type
        self.directory = directory

    @property
    def full_pattern(self):
        if self.directory is None:
            return self.pattern
        return os.path.join(self.directory, self.pattern)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            raise Exception("Can not compare")
        attrs = ("label", "pattern", "locator", "file_type", "directory")
        return all(
                getattr(self, attr) == getattr(other, attr)
                for attr in attrs)

    def __repr__(self):
        arg_attrs = [
            "label",
            "pattern"]
        args = [self._str(getattr(self, attr))
                for attr in arg_attrs]
        kwarg_attrs = [
            "locator",
            "file_type",
            "directory"]
        kwargs = [
            "{}={}".format(attr, self._str(getattr(self, attr)))
                for attr in kwarg_attrs]
        return "{}({})".format(
                self.__class__.__name__,
                ", ".join(args + kwargs))
    @staticmethod
    def _str(value):
        if isinstance(value, str):
            return "'{}'".format(value)
        else:
            return str(value)


@export
def load_config(path):
    """Load configuration from a file"""
    return Config.load(path)


@export
def from_files(files, file_type):
    """Define configuration with a list of files"""
    return Config.from_files(files, file_type)
