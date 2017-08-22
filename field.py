'''
aaa
'''

import os
import numpy as np
from timeseries import TimeSeries as TimeSeries


class Field:
    '''
    The Field class stores data relative to an Oil field, such as the well data
    and well types. The class itself is a thin wrapper over the TimeSeries
    class, however, it allows querying oil-field specific data, such as
    property data from producer or injector wells separately for multiple
    properties.
    '''

    def __init__(self, well_types=None):
        self.well_types = well_types
        self.well_data = {}
        self._name = ''

    def __len__(self):
        '''
        Returns the number of timesteps for this field.
        '''
        if not len(self.well_data):
            return 0
        first_field_key = next(iter(self.well_data))
        return len(self.well_data[first_field_key])

    @property
    def properties(self):
        '''
        Returns a list of properties loaded by this field.
        '''
        return list(self.well_data.keys())

    @property
    def name(self):
        '''
        Returns the name of this field.
        '''
        return self._name
    
    def get_well_data(self, well_prop=None, well_type=None, well_names=None):
        '''
        Returns the well data stored in this object. Optionally, may return
        only a subset of the wells defined by their type or names, but not both.
        This function raises a ValueError exception if the data was not set yet.

        Arguments:
        well_prop -- The desired property. If no property is given, data from
        all properties is returned.
        well_type -- The type of well to be returned, either producer ('P') or
        injector ('I'). This parameter has precedence over the well_names
        parameter, meaning that if 'P' is passed as a parameter, and wells of
        type 'I' are present in the well_names list, only wells of type 'P' in
        the well_names list will be returned.
        well_names -- An optional list containing the well names.

        Returns:
        A dictionary of numpy.ndarray with the selected data using properties as
        keys.
        '''
        if not len(self):
            raise ValueError('No well data loaded yet.')

        if not well_prop:
            well_prop = list(self.well_data.keys())
        if isinstance(well_prop, str):
            well_prop = [well_prop]

        well_data = {}
        for prop in well_prop:
            if prop not in self.well_data.keys():
                print('WARNING: Property {} not found. Continuing.'.format(prop))
                continue

            wells = self.well_data[prop].names
            if well_names and len(well_names) > 0:
                wells = [w for w in wells if w in well_names]
            if well_type and isinstance(well_type, str):
                wells = [w for w in wells if self.well_types[w] == well_type]

            well_data[prop] = self.well_data[prop].get_data(names=list(wells))

        return well_data

    def get_group_data(self, well_type=None, well_prop=None):
        '''
        Accumulates the production values of wells of a given type for each
        property and returns them. If well_types == 'P', then the production
        values for all wells of type 'P' will be accumulated in a single numpy
        array for each property and returned.

        Arguments:
        well_type -- Optional argument to indicate the types of wells to be
        accumulated. If set to None, the production of all wells will be
        accumulated and returned.
        well_prop -- Optional argument indicating the properties to retrieve
        data from. If left empty, all properties will be queried.

        Returns:
        A dictionary with the properties as keys and the group data, in np.array
        format, as values.
        '''
        prop_dict = self.get_well_data(well_prop=well_prop, well_type=well_type)
        group_dict = {}
        for prop_name, prop_data in prop_dict.items():
            group_data = np.zeros(shape=(len(prop_data), 1), dtype=np.float)
            group_data = np.sum(prop_data, axis=1)
            group_dict[prop_name] = group_data
            
        return group_dict

    def load_field(self, base_path, prop_list, fieldname):
        '''
        Loads the well data from a CSV file. The CSV file must be delimited by
        commas, each well is defined by a single column and the first line
        must contain the wells names. This method raises ValueError exceptions
        if the filename is empty or the specified file does not exist.

        Arguments:
        base_path -- Root of the data directory. 
        prop_list -- Single property or list of properties to load. Must be
        folders under base_path.
        fieldname -- The name of the field to load inside each base_path/prop
        folder. This will also be the field name returned by 'name'.
        '''
        self._name = fieldname
        if isinstance(prop_list, str):
            prop_list = [prop_list]
        for p in prop_list:
            filename = os.path.join(base_path, p, fieldname) + '.csv'
            self.well_data[p] = TimeSeries(filename=filename)

    def set_well_types(self, well_types, overwrite=False):
        '''
        Sets the well types. If overwrite is True, then any wells with a type
        already defined in the object have their type overwritten by the new
        value in the well_types parameter, else, the new value is discarded.
        By default, any new wells will be appended to the dict of existing
        wells.

        Arguments:
        well_types -- A dictionary with the well names as keys and the well
        types as values. In general, the allowed types are 'P' for producer and
        'I' for injector wells, however, other types are allowed and it's the
        user's responsability to control and add meaning to them.
        overwrite -- If set to True, any values already present in the object
        will have their type overwritten by the new value. Default value is
        False.
        '''
        if not self.well_types:
            self.well_types = well_types
        if overwrite:
            self.well_types.update(well_types)
        else:
            well_list = [(k, v) for k, v in well_types.items() if k not in self.well_types]
            self.well_types.update(dict(well_list))


    def get_well_types(self, well_names=None):
        '''
        Returns the types of wells in this field. If the optional well_names
        parameter is defined, returns only the types of the given wells.

        Arguments:
        well_names -- Optional argument indicating which well types should be
        returned.

        Returns:
        A dictionary with the well names as keys and the types as values.
        '''
        if not self.well_types:
            raise ValueError('No well types defined yet.')

        if well_names is not None:
            return dict((k, v) for k, v in self.well_types.items() if k in well_names)
        return self.well_types


def test_Field():
    PROPERTY = 'NP'
    FIELDNAME = 'UNISIM-I-H_001'
    BASE_DATA_PATH = os.path.join('..', 'data', 'ajustado')

    well_types = {}
    with open(os.path.join(BASE_DATA_PATH, '..', 'welltype.csv'), 'r') as fin:
        contents = fin.readlines()
        names, types = contents[0].strip().split(','), contents[1].strip().split(',')
        well_types = dict(zip(names, types))
    
    f = Field()
    print(len(f))

    f.set_well_types(well_types=well_types)

    f.load_field(BASE_DATA_PATH, 'NP', FIELDNAME)
    print(len(f))

    f.load_field(BASE_DATA_PATH, ['NP', 'WP', 'QW', 'QO'], FIELDNAME)
    print(len(f))
    #print(f.get_well_types())

    a = f.get_well_data()
    #print(a.keys())
    #print(a['NP'].shape)

    a = f.get_well_data(well_prop=['NP', 'WP'], well_names=['NA1A', 'NA3D', 'INJ003'])
    #print(a.keys())
    #print(a['NP'].shape)

    a = f.get_well_data(well_type='P', well_names=['NA1A', 'NA3D', 'INJ003'])
    #print(a.keys())
    #print(a['NP'].shape)

    f.get_group_data('NP', 'P')
    a = f.get_group_data(['NP', 'QW'], 'P')
    #print(a)
    #print(f.get_well_types())
    #print(f.get_well_types(well_names=['PROD005', 'INJ003']))

if __name__ == '__main__':
    test_Field()
