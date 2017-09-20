#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Module to handle the Instance/Distance chart.
"""

import numpy as np
import scipy.spatial.distance
from matplotlib import cm
from matplotlib.backends.backend_qt5agg import \
    FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtCore import QPoint
from PyQt5.QtWidgets import QSizePolicy, QToolTip
from PyQt5.QtGui import QFont, QPalette, QColor

from brushableplot import BrushableCanvas
from zoomhandler import ZoomHandler
from panhandler import PanHandler


class DistanceChart(FigureCanvas, BrushableCanvas):
    """
    This class builds an Instance/Distance plot.

    Given a set of data instances (or scenarios) and a baseline instance, this
    class calculates the distance between the inputs and the baseline using the
    chosen metric and plots them in a scatterplot. The plot's X axis is the
    instance ID and the Y axis represents the distance from the baseline.

    Other data instances may be set as 'references', meaning that they can be
    plotted with different parameters (other markers, colors and sizes) and
    they cannot be selected by the brushing & linking technique. These
    reference curves will not be changed when another instance is selected
    (i.e. their opacity will remain intact).

    This class supports marking the desired curves using the brushing & linking
    technique.
    """

    def __init__(self, canvas_name, parent, width=5, height=5, dpi=100,
                 **kwargs):
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
        kwargs:
            Other keyword arguments.
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

        self._zoomhandler = ZoomHandler(self.axes)
        self._panhandler = PanHandler(self.axes, 3)

        # Data setup
        self._curves = None
        self._points = None
        self._reference_idx = set()
        self._baseline_idx = None
        self._distance_metric = 'euclidean'
        self._curvenames = None
        self._point_artists = None

        # Plot style setup
        self._plot_title = self.base_plot_name()
        self._log_scale = False
        self._reference_parameters = {}
        self._cmap_name = 'rainbow'
        self._points_colors = {}
        self._hthresh_line = None
        self._group_selection = False
        self._yidx_points = None
        self._plot_params = kwargs
        if 'picker' not in self._plot_params:
            self._plot_params['picker'] = 3
        if 's' not in self._plot_params:
            self._plot_params['s'] = 40

        # Callback IDs
        self._cb_mouse_move_id = None
        self._cb_mouse_button_id = None
        self._cb_scrollwheel_id = None
        self._cb_axes_leave_id = None
        self._cb_fig_leave_id = None

        # Callbacks
        self._cb_notify_tooltip = None

        self._connect_cb()

    def __del__(self):
        self._disconnect_cb()
        self._axes = None
        self._distance_metric = None
        self._curves = None
        self._points_colors.clear()
        self._reference_idx.clear()
        self._reference_parameters.clear()
        self._baseline_idx = None
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
        Returns the instance data as a numpy.matrix.
        """
        return self._curves

    @property
    def distance_metric(self):
        """
        Returns the distance metric used to build the plot.
        """
        return self._distance_metric

    @property
    def log_scale(self):
        """
        Returns if the plot is using logarithmic scale in the Y axis.
        """
        return self._log_scale

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
        return 'Distance Chart'

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
    def group_selection_enabled(self):
        """
        Returns the state of the group selection option.
        """
        return self._group_selection

    @property
    def curvenames(self):
        """
        Returns the names of the data-points given by the user.
        """
        return self._curvenames

    def set_group_selection_enabled(self, enable):
        """
        Enables or disables the group selection option.

        Parameters
        ----------
        enable: boolean
            True to enable group selection, False otherwise.
        """
        self._group_selection = enable

    def set_distance_metric(self, metric, update_chart=True):
        """
        Sets the distance_metric to use when building the plot.

        Arguments
        ---------
        metric: str
            The distance metric to use. Must be a metric supported by
            scipy.spatial.distance.pdist.
        update_chart: boolean
            Switch to indicate if the plot should be updated. Default value is
            True
        """
        self._distance_metric = metric
        if update_chart:
            self.update_chart(data_changed=True)

    def set_log_scale(self, log_scale, update_chart=True):
        """
        Sets if the Y axis should be in logarithmic scale.

        Arguments
        ---------
        log_scale: boolean
            If True, the Y axis will be converted to log scale and plotted.
        update_chart: boolean
            Switch to indicate if the chart should be updated immediatly or
            not. Default value is True.
        """
        self._log_scale = log_scale

        # Must reset the zoom, since the axes limits are changed.
        self._zoomhandler.reset_zoom()

        if update_chart:
            self.update_chart(data_changed=True)

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
        Sets the input curves for this plot.

        Arguments
        ---------
        curves: numpy.array
            A matrix containing the input data arranged by row.
        update_chart: boolean
            Switch to indicate if the plot should be updated with the new data.
            Default value is True.
        """
        self._curves = curves

        # Reseting the reference and baseline data
        self._reference_idx.clear()
        self._reference_parameters.clear()
        self._baseline_idx = None
        self._hthresh_line = None

        # Reseting the highlighted data
        self.highlight_data(self._highlighted_data,
                            erase=True, update_chart=False)

        if update_chart:
            self.update_chart(data_changed=True)
            self.reset_plot()

    def set_reference_curve(self, curve_idx, is_ref, update_chart=True,
                            **kwargs):
        """
        Marks a curve (point) as reference if 'is_ref' is True. Restores the
        curve status as 'common' if 'is_ref' is False. This disengages the
        highlight of the selected curve and forbids it from happening.

        Arguments
        ---------
        curve_idx: int
            The index of the selected curve.
        is_ref: boolean
            Switch to indicate if the index is being marked as reference (True)
            or marked as a common curve (False).
        update_chart:boolean
            Switch to indicate if the plot should be updated with the new data.
            Default value is True.
        kwargs: Other graphical parameters
            Graphical parameters for the curve marked as reference (color,
            marker, size, and others accepted by axes.scatter).
        """
        if curve_idx not in range(self.curves.shape[0]):
            raise ValueError('Index out of range')
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

    def set_baseline_curve(self, curve_idx, update_chart=True):
        """
        Sets the baseline curve for this plot. The points to be plotted will be
        the distances between all other curves and the baseline.

        Arguments
        ---------
        curve_idx: int
            The index of the baseline curve in the curves matrix.
        update_chart: boolean
            Switch to indicate if the plot should be updated with the new data.
            Default value is True.
        """
        if curve_idx not in range(self.curves.shape[0]):
            raise ValueError('Index out of range')
        self._baseline_idx = curve_idx
        if update_chart:
            self._hthresh_line = None
            self.update_chart(data_changed=True)

    def set_curve_tooltip(self, curve_idx):
        """
        Draws the tooltip over the selected curve point. The tooltip is
        dislocated by a 1% of the size of the plot in the X and Y axis.

        Parameters
        ----------
        curve_idx: int
            The index of the curve to draw the tooltip on.
        """
        # Restoring the points' sizes.
        if self._point_artists:
            for art in self._point_artists:
                if art:
                    art.set_sizes([self._plot_params['s']])

        if not curve_idx or curve_idx not in range(self.curves.shape[0]):
            self.draw()
            return

        # Increasing the radius of the selected point.
        art = self._point_artists[curve_idx]
        if art:
            art.set_sizes([self._plot_params['s'] * 3])
        self.draw()

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
        update_chart: boolean
            Switch to indicate if the plot should be updated. Default value
            is True.
        """
        self._cmap_name = cmap_name
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

    def reset_plot(self):
        """
        Resets the plot state, undoing all zoom and pan actions.
        """
        self._zoomhandler.reset_zoom()
        self._panhandler.reset_pan()
        self.update_chart(data_changed=True)

    # Callback methods
    def cb_mouse_motion(self, event):
        """
        Callback to process a mouse movement event.

        If the group selection option is enabled, then any points with
        Y-coordinate less than the cursor's Y-coordinate will be marked in a
        different opacity level, but not highlighted. If the user clicks with
        the mouse, then the points will be highlighted, but this event is
        processed in another method.

        This method also processes tooltip-related events when the group
        selection is disabled. If the user hovers the mouse cursor over a data
        point, then the name associated to that point will be shown in a
        tooltip.

        Parameters
        ----------
        event: matplotlib.backend_bases.MouseEvent
            Data about the event.
        """
        # We remove the horizonal line here (if any), regardless of the mouse
        # cursor position. We also restore the points colors.
        if self._hthresh_line:
            lines = self.axes.get_lines()
            for l in lines:
                self.axes.lines.remove(l)
                del l

            self._hthresh_line = None

            for i, p in enumerate(self.axes.collections):
                if i not in self._reference_idx:
                    p.set_facecolor(self._points_colors[i])
            self.draw()

        # Restoring the points' original size.
        if self._point_artists:
            for art in self._point_artists:
                if art is None:
                    continue
                art.set_sizes([self._plot_params['s']])

        if event.xdata is None or event.ydata is None or self._points is None:
            return False
        if self.group_selection_enabled:
            # We must get only the points above the cursor.
            diff = self._points - event.ydata
            above = []
            above = [i for i in reversed(self._yidx_points) if diff[i] >= 0]

            for a in above:
                if a in self._reference_idx:
                    continue
                self.axes.collections[a].set_facecolor(cm.gray(200))

                self._hthresh_line = self.axes.axhline(y=event.ydata, c='b',
                                                       linewidth=2)
        else:
            # Testing if the cursor is over a point. If it is, we plot the
            # tooltip and notify this event by calling the registered
            # callback, if any.
            if not self.curvenames:
                return False
            else:
                hover_idx = None
                for i, art in enumerate(self._point_artists):
                    if not art:
                        continue
                    contains, _ = art.contains(event)
                    if contains:
                        art.set_sizes([self._plot_params['s'] * 3])
                        if i > len(self.curvenames):
                            return False
                        hover_idx = i
                        break

                if hover_idx is not None:
                    palette = QPalette()
                    palette.setColor(QPalette.ToolTipBase,
                                     QColor(252, 243, 207))
                    palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
                    QToolTip.setPalette(palette)
                    QToolTip.setFont(QFont('Arial', 14, QFont.Bold))
                    pos = self.mapToGlobal(
                        QPoint(event.x, self.height() - event.y))
                    QToolTip.showText(pos, '{}'.format(
                        self.curvenames[hover_idx]))
                else:
                    QToolTip.hideText()

                if self._cb_notify_tooltip:
                    self._cb_notify_tooltip(self.name, hover_idx)

        self.draw()

    def cb_mouse_button(self, event):
        """
        Callback to process a mouse button press event.
        Any points with Y-coordinate less than the cursor's Y-coordinate will
        be highlighted if the user clicks with the left mouse-button.

        Parameters
        ----------
        event: matplotlib.backend_bases.MouseEvent
            Data about the event.
        """
        if event.xdata is None or event.ydata is None or event.button is None:
            return True
        if self._points is None or len(self._points) == 0:
            return True

        # Left mouse button pressed.
        if event.button == 1:
            to_highlight = []
            # If the group selection option is enabled, we perform a group
            # selection. Else, we just check each plotted path for collisions
            # with the mouse pointer and add them to the list of paths to
            # highlight.
            if self.group_selection_enabled:
                self.highlight_data(self.highlighted_data, erase=True,
                                    update_chart=False)

                diff = self._points - event.ydata
                below = [i for i in self._yidx_points if diff[i] <= 0]

                for b in below:
                    if b in self._reference_idx:
                        continue
                    to_highlight.append(b)
            else:
                to_erase = []
                for i, pathcol in enumerate(self.axes.collections):
                    if i in self._reference_idx:
                        continue
                    contains, _ = pathcol.contains(event)
                    if contains:
                        if i in self.highlighted_data:
                            to_erase.append(i)
                        else:
                            to_highlight.append(i)

                self.highlight_data(to_erase, erase=True, update_chart=False)

            self.highlight_data(to_highlight, erase=False, update_chart=True)
            self.notify_parent()

    def cb_axes_leave(self, event):
        """
        Callback to process an event generated when the mouse leaves the plot
        axes.

        This event removes the tooltip box, calls the "cb_notify_tooltip"
        callback, if set, to remove the tooltip from other views and restores
        the points' sizes to the default value..

        Parameters
        ----------
        event: matplotlib.backend_bases.LocationEvent
            Data about the event.
        """
        if self._cb_notify_tooltip:
            self._cb_notify_tooltip(self.name, None)

        if self._point_artists:
            for art in self._point_artists:
                if art is None:
                    continue
                art.set_sizes([self._plot_params['s']])
        self.draw()

    def update_chart(self, **kwargs):
        if self.curves is None:
            return

        if 'selected_data' in kwargs:
            # If there are no selected series, we restore their alpha to 1.0
            # (totally opaque)
            bg_alpha = 0.2
            if not self.highlighted_data:
                bg_alpha = 1.0

            for i, col in enumerate(self.axes.collections):
                if i in self._reference_idx:
                    continue
                col.set_alpha(bg_alpha)

            for i in self.highlighted_data:
                self.axes.collections[i].set_alpha(1.0)

        if 'data_changed' in kwargs:
            self.axes.cla()
            self.axes.set_title(self.plot_title)
            fmt_xlab = 'Scenario ({} baseline)'
            if not self.curvenames:
                fmt_xlab = fmt_xlab.format(self._baseline_idx)
            else:
                fmt_xlab = fmt_xlab.format(
                    self._curvenames[self._baseline_idx])

            self.axes.set_xlabel(fmt_xlab)
            self.axes.set_ylabel('Distance')
            self.axes.set_xlim([0, self.curves.shape[0] + 1])
            self.axes.spines['bottom'].set_linewidth(2.5)
            self.axes.spines['bottom'].set_color(
                self._reference_parameters[self._baseline_idx]['color'])
            self._point_artists = [None] * self.curves.shape[0]

            X, P = self._build_distance_plot_data()
            if self.log_scale:
                P = np.log10(P)
                P[P == -np.inf] = 0
                P[P == np.inf] = 0
                self.axes.set_ylabel('log_10(Distance)')

            self._points = P
            # Sorting the points by Y coordinate.
            self._yidx_points = np.argsort(P)

            # Setting the plot's Y axes.
            ymin = P[self._yidx_points[1]]
            ymax = P[self._yidx_points[-1]]
            self.axes.set_ylim([0.9 * ymin, 1.1 * ymax])

            # Setting the colormap.
            colormap = cm.get_cmap(name=self.colormap_name,
                                   lut=len(self.curves))
            self._points_colors = dict((i, colormap(i))
                                       for i in range(len(self.curves)))

            # Inadequate way to plot the data, but this is needed in order to
            # create several pathcollections and enable us to differentiate
            # between them during the picking process.
            for i, x in enumerate(X):
                if i == self._baseline_idx:
                    continue
                plot_params = self._plot_params
                if i in self._reference_idx:
                    plot_params = self._reference_parameters[i]
                else:
                    plot_params['c'] = self._points_colors[i]
                self._point_artists[i] = self.axes.scatter(x=x + 1,
                                                           y=self._points[i],
                                                           **plot_params)

            self.update_chart(selected_data=True)

        if 'apply_transforms' in kwargs:
            self._zoomhandler.apply_zoom()
            self._panhandler.apply_pan()
        if 'apply_zoom' in kwargs:
            self._zoomhandler.apply_zoom()
        if 'apply_pan' in kwargs:
            self._panhandler.apply_pan()

        self.draw()

    # Private methods
    def _connect_cb(self):
        """
        Connects the callbacks to the matplotlib canvas.
        """
        fig = self.figure
        self._cb_mouse_move_id = fig.canvas.mpl_connect(
            'motion_notify_event', self.cb_mouse_motion)
        self._cb_mouse_button_id = fig.canvas.mpl_connect(
            'button_press_event', self.cb_mouse_button)
        self._cb_scrollwheel_id = fig.canvas.mpl_connect(
            'scroll_event', self._zoomhandler)
        self._cb_axes_leave_id = fig.canvas.mpl_connect(
            'axes_leave_event', self.cb_axes_leave)
        self._cb_fig_leave_id = fig.canvas.mpl_connect(
            'figure_leave_event', self.cb_axes_leave)

    def _disconnect_cb(self):
        """
        Detaches the callbacks from the matplotlib canvas.
        """
        fig = self.figure
        if self._cb_mouse_move_id:
            fig.canvas.mpl_disconnect(self._cb_mouse_move_id)
            self._cb_mouse_move_id = None
        if self._cb_mouse_button_id:
            fig.canvas.mpl_disconnect(self._cb_mouse_button_id)
            self._cb_mouse_button_id = None
        if self._cb_scrollwheel_id:
            fig.canvas.mpl_disconnect(self._cb_scrollwheel_id)
            self._cb_scrollwheel_id = None
        if self._cb_axes_leave_id:
            fig.canvas.mpl_disconnect(self._cb_axes_leave_id)
            self._cb_axes_leave_id = None
        if self._cb_fig_leave_id:
            fig.canvas.mpl_disconnect(self._cb_fig_leave_id)
            self._cb_fig_leave_id = None

    def _build_distance_plot_data(self):
        """
        Builds the Y axis data for the distance plot.

        Returns
        -------
        out: tuple of numpy.array
            The X and Y axis values of the points to plot. The Y values are the
            distances between the input and baseline data.

            The baseline is not included in the results.
        """
        if self.curves is None:
            raise AttributeError(
                'No input data provided. Call \'set_curves\' first.')
        if self._baseline_idx is None:
            raise AttributeError(
                'No reference data provided. Call \'set_baseline_curve\' first.')
        D = scipy.spatial.distance.pdist(
            self.curves, metric=self.distance_metric)
        Y = scipy.spatial.distance.squareform(D)
        Y = Y[self._baseline_idx, :]
        X = range(self.curves.shape[0])
        return (X, Y)


