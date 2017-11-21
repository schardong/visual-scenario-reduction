#!/usr/bin/python3
# -*- coding: utf-8 -*-

import numpy as np
import matplotlib
from matplotlib.backends.backend_qt5agg import \
    FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib import cm
from PyQt5.QtWidgets import QSizePolicy

from brushableplot import BrushableCanvas
from zoompanhandler import ZoomPanHandler


def fanchart(ax, x, y, q=np.arange(0, 110, 10),
             colormap=cm.get_cmap(name='Reds', lut=8), **kwargs):
    """
    A helper function to plot a fanchart.

    Parameters
    ----------
    ax: matplotlib.Axes
        The axes to plot the fanchart.
    x: np.array
        The data for the X axis.
    y: np.array
        The data for the Y axis. Must be a series of curves arranged by row.
    q: array
        A list of percentiles to pass to np.percentile.
    colormap: char or matplotlib.colors.Colormap
        The colors to apply to the ax.fill_between polygons. May be a
        character, or a colormap.
    kwargs: other named arguments
        Other arguments to pass to fill_between.

    Returns
    -------
    artists: list
        List of artists added to the axes.
    """
    if len(x) != y.shape[1]:
        fmt = 'Incompatible data dimensions x={}, y=({}, {})'
        raise ValueError(fmt.format(len(x), y.shape[0], y.shape[1]))
    if not isinstance(x, list):
        x = list(x)

    q_curves = np.percentile(y, q=q, axis=0)
    n = len(q)
    first_idx = range(0, int(n / 2))
    second_idx = range(n - 1, int(n / 2) - 1, -1)
    rows_idx = zip(first_idx, second_idx)

    artists = []
    _, y = q_curves.shape
    for idx, idx_tuple in enumerate(rows_idx):
        c1, c2 = q_curves[idx_tuple, :]
        curr_color = colormap
        if isinstance(colormap, matplotlib.colors.Colormap):
            curr_color = colormap(idx + 1)
        a = ax.fill_between(x=x, y1=c1, y2=c2, color=curr_color, **kwargs)
        artists.append(a)

    return artists


