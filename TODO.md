# TO-DO list
- [ ] Read observed data.
  - [ ] Observed data is organized in a manner that each file describes a single well. Each well file contains several properties and the first column is the time index in days. The original time index must be obtained in order to address this.
  - [ ] Group-based observed data is done by accumulating the observed data for all wells of a group for a given property. Since not all timesteps contain observed data, the time index must be used (each possible value must be assined to a corresponding row in a np.ndarray). Possible solution for this:
  ```python
    # The first column is the time index column.
    # self._obs_data is a dict indexed by the well name. The values are of type TimeSeries and contain the observed data.
    def _build_time_idx():
        possible_times = set()
        days_col='days'
        for well_name, well in self._obs_data.items():
            days = well.get_data(days_col)
            for d in days:
                possible_times.add(d[0])
        possible_times = list(possible_times)
        possible_times = sorted(possible_times)
        self.time_idx = dict(zip(possible_times, range(possible_times)))

    def get_group_obs_data(well_type='P'):
        pass
  ```
- [ ] Add a base plotting class that inherits (or is inherited by) the BrushablePlot class.
  - [ ] Several functions are repeated through the plotting classes, set_curves being one of them. Further code analysis may help determine if this base class is doable and viable or not.
- [ ] Give the option to disable brushing and linking on some plots later on.
- [ ] Add the "visibility" concept to the plots' data. This will allow for a new UI element to set the visibility of our realizations.
- [x] Group the options using "Algorithm options" and "Graphical options" in the side panel;
  - [x] Make a small options section for each plot;
- [x] Make the Fanchart use grayscale colors for the fans;
- [x] Connect the projection and fanchart. If the user hovers the mouse over a point in the projection plot, show a vertical line indicating the timestep of that point in the fanchart;
- [x] Make a better colormap for the plots;
  - [x] Add colormap support for the distance chart;
  - [x] Add colormap support for the rank chart;
  - [x] Add colormap support for the projection chart;
  - [x] Add colormap support for the fanchart;
- [x] Add a mouse_motion callback to the distance chart. Mark all the points below the pointer with a color, and those above in grayscale. With a click, the user may confirm the selection;
  - [x] Add the callbacks to the distance chart;
  - [x] Add a horizonal line indicating the precise distance;
  - [x] Add the callbacks to the rank chart;
  - [x] Pop a dialog to ask for confirmation if a selection was made before;
  - [x] Make this behavior optional by a button press (Ctrl + mouse disables it);
- [x] Change the mouse cursor on long operations (Changing the property, loading data);
- [x] Remove the confirmation when clearing the selected data.
- [ ] Enable area selection in the projection plot;
- [x] Zoom mechanisms to the plots;
- [ ] Panning mechanisms to the plots;
- [x] Legend indicating the P10, P50 and P90's glyphs;
- [ ] Add a trace to the distance plot. This trace will show the distance with increasingly lesser timesteps. (T-1), (T-2), (T-3), ....
- [x] Tooltip indicating the model's name when the user hovers the mouse over them.

## Ideas
- [ ] Density 2D scatter plot.
  - [ ] Would act as a 2D fanchart using the projection data.
- [ ] Add color based on the timestep to the MP-Plot. Add the option to use opacity as well.
- [ ] Apply different colors for different time series in order to compare them;
- [ ] Add visual feedback to the time-range selected by the user (from the distance chart to the other plots).


## Research
* Figure out the 3 timesteps that the distance plot fails to deliver the correct result;
* Test the method in CMOST and compare the results (which software is cheaper, more acessible, error metrics, etc.).
