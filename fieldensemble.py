import os
import numpy as np
from field import Field


class FieldEnsemble:
    """
    TODO(gschardong):
    1) Read well type data;
    2) Read observed data;
    3) Return data by well type (done in Field);
    4) Return only historic or forecast data;
    """

    def __init__(
        self, well_data_path="", prop_list=[], well_type_path="", obs_data_path=""
    ):
        self._fields = {}
        self._well_types = {}
        self._obs_data = np.zeros(shape=(1, 1))

        if well_data_path:
            self.load_fields(base_path=well_data_path, prop_list=prop_list)
        if well_type_path:
            self.load_well_types(path=well_type_path)
        if obs_data_path:
            self.load_observed_data(path=obs_data_path)

    def __len__(self):
        """
        Returns the number of fields stored in this ensemble.
        """
        return len(self._fields)

    @property
    def field_names(self):
        """
        Returns the names of the fields of this ensemble.
        """
        return list(self._fields.keys())

    @property
    def well_names(self):
        """
        Returns the well names of the fields in this ensemble. It is expected
        that all fields have the same wells.
        """
        return list(self._well_types.keys())

    @property
    def well_types(self):
        """
        Returns the types of wells for the fields in this ensemble.

        Returns:
        A dictionary with the wells' names as keys and their types as values.
        """
        return self._well_types

    def get_well_data(self, well_name="", well_prop=""):
        """
        Returns the data of a property, or list of properties of a well from
        all fields.

        Arguments:
        well_name -- A single well name. Raises ValueError if not well is found.
        well_prop -- One or more properties to query.

        Returns -- A numpy.ndarray for each property selected. If more than one
        property is selected, then a dictionary with the properties as keys is
        returned.
        """
        raise NotImplementedError

    def get_group_data(self, well_type="", well_prop=""):
        """ """
        if isinstance(well_prop, str):
            well_prop = [well_prop]

        ## Creating a dict of numpy arrays, each with N rows and F columns,
        ## where N is the number of timesteps and F is the number of fields in
        ## this ensemble.
        group_data = {}
        for prop in well_prop:
            s = (len(self.get_field(self.field_names[0])), len(self))
            group_data[prop] = np.zeros(shape=s)

        field_names = sorted(self.field_names)
        for i, fname in enumerate(field_names):
            field = self.get_field(fname)
            fgroup = field.get_group_data(well_type=well_type, well_prop=well_prop)
            for prop, data in fgroup.items():
                group_data[prop][:, i] = data

        return group_data

    def get_field(self, name):
        """
        Returns a field with the given name. If no field is found, then None
        will be returned instead. If a list of names is given, then a dictionary
        will be returned.

        Arguments:
        name -- A single string of list of strings containing the names of the
        fields to return.

        Returns:
        A single field (if name is a string) or a dictionary with the
        corresponding fields (if name is a list).
        """
        if isinstance(name, str):
            return self._fields[name]
        elif isinstance(name, list):
            fields = {}
            for n in name:
                fields[n] = self.get_field(n)
            return fields

    def add_field(self, field):
        """
        Adds a new field to the ensemble. Raises ValueError if the Field is
        invalid (None or empty).

        Arguments:
        field -- The field to be added.
        """
        self._fields[field.name] = field

    def rem_field(self, field_name):
        """
        Removes a field from the ensemble. Raises ValueError if the field is
        not in the ensemble.

        Arguments:
        field_name -- The name of the field to remove.
        """
        if not field_name in self._fields:
            raise ValueError("Field not in ensemble.")
        self._fields[field_name] = None

    def load_fields(self, base_path, prop_list=[]):
        """
        Reads all CSV files in the directory indicated as Fields. Raises
        ValueError if the path is invalid.

        Arguments:
        base_path -- Root path to the CSV files.
        prop_list -- The list of properties to be read. Must be folder names
        under 'base_path'.
        """
        if not os.path.exists(base_path):
            raise ValueError("Invalid path.")

        if isinstance(prop_list, str):
            prop_list = [prop_list]
        if not len(prop_list):
            prop_list = os.listdir(base_path)

        fieldnames = os.listdir(os.path.join(base_path, prop_list[0]))

        for field in fieldnames:
            field = field.split(".")[0]
            f = Field()
            f.load_field(base_path, prop_list, field)
            self.add_field(f)

    def load_well_types(self, path):
        """
        Loads the well types for the fields of this ensemble. If there are
        fields in the ensemble, then their corresponding set_well_types method
        is called.

        Arguments:
        path -- Path to the well type file. This file must be in CSV format
        with the well names as a header and the well types as the only data.
        The file must be named 'welltypes.csv'.
        """
        filename = "welltype.csv"
        with open(os.path.join(path, filename), "r") as fin:
            contents = fin.readlines()
            names, types = contents[0].strip().split(","), contents[1].strip().split(
                ","
            )
            self._well_types = dict(zip(names, types))

            if len(self):
                for k, f in self._fields.items():
                    self._fields[k].set_well_types(self.well_types)

    def load_observed_data(self, path):
        """
        Loads the observed data for the fields.
        """
        if not path or not path:
            raise ValueError("Invalid path, no observed data loaded.")

        filenames = os.listdir(path)
        for f in filenames:
            pass


def test_FieldEnsemble():
    PROPERTY = ["NP", "WP"]
    BASE_DATA_PATH = os.path.join("..", "data", "ajustado")

    fe = FieldEnsemble(well_data_path=BASE_DATA_PATH, well_type_path="../data")
    print(fe.well_types)

    group_data_dict = fe.get_group_data(well_prop=PROPERTY, well_type="P")

    for gdata in group_data_dict:
        print(len(gdata))
        print(gdata.shape)


if __name__ == "__main__":
    test_FieldEnsemble()