class Fanchart(FigureCanvas, BrushableCanvas):
    """
    This class builds a Fanchart of the given data.

    Given a set of time series, this class builds a fanchart of the input data.
    This class also supports highlighting specific series. In this case, the
    selected data series is plotted over the base fanchart as a line chart.

    There is also support for selecting reference series. These series are
    also plotted over the fanchart with the specified plot parameters. They are
    never unhighlighted and cannot be selected, acting only as a means to
    compare it to the data distribution.
    """

    def __init__(self, canvas_name, parent=None, width=5, height=5, dpi=100,
                 q=np.arange(0, 110, 10), **kwargs):
        """
        Parameters
        ----------
        canvas_name: str
            The name of this object. To be used when notifying the parent
            widget of changes.
        parent: Qt5.QWidget
            The parent widget. Default is None. The parent widget must
            implement the 'set_brush_data' method. This method receives
            this objects's canvas_name and a list containing the indices of
            all objects highlighted.
        width: int
            The width of this plot canvas. Default value is 5.
        height: int
            The height of this plot canvas. Default value is 5.
        dpi: int
            This canvas's resolution. Default value is 100.
        q: array
            A list of percentiles to pass to np.percentile.
        kwargs: other named arguments
            Other arguments to pass to fill_between.
        """
        # Initial setup
        fig = Figure(figsize=(width, height), dpi=dpi)
        self._axes = fig.add_subplot(1, 1, 1)
        FigureCanvas.__init__(self, fig)
        FigureCanvas.setSizePolicy(self,
                                   QSizePolicy.Expanding,
                                   QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
        self.setParent(parent)
        BrushableCanvas.__init__(self, canvas_name, parent)

        self._zphandler = ZoomPanHandler(self.axes, scale_factor=1.5)

        # Data setup
        self._curves = None
        self._percentiles = q
        self._reference_idx = set()
        self._highlighted_ts = None
        self._curvenames = None
        self._time_range = ()
        self._hidden_curves = set()

        # Plot styles
        self._plot_title = self.base_plot_name()
        self._cmap_name = 'rainbow'
        self._fan_cmap_name = 'gray_r'
        self._curves_colors = {}
        self._reference_parameters = {}
        self._vline = None
        self._vline_props = {}
        self._plotted_lines = None
        self._time_range_poly = None
        self._time_range = ()
        self._hovered_line = None
        self._plot_params = kwargs
        if 'linewidth' not in self._plot_params:
            self._plot_params['linewidth'] = 1.5

    def __del__(self):
        self._axes = None
        self._curves = None
        self._percentiles = None
        self._reference_idx.clear()
        self._reference_parameters.clear()
        BrushableCanvas.__del__(self)

    @property
    def axes(self):
        """
        Returns the axes associated to this object.

        Returns
        -------
        out: matplotlib.Axes
            The associated axes.
        """
        return self._axes

    @property
    def curves(self):
        """
        Returns the curves used to build this fanchart.

        Returns
        -------
        out: numpy.array
            The stored curves as a matrix arranged by row.
        """
        return self._curves

    @property
    def percentiles(self):
        """
        Returns the percentile range used to build the fans of the fanchart.
        """
        return self._percentiles

    @property
    def plot_title(self):
        """
        Returns the title of this plot.
        """
        return self._plot_title

    @classmethod
    def base_plot_name(self):
        """
        Static method that returns the base name of this plot.
        """
        return 'Fanchart'

    @property
    def colormap_name(self):
        """
        Returns the name of the colormap being used to plot the lines over the
        fanchart.

        Returns
        -------
        out: str
            The colormap's name.
        """
        return self._cmap_name

    @property
    def fan_colormap_name(self):
        """
        Returns the name of the colormap being used to plot the base fanchart.

        Returns
        -------
        out: str
            The colormap's name.
        """
        return self._fan_cmap_name

    @property
    def highlighted_timestep(self):
        """
        Returns the value of the highlighted timestep.

        Returns
        -------
        out: int or None
            The value of the highlighted timestep. If no timestep is
            highlighted, returns None.
        """
        return self._highlighted_ts

    @property
    def curvenames(self):
        """
        Returns a list with the names of the curves.
        """
        return self._curvenames

    @property
    def time_range(self):
        """
        Returns the currently used timestep range.
        """
        return self._time_range

    def set_highlighted_timestep(self, ts, update_chart=True, **plotprops):
        """
        Sets the currently highlighted timestep.

        This will signal the chart to plot a vertical line indicating the
        currently selected timestep. This behavior can be disabled by passing
        'None' as the 'ts' parameter.

        Raises a ValueError exception if the timestep is out of range. Has no
        effect if there are no curves set.

        Parameters
        ----------
        ts: int or None
            The timestep value, or None if the indicator line should be erased.
        update_chart: boolean
            Switch that indicates if the plot should be updated now.
        plotprops: keyword arguments
            Plot style for the timestep indicator line.
        """
        if self.curves is None:
            return
        if ts is not None and (ts < 0 or ts >= self.curves.shape[1]):
            raise ValueError('Timestep out of range.')

        self._highlighted_ts = ts
        self._vline_props = plotprops
        if not self._vline_props:
            self._vline_props = {'color': 'b', 'linewidth': 2}
        if update_chart:
            self.update_chart(highlighted_timestep=True)

    def set_curves(self, curves, update_chart=True):
        """
        Sets the data about the curves to be projected. Resets any information
        about the reference data and highlighted data.

        Parameters
        ----------
        curves: numpy.array
            The new curve data matrix arranged by row.
        update_chart: boolean
            Switch that indicates if the plot should be updated now.
        """
        self._curves = curves
        self._time_range = (0, self.curves.shape[1])

        # Reseting the reference data
        self._reference_idx.clear()
        self._reference_parameters.clear()

        # Reseting the highlighted data
        self.highlight_data(self._highlighted_data,
                            erase=True, update_chart=False)

        if update_chart:
            self.update_chart(data_changed=True)
            self._zphandler.set_base_transforms()

    def set_reference_curve(self, curve_idx, is_ref, update_chart=True,
                            **kwargs):
        """
        Adds or removes a curve from the reference curves set. Reference curves
        are not included in the picking and will never have their alpha changed
        when a common curve is selected.

        Parameters
        ----------
        curve_idx: int
            The index of the curve in the matrix.
        is_ref: boolean
            Switch to indicate if the curve should be added or removed from the
            reference curves set.
        update_chart: boolean
            Switch to indicate if the chart should be updated now.
        kwargs: Plot arguments for the reference curve.
        """
        if is_ref:
            self._reference_idx.add(curve_idx)
            self._reference_parameters[curve_idx] = kwargs
        else:
            self._reference_idx.discard(curve_idx)
            if self._reference_parameters[curve_idx]:
                del self._reference_parameters[curve_idx]
        if update_chart:
            self.update_chart(data_changed=True, apply_transforms=True)

    def is_reference_curve(self, idx):
        """
        Returns if a given curve index is a reference curve.
        Raises a ValueError if the index is out of range.

        Parameters
        ----------
        idx: int
            The curve index to query.

        Returns
        -------
        True if the given index is a reference curve, False otherwise.
        """
        if idx < 0 or idx > self.curves.shape[0]:
            raise ValueError('Index out of range.')
        return idx in self._reference_idx

    def set_draw_curve(self, idx, draw):
        """
        Sets wheter a curve should be drawn or not. Also works on
        reference curves.

        Parameters
        ----------
        idx: int
            The curve's index.
        draw: boolean
            True to draw the curve, False to hide it.
        """
        if idx < 0 or idx > self.curves.shape[0]:
            raise ValueError('Index out of range')

        if not draw:
            self._hidden_curves.add(idx)
        else:
            self._hidden_curves.discard(idx)

        if self._plotted_lines and self._plotted_lines[idx]:
            self._plotted_lines[idx].set_visible(draw)

        self.draw()

    def is_drawing_curve(self, idx):
        """
        Returns wheter the selected curve is hidden or not.
        """
        if idx < 0 or idx > self.curves.shape[0]:
            raise ValueError('Index out of range')
        if self._plotted_lines and self._plotted_lines[idx]:
            return self._plotted_lines[idx].get_visible()
        else:
            return False

    def set_curve_tooltip(self, curve_idx):
        """
        Draws the tooltip over the selected curve

        Parameters
        ----------
        curve_idx: int
            The index of the curve to draw the tooltip on.
        """
        # Erasing the highlighted series, or restoring its width, if it was
        # highlighted before the mouse-hover event.
        if self._hovered_line:
            if self._hovered_line[0] not in self.highlighted_data:
                self._hovered_line[0].set_visible(False)
            else:
                self._hovered_line[0].set_linewidth(
                    self._plot_params['linewidth'])

        if not curve_idx or curve_idx not in range(self.curves.shape[0]):
            self.draw()
            return

        #if not self.is_drawing_curve(curve_idx):
        #    print('Not drawing {}'.format(curve_idx))
        #    return

        # Fix bug here.
        color = 'black'
        print(self._reference_idx)
        if curve_idx in self._reference_idx:
            print("curve_idx is a reference = {}".format(curve_idx))
            color = self._reference_parameters[curve_idx]['color']
        else:
            color = self._curves_colors[curve_idx]

        curr_xlim = self.axes.get_xlim()
        curr_ylim = self.axes.get_ylim()
        self._hovered_line = self.axes.plot(
            self.curves[curve_idx, :], color=color,
            linewidth=self._plot_params['linewidth'] * 2)

        self.axes.set_xlim(curr_xlim)
        self.axes.set_ylim(curr_ylim)

        self.draw()

    def set_fan_colormap(self, cmap_name, update_chart=True):
        """
        Sets the colormap to apply to the fans in the Fanchart.

        Parameters
        ----------
        cmap_name: str
            The colormap's name. Any values accepted by matplotlib are valid.
        update_chart: boolean
            Switch to indicate if the plot should be updated. Default value
            is True.
        """
        self._fan_cmap_name = cmap_name
        if update_chart:
            self.update_chart(data_changed=True, apply_transforms=True)

    def set_lines_colormap(self, cmap_name, update_chart=True):
        """
        Sets the colormap to use when plotting the lines.

        Parameters
        ----------
        cmap_name: str
            The colormap's name. Any values accepted by matplotlib are valid.
        update_chart: boolean
            Switch to indicate if the plot should be updated. Default value
            is True.
        """
        self._cmap_name = cmap_name
        if update_chart:
            self.update_chart(data_changed=True, apply_transforms=True)

    def set_plot_title(self, title, update_chart=True):
        """
        Sets the title of this plot.

        Parameters
        ----------
        title: str
            This plot's title.
        update_chart: boolean
            Switch to indicate if the chart should be updated at the end of
            the method.
        """
        self._plot_title = title
        if update_chart:
            self.update_chart(data_changed=True, apply_transforms=True)

    def set_curvenames(self, curvenames):
        """
        Sets the names of the curves. These are shown if the tooltip feature
        is enabled.

        Parameters
        ----------
        curvenames: list of str
            A list containing the data's names.
        """
        self._curvenames = curvenames

    def set_time_range(self, start, end, update_chart=True):
        """
        Sets the time range to use when creating the rank curves.

        Parameters
        ----------
        start: int
            The starting timestep, must be larger than 0 and smaller than end.
        end: int
            The last timestep, inclusive. Must be larget than start and
            smaller than self.curves.shape[1].
        update_chart: boolean
            Switch to indicate if the plot should be updated. Default value is
            True.
        """
        if self.curves is None:
            return
        if start < 0 or end > self.curves.shape[1] or start >= end:
            return

        self._time_range = (start, end)
        if update_chart:
            self.update_chart(data_changed=True)
            self._zphandler.set_base_transforms()

    def update_chart(self, **kwargs):
        """
        Function to update the plot when the parameters are changed.

        Parameters
        ----------
        kwargs: Keyword arguments
        """
        if self.curves is None:
            return

        tr = range(self.time_range[0], self.time_range[1])
        nref_idx = set(range(self.curves.shape[0])) - self._reference_idx

        if 'selected_data' in kwargs:
            # First, we clear the lines from the chart.
            for l in self._plotted_lines:
                if l is not None:
                    l.set_visible(False)

#            for i in self._hidden_curves:
#                self._plotted_lines[i].set_visible(False)

#            visible_idx = set(range(self.curves.shape[0])) - self._hidden_curves
#            for i in visible_idx:
#                self._plotted_lines[i].set_visible(True)

            # Then we add the selected lines over it.
            for i in self.highlighted_data:
                if i not in self._hidden_curves:
                    self._plotted_lines[i].set_visible(True)

        if 'data_changed' in kwargs:
            self.axes.cla()
            self.axes.set_title(self.plot_title)
            self.axes.set_xlabel('Timestep')
            self.axes.set_ylabel('Value')
            xmin, xmax = self.time_range
            self.axes.set_xlim([xmin, xmax - 1])

            lines_colormap = cm.get_cmap(name=self.colormap_name,
                                         lut=len(self.curves))
            self._curves_colors = dict((i, lines_colormap(i))
                                       for i in nref_idx)

            self._plotted_lines = [None] * self.curves.shape[0]

            if self.curves is not None:
                fanchart(ax=self.axes,
                         x=tr,
                         y=self.curves[:, tr],
                         colormap=cm.get_cmap(
                             name=self.fan_colormap_name, lut=8),
                         q=self.percentiles,
                         **self._plot_params)

                for i in nref_idx:
                    self._plotted_lines[i] = self.axes.plot(
                        tr, self.curves[i, tr],
                        color=self._curves_colors[i])[0]

                # We must add the selected data over the fanchart.
                self.update_chart(selected_data=True)

                # If we have reference curves, we plot them here.
                for i in self._reference_idx:
                    self._plotted_lines[i] = self.axes.plot(
                        tr, self.curves[i, tr], **self._reference_parameters[i])[0]

        if 'highlighted_timestep' in kwargs:
            # If the timestep indicator line is drawn, we set it as invisible
            # here.
            if self._vline is not None:
                self._vline.set_visible(False)

            if self.highlighted_timestep is not None:
                self._vline = self.axes.axvline(x=self.highlighted_timestep,
                                                **self._vline_props)

        if 'apply_transforms' in kwargs:
            self._zphandler.apply_transforms()

        self.draw()


def main():
    from PyQt5.QtWidgets import (QApplication, QComboBox, QFormLayout, QLabel,
                                 QMainWindow, QWidget, QPushButton,
                                 QHBoxLayout, QVBoxLayout)
    import sys
    """
    Simple feature test function for the Fanchart class.
    """
    class MyTestWidget(QMainWindow):
        """
        Qt derived class to embed our plot.
        """

        def __init__(self):
            super().__init__()
            self.left = 0
            self.top = 0
            self.title = 'Fanchart test'
            self.width = 1000
            self.height = 1000
            self.colormaps = {'Shades of Red': 'Reds',
                              'Shades of Blue': 'Blues',
                              'Rainbow': 'rainbow',
                              'Greyscale': 'gray_r'}

            self.lines_colormap = {'Autumn': 'autumn',
                                   'Copper': 'copper',
                                   'Heat': 'hot',
                                   'Summer': 'summer',
                                   'Winter': 'winter',
                                   'Terrain': 'gist_earth', }
            self.buildUI()
            self.update_data()

        def buildUI(self):
            self.setWindowTitle(self.title)
            self.setGeometry(self.left, self.top, self.width, self.height)

            self.fanchart = Fanchart(canvas_name='fanchart1', parent=self)
            title = self.fanchart.base_plot_name() + ' of Random Data'
            self.fanchart.set_plot_title(title)

            self.combo_colormap = QComboBox(self)
            self.combo_colormap.currentIndexChanged.connect(
                self.colormap_changed)
            for k in self.colormaps.keys():
                self.combo_colormap.addItem(k)

            self.combo_line_colormap = QComboBox(self)
            self.combo_line_colormap.currentIndexChanged.connect(
                self.line_colormap_changed)
            for k in self.lines_colormap.keys():
                self.combo_line_colormap.addItem(k)

            p10_button = QPushButton('Enable P10', self)
            p10_button.clicked.connect(self.enableP10)
            p50_button = QPushButton('Enable P50', self)
            p50_button.clicked.connect(self.enableP50)
            p90_button = QPushButton('Enable P90', self)
            p90_button.clicked.connect(self.enableP90)
            rand_data = QPushButton('Generate new data', self)
            rand_data.clicked.connect(self.update_data)
            reset_button = QPushButton('Reset view', self)
            reset_button.clicked.connect(self.reset_plot)

            self.main_widget = QWidget(self)
            l = QHBoxLayout(self.main_widget)
            l.addWidget(self.fanchart)

            combo_layout = QFormLayout(self.main_widget)
            l1 = QLabel('Fans colormap:')
            l2 = QLabel('Lines colormap:')
            combo_layout.addRow(l1, self.combo_colormap)
            combo_layout.addRow(l2, self.combo_line_colormap)

            sidelayout = QVBoxLayout(self.main_widget)
            sidelayout.addLayout(combo_layout)
            sidelayout.addWidget(p90_button)
            sidelayout.addWidget(p50_button)
            sidelayout.addWidget(p10_button)
            sidelayout.addWidget(rand_data)
            sidelayout.addWidget(reset_button)

            l.addLayout(sidelayout)

            self.setFocus()
            self.setCentralWidget(self.main_widget)

        def update_data(self):
            curves = np.random.normal(size=(10, 50))
            curves = np.vstack(
                (curves, np.percentile(curves, q=[10, 50, 90], axis=0)))

            self.fanchart.set_curves(curves)
            self.fanchart.set_reference_curve(curves.shape[0] - 3,
                                              True, False, color='m')
            self.fanchart.set_reference_curve(curves.shape[0] - 2,
                                              True, False, color='y')
            self.fanchart.set_reference_curve(curves.shape[0] - 1,
                                              True, True, color='c')

        def brush_series(self, child_name, obj_ids):
            print('widget {} brushed some objects.'.format(child_name))
            print('Objects:\n\t', obj_ids)

        def keyPressEvent(self, e):
            # Test if the key is a number.
            if e.key() in range(48, 58):
                k = e.key() - 48
                erase = self.fanchart.is_data_instance_highlighted(k)
                self.fanchart.highlight_data(k, erase)

        def enableP10(self):
            c = self.fanchart.curves.shape[0]
            draw = self.fanchart.is_drawing_curve(c - 3)
            self.fanchart.set_draw_curve(c - 3, not draw)

        def enableP50(self):
            c = self.fanchart.curves.shape[0]
            draw = self.fanchart.is_drawing_curve(c - 2)
            self.fanchart.set_draw_curve(c - 2, not draw)

        def enableP90(self):
            c = self.fanchart.curves.shape[0]
            draw = self.fanchart.is_drawing_curve(c - 1)
            self.fanchart.set_draw_curve(c - 1, not draw)

        def colormap_changed(self):
            opt = self.combo_colormap.currentText()
            self.fanchart.set_fan_colormap(self.colormaps[opt])

        def line_colormap_changed(self):
            opt = self.combo_line_colormap.currentText()
            self.fanchart.set_lines_colormap(self.lines_colormap[opt])

        def reset_plot(self):
            self.fanchart.reset_plot()

    app = QApplication(sys.argv)
    ex = MyTestWidget()
    ex.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