def main():
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget,
                                 QPushButton, QVBoxLayout, QHBoxLayout, QFormLayout, QSlider,
                                 QMessageBox, QCheckBox, QLabel)
    from PyQt5 import QtCore
    from PyQt5.QtCore import Qt
    import sys

    """
    Simple feature test function for the DistanceChart class.
    """
    class MyTestWidget(QMainWindow):
        """
        Qt derived class to embed our plot.
        """

        def __init__(self):
            super().__init__()
            self.left = 0
            self.top = 0
            self.title = 'Dummy Qt widget'
            self.width = 600
            self.height = 400
            self._sld_timestep_start = None
            self._sld_timestep_end = None
            self._timerange = ()

            self.setFocusPolicy(QtCore.Qt.WheelFocus)
            self.buildUI()
            self.update_data()

        @property
        def max_timerange(self):
            return (0, 50)

        @property
        def timerange(self):
            return self._timerange

        def buildUI(self):
            self.setWindowTitle(self.title)
            self.setGeometry(self.left, self.top, self.width, self.height)

            self.dist_chart = DistanceChart(parent=self,
                                            canvas_name='dist1',
                                            s=40)

            eucl_button = QPushButton('Euclidean metric', self)
            eucl_button.clicked.connect(self.set_metric_euclidean)
            manh_button = QPushButton('Manhattan metric', self)
            manh_button.clicked.connect(self.set_metric_manhattan)
            logscale_button = QPushButton('Log scale Y axis', self)
            logscale_button.clicked.connect(self.set_log_scale)
            p10_baseline_button = QPushButton('Set P10 as baseline', self)
            p10_baseline_button.clicked.connect(self.set_baseline_p10)
            p50_baseline_button = QPushButton('Set P50 as baseline', self)
            p50_baseline_button.clicked.connect(self.set_baseline_p50)
            p90_baseline_button = QPushButton('Set P90 as baseline', self)
            p90_baseline_button.clicked.connect(self.set_baseline_p90)
            rand_data = QPushButton('Generate new data', self)
            rand_data.clicked.connect(self.update_data)
            group_sel = QCheckBox('Group selection', self)
            group_sel.setChecked(self.dist_chart.group_selection_enabled)
            group_sel.stateChanged.connect(self.set_group_selection)
            reset_button = QPushButton('Reset view', self)
            reset_button.clicked.connect(self.reset_plot)

            lbl_start_ts = QLabel('Start time', self)
            lbl_end_ts = QLabel('End time', self)

            self._sld_timestep_start = QSlider(Qt.Horizontal, self)
            self._sld_timestep_start.setTickPosition(QSlider.TicksBothSides)
            self._sld_timestep_start.setMinimum(0)
            self._sld_timestep_start.setSingleStep(1)
            self._sld_timestep_start.setPageStep(5)
            self._sld_timestep_start.valueChanged.connect(
                self.set_start_timestep)

            self._sld_timestep_end = QSlider(Qt.Horizontal, self)
            self._sld_timestep_end.setMinimum(0)
            self._sld_timestep_end.setTickPosition(QSlider.TicksBothSides)
            self._sld_timestep_end.setSingleStep(1)
            self._sld_timestep_end.setPageStep(5)
            self._sld_timestep_end.valueChanged.connect(self.set_end_timestep)

            self.main_widget = QWidget(self)
            l = QHBoxLayout(self.main_widget)
            l.addWidget(self.dist_chart)

            slider_layout = QFormLayout(self.main_widget)
            slider_layout.addRow(lbl_start_ts, self._sld_timestep_start)
            slider_layout.addRow(lbl_end_ts, self._sld_timestep_end)

            button_layout = QVBoxLayout(self.main_widget)
            button_layout.addWidget(eucl_button)
            button_layout.addWidget(manh_button)
            button_layout.addWidget(logscale_button)
            button_layout.addWidget(p10_baseline_button)
            button_layout.addWidget(p50_baseline_button)
            button_layout.addWidget(p90_baseline_button)
            button_layout.addWidget(rand_data)
            button_layout.addWidget(group_sel)
            button_layout.addWidget(reset_button)
            button_layout.addLayout(slider_layout)

            l.addLayout(button_layout)

            self.setFocus()
            self.setCentralWidget(self.main_widget)

        def update_data(self):
            curves = np.random.normal(size=(10, self.max_timerange[1]))
            self.curves = np.vstack(
                (curves, np.percentile(curves, q=[10, 50, 90], axis=0)))
            self._timerange = self.max_timerange

            self.dist_chart.set_curves(self.curves, False)
            self.dist_chart.set_reference_curve(self.curves.shape[0] - 3, True,
                                                False, color='r', marker='v',
                                                s=50)
            self.dist_chart.set_reference_curve(self.curves.shape[0] - 2, True,
                                                False, color='b', marker='<',
                                                s=50)
            self.dist_chart.set_reference_curve(self.curves.shape[0] - 1, True,
                                                False, color='g', marker='^',
                                                s=50)
            self.dist_chart.set_baseline_curve(self.curves.shape[0] - 2, True)
            curvenames = ['Curve-' + str(i + 1)
                          for i in range(curves.shape[0])]
            curvenames.extend(['Perc10', 'Perc50', 'Perc90'])
            self.dist_chart.set_curvenames(curvenames)

            min_ts, max_ts = self.max_timerange
            self._sld_timestep_start.setMinimum(min_ts)
            self._sld_timestep_start.setMaximum(max_ts)
            self._sld_timestep_start.setValue(min_ts)

            self._sld_timestep_end.setMinimum(min_ts)
            self._sld_timestep_end.setMaximum(max_ts)
            self._sld_timestep_end.setValue(max_ts)

        def set_timestep_range(self, ts_start, ts_end):
            self._timerange = (ts_start, ts_end)
            highlighted_data = self.dist_chart.highlighted_data

            self.dist_chart.set_curves(self.curves[:, ts_start:ts_end],
                                       update_chart=False)
            self.dist_chart.set_reference_curve(self.curves.shape[0] - 3, True,
                                                False, color='r', marker='v',
                                                s=50)
            self.dist_chart.set_reference_curve(self.curves.shape[0] - 2, True,
                                                False, color='b', marker='<',
                                                s=50)
            self.dist_chart.set_reference_curve(self.curves.shape[0] - 1, True,
                                                False, color='g', marker='^',
                                                s=50)
            self.dist_chart.set_baseline_curve(self.curves.shape[0] - 2, True)

            self.dist_chart.highlight_data(highlighted_data, erase=False,
                                           update_chart=True)

        def set_metric_euclidean(self):
            self.dist_chart.set_distance_metric('euclidean')

        def set_metric_manhattan(self):
            self.dist_chart.set_distance_metric('cityblock')

        def set_metric_correlation(self):
            self.dist_chart.set_distance_metric('correlation')

        def set_log_scale(self):
            self.dist_chart.set_log_scale(not self.dist_chart.log_scale)

        def set_baseline_p10(self):
            self.dist_chart.set_baseline_curve(self.curves.shape[0] - 3, True)

        def set_baseline_p50(self):
            self.dist_chart.set_baseline_curve(self.curves.shape[0] - 2, True)

        def set_baseline_p90(self):
            self.dist_chart.set_baseline_curve(self.curves.shape[0] - 1, True)

        def set_brushed_data(self, child_name, obj_ids):
            print('widget {} brushed some objects.'.format(child_name))
            print('Objects:\n\t', obj_ids)

        def set_start_timestep(self, start_ts):
            start_min, _ = self.max_timerange
            _, end_ts = self.timerange

            if start_ts >= end_ts:
                if start_ts > start_min:
                    start_ts = end_ts - 1
                else:
                    end_ts = start_ts + 1

            self._sld_timestep_start.setValue(start_ts)
            self._sld_timestep_end.setValue(end_ts)
            self.set_timestep_range(start_ts, end_ts)

        def set_end_timestep(self, end_ts):
            _, end_max = self.max_timerange
            start_ts, _ = self.timerange

            if start_ts >= end_ts:
                if end_ts < end_max:
                    end_ts = start_ts + 1
                else:
                    start_ts = end_ts - 1

            self._sld_timestep_start.setValue(start_ts)
            self._sld_timestep_end.setValue(end_ts)
            self.set_timestep_range(start_ts, end_ts)

        def set_group_selection(self, i):
            check = True
            if i == QtCore.Qt.Unchecked:
                check = False
            self.dist_chart.set_group_selection_enabled(check)

        def popup_question_dialog(self, title, question):
            msg = QMessageBox(QMessageBox.Question, title, question,
                              QMessageBox.Yes | QMessageBox.No, self)
            answer = msg.exec()
            return answer == QMessageBox.Yes

        def reset_plot(self):
            self.dist_chart.reset_plot()

    app = QApplication(sys.argv)
    ex = MyTestWidget()
    ex.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
