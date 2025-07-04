#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This module contains the classes to plot the Time Lapsed projection plot.
"""

import math
import numpy as np
import scipy.spatial.distance
import sklearn.manifold
from enum import Enum
from matplotlib.collections import LineCollection
from matplotlib.colors import rgb_to_hsv, hsv_to_rgb
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib import cm
from PyQt5.QtCore import QPoint
from PyQt5.QtWidgets import QSizePolicy, QToolTip
from PyQt5.QtGui import QFont, QPalette, QColor
from scipy.interpolate import interp1d

from brushableplot import BrushableCanvas
from mp import time_lapse_lamp
from zoompanhandler import ZoomPanHandler


def _plot_timelapse_lamp(
    ax, point_list, plot_points=True, plot_lines=False, path_colors=None, **kwargs
):
    """
    A helper function to plot the time lapse lamp points.

    Parameters
    ----------
    ax: matplotlib.Axes
        The axes to plot the points.
    point_list: list of numpy.array
        List of points organized by time step.
    plot_points: boolean
        Switch to indicate if the points should be plotted. Default value is
        True.
    plot_lines: boolean
        Switch to indicate if the lines connecting the points should be
        plotted. Default value is False.
    path_colors: list
        A list of RGBA colors to apply to the plotted elements (lines and
        points). An easy way to generate this is to use matplotlib's cm module.
    kwargs: other named arguments
        Other arguments to pass to ax.scatter and ax.plot

    Returns
    -------
    artists: tuple
        A tuple of 2 lists. The first list contains the artist added by the
        call to ax.scatter (if plot_points is True) and the second list
        contains the artists added by ax.plot (if plot_lines is True).
    """
    if not isinstance(point_list, list):
        point_list = [point_list]

    scatter_artists = []
    plot_artists = []
    for i, p in enumerate(point_list):
        x = p[:, 0]
        y = p[:, 1]
        pc = None
        pl = None
        if path_colors is not None:
            kwargs["c"] = path_colors[i]
        if plot_points:
            pc = ax.scatter(x, y, **kwargs)
        if plot_lines:
            pl = ax.plot(x, y, **kwargs)
        scatter_artists.append(pc)
        plot_artists.append(pl)
    return (scatter_artists, plot_artists)


class SaturationMapType(Enum):
    CONSTANT = "constant"
    LINEAR_INC = "linear_increasing"
    LINEAR_DEC = "linear_decreasing"
    VARIANCE = "variance"


class GlyphSizeMap(Enum):
    LINEAR_INC = "linear_increasing"
    LINEAR_DEC = "linear_decreasing"


class TimeLapseChart(FigureCanvas, BrushableCanvas):
    """
    This class builds a series of successive multidimensional projections of
    the input data and plots them as point paths.

    Given a set of time series, this class uses the Classic, Metric
    Multidimensional Scaling algorithm to create a series of control points
    using the and then, using the Local Affine Multidimensional Projection,
    the series are projected at successive time intervals, thus creating a path
    for each curve.

    This class supports marking the paths using brushing & linking.
    """

    def __init__(self, canvas_name, parent=None, width=5, height=5, dpi=100, **kwargs):
        """
        Parameters
        ----------
        canvas_name: str
            The name of this object. To be used when notifying the parent widget
            of changes.
        parent: Qt5.QWidget
            The parent widget. Default is None. The parent widget must implement
            the 'brush_series' method. This method receives this objects's
            canvas_name and a list containing the indices of all objects
            highlighted.
        width: int
            The width of this plot canvas. Default value is 5.
        height: int
            The height of this plot canvas. Default value is 5.
        dpi: int
            This canvas's resolution. Default value is 100.
        kwargs:
            Other keyword arguments. These arguments are used when plotting the
            line and point projections. No line or point specific options may
            be set here. Set those using the
            set_line_plot_params/set_point_plot_params methods.
        """
        # Initial setup
        fig = Figure(figsize=(width, height), dpi=dpi)
        self._axes = fig.add_subplot(1, 1, 1)
        FigureCanvas.__init__(self, fig)
        FigureCanvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
        self.setParent(parent)
        BrushableCanvas.__init__(self, canvas_name, parent)

        self._zphandler = ZoomPanHandler(self.axes, scale_factor=1.5)

        # Data setup
        self._curves = None
        self._control_points = None
        self._projected_curves = []
        self._timestep_data = [0, 0, 1]
        self._reference_idx = set()
        self._dims = 2
        self._tree = None
        self._curvenames = None
        self._ts_variance = None
        self._hidden_curves = set()

        # Plot styles
        self._plot_lines = False
        self._plot_points = True
        self._plot_brush_stroke = False
        self._point_artists = {}
        self._line_artists = {}
        self._brush_stroke_artists = {}
        self._plot_title = self.base_plot_name()
        self._reference_parameters = {}
        self._cmap_name = "rainbow"
        self._plot_params = kwargs
        self._brush_size_lims = (2, 35)
        self._saturation_map = SaturationMapType.CONSTANT
        self._glyph_size_map = GlyphSizeMap.LINEAR_INC

        if "picker" not in self._plot_params:
            self._plot_params["picker"] = 3

        self._plot_line_params = dict(linewidth=1.5)
        self._plot_point_params = dict(s=40)

        # Callback IDs
        self._cb_pick_id = None
        self._cb_mouse_move_id = None
        self._cb_scrollwheel_id = None
        self._cb_axes_leave_id = None
        self._cb_fig_leave_id = None

        # Callback functions
        self._cb_notify_timestep = None
        self._cb_notify_tooltip = None

        self._connect_cb()

    def __del__(self):
        self._disconnect_cb()
        self._axes = None
        self._control_points = None
        self._curves = None
        self._reference_idx.clear()
        self._reference_parameters.clear()
        self._cb_notify_timestep = None
        self._cb_notify_tooltip = None
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
        Returns the curve data stored in this object.

        Returns
        -------
        out: numpy.array
            The curves matrix arranged by row.
        """
        return self._curves

    @property
    def control_points(self):
        """
        Returns the control points generated by the MDS algorithm.
        Returns
        -------
        out: numpy.array
            A numpy matrix with the control points. The points' order is the
            same as the curves.
        """
        return self._control_points

    @property
    def projected_curves(self):
        """
        Returns a list with the projected points of the curves.

        Returns
        out: list of numpy.array
            The projections of the curves. Each list element is a numpy matrix
            that corresponds to a single curve. Each row in this matrix is the
            projection of that curve up to the selected time step.
        """
        return self._projected_curves

    @property
    def timestep_data(self):
        """
        Returns the list with timestep information. The list has 3 elements,
        the start, end and step size of the timestep,
        """
        return self._timestep_data

    @property
    def start_time(self):
        """
        Returns the index of the first timestep to be considered when
        projecting the data.
        """
        return self.timestep_data[0]

    @property
    def end_time(self):
        """
        Returns the index of the last timestep to be considered when projecting
        the data.
        """
        return self.timestep_data[1]

    @property
    def step_time(self):
        """
        Returns the step size timestep interval to be considered when
        projecting the data.
        """
        return self.timestep_data[2]

    @property
    def plot_points(self):
        """
        Returns True if the projections are being plotted as points.
        """
        return self._plot_points

    @property
    def plot_lines(self):
        """
        Returns True if we are plotting lines over the projections.
        """
        return self._plot_lines

    @property
    def plot_brush_stroke(self):
        """
        Returns True if we are plotting brush strokes over the projections.
        """
        return self._plot_brush_stroke

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
        return "Time-lapsed LAMP Chart"

    @property
    def dims(self):
        """
        Returns the number of dimensions used in the projection.
        """
        return self._dims

    @property
    def colormap_name(self):
        """
        Returns the name of the colormap being used by this chart.

        Returns
        -------
        out: str
            The colormap's name.
        """
        return self._cmap_name

    @property
    def curvenames(self):
        """
        Returns the names of the curves.
        """
        return self._curvenames

    @property
    def point_plot_params(self):
        """
        Returns the plot parameter dictionary used when plotting the projected
        points.
        """
        return self._plot_point_params

    @property
    def line_plot_params(self):
        """
        Returns the plot parameter dictionary used when plotting the projected
        lines.
        """
        return self._plot_line_params

    @property
    def saturation_map_type(self):
        """
        Returns the type of saturation map to use (constant, linear or variance based).
        """
        return self._saturation_map

    @property
    def glyph_size_type(self):
        """
        Returns the type of glyph size map to use (constant, linear, or variance based).
        """
        return self._glyph_size_map

    def set_notify_timestep_callback(self, func):
        """
        Receives a callback function to call when there is a timestep
        selection in the plot.

        Such selections happen when the user hovers the mouse cursor over one
        of the projected points, each point corresponds to a timestep of the
        original set of series. When an event like this is triggered, the
        selected function is called with two arguments: this canvas name and
        the index of the selected timestep.

        Parameters
        ----------
        func: function
            The function to be called. This function will be given this plot's
            name and the timestep selected.
        """
        self._cb_notify_timestep = func

    def set_notify_tooltip_callback(self, func):
        """
        Sets the callback function to call when a tooltip is drawn on this
        plot.

        The callback function given here is called right after drawing the
        tooltip on this plot. This can be used to link several plots.

        Parameters
        ----------
        func: function
            The function to be called after a tooltip is drawn. This function
            receives the plot's name and the selected curve index.
        """
        self._cb_notify_tooltip = func

    def set_curves(self, curves, update_chart=True):
        """
        Sets the data about the curves to be projected. Resets any information
        about the reference data, highlighted data and sets the end timestep if
        it was not set or it is larger than the size of the data.

        Parameters
        ----------
        curves: numpy.array
            A matrix containing the curves. Each row corresponds to a single
            curve.
        update_chart: boolean
            Switch to indicate if the chart should be updated at the end of the
            function.
        """
        v = np.var(curves, axis=0)
        a, b = np.min(v), np.max(v)
        v = (v - a) / (b - a)

        self._ts_variance = v
        self._curves = curves

        # Fixing the end timestep
        if self.end_time == 0 or self.end_time > curves.shape[1]:
            self._timestep_data[1] = curves.shape[1]

        # Reseting the reference data
        self._reference_idx.clear()
        self._reference_parameters.clear()

        # Reseting the highlighted data
        self.highlight_data(self.highlighted_data, erase=True, update_chart=False)

        self._update_projected_data()
        self._build_kdtree()

        if update_chart:
            self.update_chart(data_changed=True, selected_data=True)
        self._zphandler.set_base_transforms()

    def set_reference_curve(self, curve_idx, is_ref, update_chart=True, **kwargs):
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
        if curve_idx not in range(self.curves.shape[0]):
            fmt = "Index out of range: {}/{}"
            raise ValueError(fmt.format(curve_idx, self.curves.shape[0]))
        if is_ref:
            self._reference_idx.add(curve_idx)
            self._reference_parameters[curve_idx] = kwargs
            if curve_idx in self.highlighted_data:
                self.highlight_data(curve_idx, erase=True, update_chart=False)
        else:
            self._reference_idx.discard(curve_idx)
            del self._reference_parameters[curve_idx]
        if update_chart:
            self.update_chart(data_changed=True)

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
            raise ValueError("Index out of range.")
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
            raise ValueError("Index out of range")

        if not draw:
            self._hidden_curves.add(idx)
        else:
            self._hidden_curves.discard(idx)

        if self._point_artists and self._point_artists[idx]:
            self._point_artists[idx].set_visible(draw)
        if self._line_artists and self._line_artists[idx]:
            self._line_artists[idx].set_visible(draw)
        if self._brush_stroke_artists and self._brush_stroke_artists[idx]:
            self._brush_stroke_artists[idx].set_visible(draw)

        self.draw()

    def is_drawing_curve(self, idx):
        """
        Returns wheter the selected curve is hidden or not.
        """
        if idx < 0 or idx > self.curves.shape[0]:
            raise ValueError("Index out of range")
        if self._point_artists:
            return self._point_artists[idx].get_visible()
        elif self._line_artists:
            return self._line_artists[idx].get_visible()
        elif self._brush_stroke_artists:
            return self._brush_stroke_artists[idx].get_visible()
        else:
            raise AttributeError("No draw call made yet")

    def set_timestep_data(
        self, start_time=None, end_time=None, step_time=None, update_chart=True
    ):
        """
        Sets the data about the timestep range to use when projecting the
        curves. Raises AttributeError exceptions if the start time is larger
        than the end time, and if the step size is larger than the given
        interval (end - start).

        The curves must have been set before calling this method.

        Parameters
        ----------
        start_time: int
            The index of the interval's start. Default value is None, will
            assign 0 as the start index.
        end_time: int
            The index of the interval's end. Must not be smaller than the
            start index. Default value is None, will assign the last
            timestep of the given curves.
        step_time: int
            The step size of the interval. Must not be larger than the
            end-start interval. Default value is None, will assign the step
            as 1.
        update_chart: boolean
            Switch to indicate if the plot should be updated before the
            method's end.
        """
        if not start_time or start_time < 0:
            self._timestep_data[0] = 0
            start_time = 0
        if not end_time:
            self._timestep_data[1] = self.curves.shape[1]
            end_time = self.curves.shape[1]
        if not step_time:
            self._timestep_data[2] = 1
            step_time = 1
        if start_time >= end_time:
            raise AttributeError("Start time is larger or equal to end time.")
        if step_time >= end_time - start_time:
            raise AttributeError("Step time is larger than the given time range.")

        self._timestep_data[0] = start_time
        self._timestep_data[1] = end_time
        self._timestep_data[2] = step_time

        self._update_projected_data()
        self._build_kdtree()

        if update_chart:
            self.update_chart(data_changed=True)

    def set_curvenames(self, curvenames):
        """
        Sets the names of the data points. These are shown if the tooltip feature is enabled.

        Parameters
        ----------
        curvenames: list of str
            A list containing the data point's names.
        """
        self._curvenames = curvenames

    # Plot style methods
    def set_plot_points(self, plot_points, update_chart=True):
        """
        Sets the option to plot the data points or not.

        Parameters
        ----------
        plot_points: boolean
            True to enable data points plotting, False to disable it.
        update_chart: boolean
            Switch to indicate if the plot should be updated now.
        """
        self._plot_points = plot_points
        if (
            not self._plot_points
            and not self._plot_lines
            and not self._plot_brush_stroke
        ):
            self.set_plot_lines(True, update_chart=update_chart)
            return
        if update_chart:
            self.update_chart(plot_glyph=True)

    def set_plot_lines(self, plot_lines, update_chart=True):
        """
        Sets the option to plot lines between the data points or not.

        Parameters
        ----------
        plot_lines: boolean
            True to enable line plotting, False to disable it.
        update_chart: boolean
            Switch to indicate if the plot should be updated now.
        """
        self._plot_lines = plot_lines
        if (
            not self._plot_lines
            and not self._plot_points
            and not self._plot_brush_stroke
        ):
            self.set_plot_points(True, update_chart=update_chart)
            return
        if update_chart:
            self.update_chart(plot_glyph=True)

    def set_plot_brush_stroke(self, plot_brush_stroke, update_chart=True):
        self._plot_brush_stroke = plot_brush_stroke
        if plot_brush_stroke:
            self.set_plot_points(False, update_chart=False)
            self.set_plot_lines(False, update_chart=False)
        if (
            not self._plot_lines
            and not self._plot_points
            and not self._plot_brush_stroke
        ):
            self.set_plot_points(True, update_chart=update_chart)
            return
        if update_chart:
            self.update_chart(plot_glyph=True)

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
            self.update_chart(data_changed=True)

    def set_colormap(self, cmap_name, update_chart=True):
        """
        Sets the colormap function to use when plotting.

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

    def set_line_plot_params(self, **kwargs):
        """
        Sets the plot parameters for the line glyphs.

        Parameters
        ----------
        kwargs: Keyword arguments
        """
        self._plot_line_params = kwargs

    def set_point_plot_params(self, **kwargs):
        """
        Sets the plot parameters for the point glyphs.

        Parameters
        ----------
        kwargs: Keyword arguments
        """
        self._plot_point_params = kwargs

    def set_saturation_map_type(self, satmap, update_chart=True):
        """
        Sets the type of saturation map to use when plotting the series.

        Parameters
        ----------
        state: SaturationMapType or str
            Either the Enum SaturationMapType or a string with the map type.
        update_chart: boolean
            Switch to indicate if the plot should be updated. Default value
            is True.
        """
        self._saturation_map = (
            satmap
            if isinstance(satmap, SaturationMapType)
            else SaturationMapType(satmap)
        )
        if update_chart:
            self.update_chart(plot_glyph=True)

    def set_glyph_size_type(self, gsmap, update_chart=True):
        """
        Sets the type of mapping for the plot glyph sizes.

        Parameters
        ----------
        gsmap: GlyphSizeMap or str
            Either the Enum GlyphSizeMap or a string with the mapping type.
        update_chart: boolean
            Switch to indicate if the plot should be updated. Default value
            is True.
        """
        self._glyph_size_map = (
            gsmap if isinstance(gsmap, GlyphSizeMap) else GlyphSizeMap(gsmap)
        )
        if update_chart:
            self.update_chart(plot_glyph=True)

    def set_curve_tooltip(self, curve_idx):
        """
        Draws the tooltip over the selected curve

        Parameters
        ----------
        curve_idx: int
            The index of the curve to draw the tooltip on.
        """
        # Restoring the points/lines sizes.
        # if self.plot_points:
        #    for art in self.axes.collections:
        #        if isinstance(art, LineCollection):
        #            art.set_linewidths(3)
        #        else:
        #            art.set_sizes([self.point_plot_params['s']])
        # if self.plot_lines:
        #    for art in self.axes.lines:
        #        art.set_linewidth(self.line_plot_params['linewidth'])

        # Hiding any hidden curves previously highlighted by this call.
        if self.plot_points:
            for i, p in self._point_artists.items():
                if i in self._hidden_curves:
                    p.set_visible(False)
        if self.plot_lines:
            for i, p in self._line_artists.items():
                if i in self._hidden_curves:
                    p.set_visible(False)
        if self.plot_brush_stroke:
            for i, p in self._brush_stroke_artists.items():
                if i in self._hidden_curves:
                    p.set_visible(False)

        # If the curve is a reference, we set their artists to visible,
        # even if they were hidden before.
        if curve_idx in self._reference_idx and curve_idx in self._hidden_curves:
            if self.plot_points:
                self._point_artists[curve_idx].set_visible(True)
            if self.plot_lines:
                self._line_artists[curve_idx].set_visible(True)
            if self.plot_brush_stroke:
                self._brush_stroke_artists[curve_idx].set_visible(True)

        if not curve_idx or curve_idx not in range(self.curves.shape[0]):
            self.draw()
            return

        if self.plot_points:
            # art = self.axes.collections[curve_idx]
            # art.set_sizes([self.point_plot_params['s'] * 3])
            pass
        if self.plot_lines:
            art = self.axes.lines[curve_idx]
            art.set_linewidth(self.line_plot_params["linewidth"] * 2)
        self.draw()

    def reset_plot(self):
        """
        Resets the plot state, undoing all zoom and pan actions.
        """
        self.update_chart(data_changed=True)

    # Callback methods
    def cb_mouse_pick(self, event):
        """
        Callback to process a picking event.

        Parameters
        ----------
        event: matplotlib.backend_bases.PickEvent
            Data about the picking event.
        """
        if event.mouseevent.button != 1:
            return True
        N = len(event.ind)
        if not N:
            return True

        # Selecting the artist type (if we are plotting points, we iterate
        # through the pathcollections, else, we iterate through the lines).
        artists = None
        if self.plot_points:
            artists = self.axes.collections
        elif self.plot_lines:
            artists = self.axes.lines

        # Searching for the series to highlight and notifying the parent
        # object.
        for i, a in enumerate(artists):
            # If the series is set as reference data, we skip it.
            if i in self._reference_idx:
                continue

            if a == event.artist:
                h = self.is_data_instance_highlighted(i)
                self.highlight_data(i, h)
                self.notify_parent()

        self.update_chart(selected_data=True)
        return True

    def cb_mouse_motion(self, event):
        """
        Callback to process a mouse movement event.

        If a point is hit by the mouse cursor, we query its index and notify
        the parent object. The parent object must then notify the fanchart (or
        any plot with a time based X axis) in order to highlight the time.

        Parameters
        ----------
        event: matplotlib.backend_bases.MouseEvent
            Data about the event.
        """
        # Restoring the original parameters.
        if self.plot_points:
            for art in self.axes.collections:
                if isinstance(art, LineCollection):
                    lwidths = np.linspace(
                        self._brush_size_lims[0],
                        self._brush_size_lims[1],
                        self.curves.shape[1],
                    )
                    art.set_linewidths(lwidths)
                else:
                    art.set_sizes([self.point_plot_params["s"]])
        if self.plot_lines:
            for art in self.axes.lines:
                art.set_linewidth(self.line_plot_params["linewidth"])

        # If the event is outside the axes, we call the timestep callback to
        # notify anyone.
        if event.xdata is None or event.ydata is None:
            if self._cb_notify_timestep:
                self._cb_notify_timestep(self.name, None)
            return False

        if not self._tree:
            return False

        _, idx = self._tree.query(np.array([event.xdata, event.ydata]))

        # Since we need only the time-step, we just take the remainder of the
        # index / number_of_curves, which gives us the timestep selected.
        pidx = math.ceil(idx / self.curves.shape[1]) - 1
        timestep = idx % self.curves.shape[1]

        art = None
        if self.plot_lines:
            art = self.axes.lines
        elif self.plot_points:
            art = self.axes.collections
        if not art:
            return True

        contains, _ = art[pidx].contains(event)

        if contains:
            if self.curvenames:
                if self.plot_points:
                    art = self.axes.collections[pidx]
                    if isinstance(art, LineCollection):
                        lwidths = np.linspace(
                            self._brush_size_lims[0],
                            3 * self._brush_size_lims[1],
                            self.curves.shape[1],
                        )
                        art.set_linewidths(lwidths)
                    else:
                        art.set_sizes([self.point_plot_params["s"] * 3])
                if self.plot_lines:
                    art = self.axes.lines[pidx]
                    art.set_linewidth(self.line_plot_params["linewidth"] * 2)

                palette = QPalette()
                palette.setColor(QPalette.ToolTipBase, QColor(252, 243, 207))
                palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
                QToolTip.setPalette(palette)
                QToolTip.setFont(QFont("Arial", 14, QFont.Bold))
                pos = self.mapToGlobal(QPoint(event.x, self.height() - event.y))
                QToolTip.showText(pos, "{}".format(self.curvenames[pidx]))

                if self._cb_notify_tooltip:
                    self._cb_notify_tooltip(self.name, pidx)

            if self._cb_notify_timestep:
                self._cb_notify_timestep(self.name, timestep + 1)
        else:
            if self._cb_notify_tooltip:
                self._cb_notify_tooltip(self.name, None)
            if self._cb_notify_timestep:
                self._cb_notify_timestep(self.name, None)
            QToolTip.hideText()

        self.draw()

    def cb_axes_leave(self, event):
        """
        Callback to process an event generated when the mouse leaves the plot
        axes.

        This event calls "cb_notify_timestep" callback in order to remove
        any highlighted timesteps in other views. Besides this, it removes the
        tooltip, if any and calls the "cb_notify_tooltip" callback, if set, to
        remove the tooltips from other views.

        Parameters
        ----------
        event: matplotlib.backend_bases.LocationEvent
            Data about the event.
        """
        if self._cb_notify_timestep:
            self._cb_notify_timestep(self.name, None)

        if self._cb_notify_tooltip:
            self._cb_notify_tooltip(self.name, None)

        self.draw()

    def update_chart(self, **kwargs):
        """
        Selectively updates the chart based on the given arguments.

        kwargs: Other arguments.
        'selected_data' - Triggers the update of the highlighted data.
        'data_changed' - Triggers a redraw of the data. Usually called when
            the data is changed. Also calls the update_chart method with the
            'selected_data' parameter.
        'plot_glyph' - Identical to the 'data_changed' parameter.
        """
        if self.curves is None or self.control_points is None:
            return

        if "selected_data" in kwargs:
            bg_alpha = 0.05
            if len(self.highlighted_data) == 0:
                bg_alpha = 1.0

            if self.plot_points:
                for i, col in enumerate(self.axes.collections):
                    if i in self._reference_idx:
                        continue
                    col.set_alpha(bg_alpha)
                for i in self.highlighted_data:
                    self.axes.collections[i].set_alpha(1.0)

            if self.plot_lines:
                for i, line in enumerate(self.axes.lines):
                    if i in self._reference_idx:
                        continue
                    line.set_alpha(bg_alpha)
                for i in self.highlighted_data:
                    self.axes.lines[i].set_alpha(1.0)

        if "data_changed" in kwargs or "plot_glyph" in kwargs:
            nref_idx = set(range(self.curves.shape[0])) - self._reference_idx
            self.axes.cla()
            self.axes.set_title(self.plot_title)
            self.axes.set_xlabel("Axis 1")
            self.axes.set_ylabel("Axis 2")
            self._point_artists = {}
            self._line_artists = {}
            self._brush_stroke_artists = {}

            colormap = cm.get_cmap(name=self.colormap_name, lut=len(self.curves))
            for i in nref_idx:
                # Handling the saturation mapping.
                sat = []
                if self.saturation_map_type == SaturationMapType.CONSTANT:
                    sat = [1.0] * (self.curves.shape[1] - 1)
                elif self.saturation_map_type == SaturationMapType.LINEAR_INC:
                    sat = np.linspace(0.01, 0.95, self.curves.shape[1])
                elif self.saturation_map_type == SaturationMapType.LINEAR_DEC:
                    sat = np.linspace(0.95, 0.01, self.curves.shape[1])
                elif self.saturation_map_type == SaturationMapType.VARIANCE:
                    sat = 1.0 - self._ts_variance
                else:
                    raise ValueError("Invalid saturation map type defined.")

                r, g, b, a = colormap(i)
                h, s, v = rgb_to_hsv((r, g, b))
                hsv_color = [(h, s * s1, v) for s1 in sat]
                rgba_color = hsv_to_rgb(hsv_color)

                # self._plot_params['color'] = colormap(i)
                self._plot_params["color"] = rgba_color
                self._plot_path_projection(
                    self.projected_curves[i], i, **self._plot_params
                )

            for i in self._reference_idx:
                self._plot_path_projection(
                    self.projected_curves[i], i, **self._reference_parameters[i]
                )

            for i in self._hidden_curves:
                if self._point_artists and self._point_artists[i]:
                    self._point_artists[i].set_visible(False)
                if self._line_artists and self._line_artists[i]:
                    self._line_artists[i].set_visible(False)
                if (
                    self._brush_stroke_artists
                    and i < len(self._brush_stroke_artists)
                    and self._brush_stroke_artists[i]
                ):
                    self._brush_stroke_artists[i].set_visible(False)

            self.axes.set_xticklabels([])
            self.axes.set_yticklabels([])
            # self.update_chart(selected_data=True)

        if "apply_transforms" in kwargs:
            self._zphandler.apply_transforms()

        self.draw()

    # Private methods
    def _connect_cb(self):
        """
        Connects the callbacks to the matplotlib canvas.
        """
        fig = self.figure
        self._cb_pick_id = fig.canvas.mpl_connect("pick_event", self.cb_mouse_pick)
        self._cb_mouse_move_id = fig.canvas.mpl_connect(
            "motion_notify_event", self.cb_mouse_motion
        )
        # self._cb_axes_leave_id = fig.canvas.mpl_connect(
        #    'axes_leave_event', self.cb_axes_leave)
        # self._cb_fig_leave_id = fig.canvas.mpl_connect(
        #    'figure_leave_event', self.cb_axes_leave)

    def _disconnect_cb(self):
        """
        Detaches the callbacks from the matplotlib canvas.
        """
        fig = self.figure
        if self._cb_pick_id:
            fig.canvas.mpl_disconnect(self._cb_pick_id)
            self._cb_pick_id = None
        if self._cb_mouse_move_id:
            fig.canvas.mpl_disconnect(self._cb_mouse_move_id)
            self._cb_mouse_move_id = None
        if self._cb_axes_leave_id:
            fig.canvas.mpl_disconnect(self._cb_axes_leave_id)
            self._cb_axes_leave_id = None
        if self._cb_fig_leave_id:
            fig.canvas.mpl_disconnect(self._cb_fig_leave_id)
            self._cb_fig_leave_id = None

    def _plot_path_projection(self, path_coords, curve_idx, **kwargs):
        """
        Helper method to plot a single projected curve.

        Parameters
        ----------
        path_coords: numpy.array
            A NxD array with the projected coordinates. N is the number of
            points and D is the number of dimensions.
        curve_idx: int
            The curve index in the original matrix.
        """
        if path_coords is None or len(path_coords) == 0:
            return

        tr = range(self.start_time, self.end_time - 1)
        x = path_coords[tr, 0]
        y = path_coords[tr, 1]

        # Handling the glyph size mapping.
        # TODO

        # Plotting the selected glyph types.
        if self.plot_points:
            # Handling colors with the new alpha values.
            self._point_artists[curve_idx] = self.axes.scatter(
                x, y, **{**self.point_plot_params, **kwargs}
            )
        if self.plot_lines:
            p = np.array([x, y]).T.reshape(-1, 1, 2)
            segs = np.concatenate([p[:-1], p[1:]], axis=1)
            # print("-------------------------------------------------")
            if "marker" in kwargs:
                del kwargs["marker"]
            # print(self.line_plot_params, kwargs.keys())
            lcol = LineCollection(segs, **{**self.line_plot_params, **kwargs})

            self.axes.add_collection(lcol)
            self._line_artists[curve_idx] = lcol

            # self._line_artists[curve_idx] = self.axes.plot(
            #    x, y, **{**self.line_plot_params, **kwargs})[0]
        if self.plot_brush_stroke:
            if curve_idx in self._reference_idx:
                return
            N_POINTS = 50
            interp_x = []
            interp_y = []
            # print(kwargs['color'].shape)
            # hsv = rgb_to_hsv(kwargs['color'])
            # sat = hsv[:, 1]

            for i in range(1, len(x)):
                f = interp1d([x[i - 1], x[i]], [y[i - 1], y[i]])
                xnew = np.linspace(x[i - 1], x[i], N_POINTS)
                ynew = f(xnew)

                interp_x.extend(xnew)
                interp_y.extend(ynew)

                # sp = interp1d([x[i-1], x[i]],
                #               [sat[i-1], sat[i]])
                # saturation_new = sp(xnew)

            if self.glyph_size_type == GlyphSizeMap.LINEAR_INC:
                glyph_sizes = np.linspace(
                    self._brush_size_lims[0] * 2,
                    self._brush_size_lims[1],
                    len(interp_x),
                )
            elif self.glyph_size_type == GlyphSizeMap.LINEAR_DEC:
                glyph_sizes = np.linspace(
                    self._brush_size_lims[1] * 2,
                    self._brush_size_lims[0],
                    len(interp_x),
                )

            c = self.axes.scatter(interp_x, interp_y, s=glyph_sizes, **kwargs)
            self._brush_stroke_artists[curve_idx] = c

    def _update_projected_data(self):
        """
        Helper method to build the projections.
        """
        self._control_points = self._create_control_points()
        proj_points = time_lapse_lamp(self.curves, self.curves, self.control_points)

        if len(self.projected_curves) > 0:
            self._projected_curves = []
        for pidx in range(self.curves.shape[0]):
            pcoord = np.zeros(shape=(self.curves.shape[1] - 1, 2))
            for idx, ts in enumerate(proj_points):
                pcoord[idx, :] = ts[pidx, :]
            self.projected_curves.append(pcoord)

    def _build_kdtree(self):
        """
        Given the projected points, this method builds a KDTree for fast
        querying of nearest neighbors.
        """
        if len(self.projected_curves) == 0:
            self._tree = None
            return

        s = self.curves.shape
        pcoord = np.zeros(shape=(s[0] * s[1], 2))
        for idx, plist in enumerate(self.projected_curves):
            start = idx * s[1]
            end = start + s[1] - 1
            pcoord[start:end, :] = plist

        self._tree = scipy.spatial.KDTree(pcoord)

    def _create_control_points(self):
        """
        This function executes the MDS algorithm on the given set of time
        series and returns its projections.

        Returns
        -------
        out: numpy.array
            The data projected in an self.dims space. Each row corresponds to
            a single time series.
        """
        tgt_data = self.curves[:, self.start_time : self.end_time : self.step_time]
        D = scipy.spatial.distance.pdist(tgt_data, metric="euclidean")
        D = scipy.spatial.distance.squareform(D)
        mds = sklearn.manifold.MDS(
            n_components=self.dims, max_iter=500, eps=1e-9, dissimilarity="precomputed"
        )
        fit = mds.fit(D)
        proj_points = fit.embedding_

        return proj_points


def main():
    from PyQt5.QtWidgets import (
        QApplication,
        QMainWindow,
        QWidget,
        QPushButton,
        QVBoxLayout,
        QHBoxLayout,
        QComboBox,
    )
    import sys

    """
    Simple feature test function for the TimeLapseLAMPChart class.
    """

    class MyTestWidget(QMainWindow):
        """
        Qt derived class to embed our plot.
        """

        def __init__(self):
            super().__init__()
            self.left = 0
            self.top = 0
            self.title = "Dummy Qt widget"
            self.width = 600
            self.height = 400
            self.buildUI()
            self.update_data()

        def buildUI(self):
            self.setWindowTitle(self.title)
            self.setGeometry(self.left, self.top, self.width, self.height)

            self.lamp = TimeLapseChart(parent=self, canvas_name="lamp1")
            self.lamp.set_colormap("gist_stern", update_chart=False)
            self.lamp.set_plot_title("Time Lapse projection plot")

            points_button = QPushButton("Plot points", self)
            points_button.clicked.connect(self.switch_point_state)
            lines_button = QPushButton("Plot lines", self)
            lines_button.clicked.connect(self.switch_line_state)
            brush_stroke_button = QPushButton("Plot brush stroke", self)
            brush_stroke_button.clicked.connect(self.switch_brush_stroke_state)
            p10_button = QPushButton("Enable P10", self)
            p10_button.clicked.connect(self.enableP10)
            p50_button = QPushButton("Enable P50", self)
            p50_button.clicked.connect(self.enableP50)
            p90_button = QPushButton("Enable P90", self)
            p90_button.clicked.connect(self.enableP90)
            rand_data = QPushButton("Generate new data", self)
            rand_data.clicked.connect(self.update_data)
            reset_button = QPushButton("Reset view", self)
            reset_button.clicked.connect(self.reset_plot)

            saturation_map_combo = QComboBox(self)
            saturation_map_combo.currentIndexChanged[str].connect(
                self.set_saturation_map_type
            )
            for k in ["constant", "linear_increasing", "linear_decreasing", "variance"]:
                saturation_map_combo.addItem(k)

            glyph_size_combo = QComboBox(self)
            glyph_size_combo.currentIndexChanged.connect(self.set_glyph_size_type)
            for k in ["constant", "linear_increasing", "linear_decreasing", "variance"]:
                glyph_size_combo.addItem(k)

            self.main_widget = QWidget(self)
            l = QHBoxLayout(self.main_widget)
            l.addWidget(self.lamp)

            button_layout = QVBoxLayout(self.main_widget)
            button_layout.addWidget(points_button)
            button_layout.addWidget(lines_button)
            button_layout.addWidget(brush_stroke_button)
            button_layout.addWidget(p90_button)
            button_layout.addWidget(p50_button)
            button_layout.addWidget(p10_button)
            button_layout.addWidget(saturation_map_combo)
            button_layout.addWidget(glyph_size_combo)
            button_layout.addWidget(rand_data)
            button_layout.addWidget(reset_button)

            l.addLayout(button_layout)

            self.setFocus()
            self.setCentralWidget(self.main_widget)

        def switch_line_state(self):
            self.lamp.set_plot_lines(not self.lamp.plot_lines)

        def switch_point_state(self):
            self.lamp.set_plot_points(not self.lamp.plot_points)

        def switch_brush_stroke_state(self):
            self.lamp.set_plot_brush_stroke(not self.lamp.plot_brush_stroke)

        def set_saturation_map_type(self, text):
            # (text)
            self.lamp.set_saturation_map_type(text)

        def set_glyph_size_type(self, text):
            print(text)

        def update_data(self):
            curves = np.random.normal(size=(30, 50))
            self.curves = np.vstack(
                (curves, np.percentile(curves, q=[10, 50, 90], axis=0))
            )

            self.lamp.set_curves(self.curves)
            self.lamp.set_reference_curve(
                self.curves.shape[0] - 3, True, False, color="r", marker="v"
            )
            self.lamp.set_reference_curve(
                self.curves.shape[0] - 2, True, False, color="b", marker="<"
            )
            self.lamp.set_reference_curve(
                self.curves.shape[0] - 1, True, False, color="g", marker="^"
            )
            self.lamp.update_chart(data_changed=True)

            curvenames = ["Curve-" + str(i + 1) for i in range(curves.shape[0])]
            curvenames.extend(["P10", "P50", "P90"])
            self.lamp.set_curvenames(curvenames)

        def enableP10(self):
            c = self.lamp.curves.shape[0]
            draw = self.lamp.is_drawing_curve(c - 3)
            self.lamp.set_draw_curve(c - 3, not draw)

        def enableP50(self):
            c = self.lamp.curves.shape[0]
            draw = self.lamp.is_drawing_curve(c - 2)
            self.lamp.set_draw_curve(c - 2, not draw)

        def enableP90(self):
            c = self.lamp.curves.shape[0]
            draw = self.lamp.is_drawing_curve(c - 1)
            self.lamp.set_draw_curve(c - 1, not draw)

        def set_brushed_data(self, child_name, obj_ids):
            print("widget {} brushed some objects.".format(child_name))
            print("Objects:\n\t", obj_ids)

        def reset_plot(self):
            self.lamp.reset_plot()

    app = QApplication(sys.argv)
    ex = MyTestWidget()
    ex.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
