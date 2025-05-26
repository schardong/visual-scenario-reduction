#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Application main window plus tests.
"""

import os
import sys

from collections import OrderedDict
from PyQt5.QtCore import QDir, Qt, QSize
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDesktopWidget,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStyleFactory,
    QVBoxLayout,
    QWidget,
    QProxyStyle,
    QStyle,
)

from fieldensemble import FieldEnsemble
from plotwidget import PlotWidget


class SpinBoxCustomStyle(QProxyStyle):
    """
    Workaround to avoid double event triggering by the QSpinBox UI items.
    """

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.SH_SpinBox_KeyPressAutoRepeatRate:
            return 10**4
        elif hint == QStyle.SH_SpinBox_ClickAutoRepeatRate:
            return 10**4
        elif hint == QStyle.SH_SpinBox_ClickAutoRepeatThreshold:
            # You can use only this condition to avoid the auto-repeat,
            # but better safe than sorry ;-)
            return 10**4
        else:
            return super().styleHint(hint, option, widget, returnData)


class MainWindow(QMainWindow):
    """
    The main window of our application.
    """

    WELL_TYPES = ["P", "I"]

    FANCHART_COLOR_OPTIONS_MAPPING = OrderedDict(
        {
            "Grayscale": "gray_r",
            "Shades of Blue": "Blues",
            "Shades of Red": "Reds",
            "Heat": "hot_r",
        }
    )

    # FANCHART_OPTIONS_ORDERING = [
    #    'Grayscale',
    #    'Shades of Blue',
    #    'Shades of Red',
    #    'Heat',
    # ]

    DATA_COLOR_OPTIONS_MAPPING = OrderedDict(
        {
            "Winter": "winter",
            "Summer": "summer",
            "Topological": "gist_earth",
            "Ocean": "ocean",
            "Gist Stern": "gist_stern",
            "Terrain": "terrain",
            "Blue to Magenta": "cool",
            "Plasma": "plasma",
            "GNUplot": "gnuplot",
            "GNUplot2": "gnuplot2",
        }
    )

    # DATA_OPTIONS_ORDERING = [
    #    'Topological',
    #    'Ocean',
    #    'Terrain',
    #    'Blue to Magenta',
    #    'Gist Stern',
    #    'Winter',
    #    'Summer',
    # ]

    TLCHART_GLYPH_SIZE_OPTIONS_MAPPING = OrderedDict(
        {
            "Linear-Increasing": "linear_increasing",
            "Linear-Decreasing": "linear_decreasing",
        }
    )

    TLCHART_SATURATION_OPTIONS_MAPPING = OrderedDict(
        {
            "Constant": "constant",
            "Linear-Increasing": "linear_increasing",
            "Linear-Decreasing": "linear_decreasing",
            "Variance": "variance",
        }
    )

    def __init__(self, width, height):
        super(MainWindow, self).__init__()
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._plt_widget = None
        self._left, self._top = 0, 0
        self._width, self._height = width, height
        self._title = "Time-series Scenario Selection"

        # Data setup
        self._ensemble = None
        self._properties = []
        self._base_data_path = ""
        self._full_data_path = ""
        self._curr_property = None
        self._curr_baseline = "P50"
        self._well_type = self.WELL_TYPES[0]

        # UI elements
        self._file_menu = None
        self._help_menu = None
        self._combo_data_colormap = None
        self._combo_property = None
        self._combo_baseline = None
        self._combo_fan_color_pallete = None
        self._chk_show_p10 = None
        self._chk_show_p50 = None
        self._chk_show_p90 = None
        self._chk_plot_brush_strokes = None
        self._combo_saturation_map = None
        self._combo_glyph_size = None
        self._chk_show_p10_lamp = None
        self._chk_show_p50_lamp = None
        self._chk_show_p90_lamp = None
        self._spin_start_ts = None
        self._spin_end_ts = None
        self._main_widget = None
        self._panel_widget = None

        self._build_ui()

    def __del__(self):
        del self._plt_widget
        del self._ensemble

    @property
    def properties(self):
        """
        Returns the time series properties available.

        Returns
        -------
        out: list
            A list with the properties.
        """
        return self._properties

    @property
    def current_property(self):
        """
        Returns the current property of the curves being shown.

        Returns
        -------
        out: str
            The current property.
        """
        return self._curr_property

    @property
    def current_baseline(self):
        """
        Returns the ID of the current baseline curve.

        Returns
        -------
        out: str
            The ID of the current baseline (p10, p50 or p90).
        """
        return self._curr_baseline

    def resizeEvent(self, event):
        """
        Processes a Qt resize event.

        Parameters
        ----------
        event: Qt
        """
        new_size = event.size()
        self._panel_widget.setMaximumSize(400, new_size.height())

    def set_current_property(self, new_prop):
        """
        Sets the current property used by the plots. Raises a ValueError
        exception if the new property is not in the list of known properties.

        Parameters
        ----------
        new_prop: str
            The new property to be used by the plots.
        """
        if new_prop not in self.properties:
            raise ValueError("New property (%s) is unknown." % new_prop)
        self._curr_property = new_prop

    def set_current_baseline(self, new_baseline):
        """
        Sets the current baseline curve for the rank and distance plots. Raises
        a ValueError exception if the baseline is unknown.

        Parameters
        ----------
        new_baseline: str
            The ID of the new baseline. Possible values are: 'p10', 'p50' and
            'p90'.
        """
        if new_baseline not in ["P10", "P50", "P90"]:
            raise ValueError("New baseline (%s) is unknown." % new_baseline)
        self._curr_baseline = new_baseline

    def fileLoadData(self):
        """
        Opens a popup file dialog and asks for the location of the data files,
        then loads them.

        TO-DO: Load initial data if the user chooses to.
        """
        data_path = QFileDialog.getExistingDirectory(
            self, "Open data directory", QDir.homePath()
        )

        if not data_path:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        self._base_data_path = data_path
        self._full_data_path = os.path.join(self._base_data_path, "ajustado")
        self._properties = os.listdir(self._full_data_path)
        cprop = self.current_property
        if not cprop or cprop not in self.properties:
            self.set_current_property(self.properties[0])

        self._ensemble = FieldEnsemble(
            well_data_path=self._full_data_path,
            prop_list=self.properties,
            well_type_path=self._base_data_path,
        )

        QApplication.restoreOverrideCursor()
        msg = QMessageBox(
            QMessageBox.Information,
            "Load data",
            "Data loaded successfully.",
            QMessageBox.Ok,
            self,
        )
        msg.exec()

        # Adding the loaded curves to the plot widget
        self.update_data(data_changed=True)

        # Adding the properties to the UI.
        self._combo_property.clear()
        for prop in self._properties:
            self._combo_property.addItem(prop)

        # Enabling the UI
        self._alg_box.setEnabled(True)
        self._global_graphical_box.setEnabled(True)
        self._timestep_box.setEnabled(True)
        self._graphics_box.setEnabled(True)
        self._tlchart_box.setEnabled(True)
        self._fanchart_box.setEnabled(True)
        self._rankchart_box.setEnabled(True)
        self._distchart_box.setEnabled(True)

    def fileQuit(self):
        """
        Method called when the application is about to quit. Any cleanups are
        performed here.
        """
        self.close()

    def helpAbout(self):
        """
        Method called whenever the 'About' option is selected. Opens a dialog
        with some information about this software.
        """
        QMessageBox.about(
            self,
            "About this software",
            "This software is a prototype time-series visualization tool that implements a series of charts in order to help on the task of selecting representative time-series. To accomplish this task, the software uses the brushing and linking technique to enable the selection of a series (or group of series) in one chart and this seleciton is reflected on the others. This tool also implements two new charts proposed by our research work, the Time-lapsed Multidimensional Projection chart and the Rank chart.\n\nThis is a prototype, meaning that there are bugs lying around and the user interface is definetly not polished. We provide no warranty whatsoever, so use this software at your own risk.",
        )

    def closeEvent(self, _):
        """
        Method called when the window is about to be closed.
        """
        self.fileQuit()

    def baseline_changed(self):
        """
        Slot method called when the baseline option is changed in the UI.
        Repasses the new value to the plots.
        """
        self._curr_baseline = self._combo_baseline.currentText()
        self.update_data(baseline_changed=True)

    def property_changed(self):
        """
        Slot method called when the property is changed in the UI. Repasses
        this new value to the plots.
        """
        self._curr_property = self._combo_property.currentText()
        self.update_data(data_changed=True)

    def clear_selected_data(self):
        """
        Slot method called when the clear data button is pressed in the UI.
        Clears the highlighted curves from all plots.
        """
        self._plt_widget.clear_selected_data()

    def set_plot_points_tlchart(self, state):
        """
        Slot method to set the plot points option in the time lapse projection
        plot.
        """
        checked = state == Qt.Checked
        self._plt_widget.set_plot_points_tlchart(checked)

        # Point and brush plots are mutually exclusive.
        if not self._chk_plot_brush_strokes.isChecked():
            if not checked and not self._chk_plot_lines.isChecked():
                self._chk_plot_lines.setChecked(True)

        if checked and self._plt_widget.get_plot_brush_strokes_tlchart():
            self._chk_plot_brush_strokes.setChecked(False)

    def set_plot_lines_tlchart(self, state):
        """
        Slot method to set the plot lines option in the time lapse projection
        plot.
        """
        checked = state == Qt.Checked
        self._plt_widget.set_plot_lines_tlchart(checked)

        if not self._chk_plot_brush_strokes.isChecked():
            if not checked and not self._chk_plot_points.isChecked():
                self._chk_plot_points.setChecked(True)

        if checked and self._plt_widget.get_plot_brush_strokes_tlchart():
            self._chk_plot_brush_strokes.setChecked(False)

    def set_plot_brush_strokes_tlchart(self, state):
        """ """
        checked = state == Qt.Checked
        self._plt_widget.set_plot_brush_strokes_tlchart(checked)

        self._combo_glyph_size.setEnabled(checked)
        if checked:
            self._chk_plot_lines.setChecked(False)
            self._chk_plot_points.setChecked(False)

    def set_ts_highlight_tlchart(self, state):
        """
        Sets wheter the timestep highlight is enabled for the projection chart.
        """
        pass
        # checked = (state == Qt.Checked)
        # self._plt_widget.set_timestep_highlight_enabled(checked)

    def set_log_scale_distchart(self, state):
        """
        Slot method to set the log-scale option in the scenario/distance plot.
        """
        checked = state == Qt.Checked
        self._plt_widget.set_log_scale_distchart(checked)

    def fan_color_pallete_changed(self):
        """
        Sets the color pallete of the fanchart.
        """
        opt = self._combo_fan_color_pallete.currentText()
        pallete = self.FANCHART_COLOR_OPTIONS_MAPPING[opt]
        self._plt_widget.set_fan_color_pallete(pallete)

    def data_colormap_changed(self):
        """
        Sets the color pallete of the data in all plots.
        """
        opt = self._combo_data_colormap.currentText()
        pallete = self.DATA_COLOR_OPTIONS_MAPPING[opt]
        self._plt_widget.set_data_color_pallete(pallete)

    def save_plots(self):
        """
        Developer only method to save the current plots to PDF images.
        """
        self._plt_widget.save_plots()

    def set_group_selection_distchart(self, state):
        """
        Sets wheter the group selection mode for the distance chart is
        activated or not.
        """
        checked = state == Qt.Checked
        self._plt_widget.set_group_selection_distchart(checked)

    def set_group_selection_rankchart(self, state):
        """
        Sets wheter the group selection mode for the bump chart is
        activated or not.
        """
        checked = state == Qt.Checked
        self._plt_widget.set_group_selection_rankchart(checked)

    def set_start_timestep(self, value):
        """
        Slot called when the start timestep is changed. When that happens, the
        new value is tested, and, if larger than the end timestep, then the
        end timestep is set as value + 1.
        """
        start_min, end_max = self._plt_widget.max_timerange
        _, end_ts = self._plt_widget.timerange

        if value >= (end_ts - 5):
            if end_ts == end_max:
                sys.stdout.write("\a")
                sys.stdout.flush()
                return

            self._spin_end_ts.valueChanged.disconnect()
            if value < end_max:
                end_ts = value + 5
                self._spin_end_ts.setValue(end_ts)
            self._spin_end_ts.valueChanged.connect(self.set_end_timestep)

        self._plt_widget.set_timestep_range(value, end_ts)

    def set_end_timestep(self, value):
        """
        Slot called when the end timestep is changed. When that happens, the
        new value is tested against the start timestep and, if smaller, then
        the start timestep is set as value - 1.
        """
        start_min, end_max = self._plt_widget.max_timerange
        start_ts, _ = self._plt_widget.timerange

        if value <= (start_ts + 5):
            if start_ts == start_min:
                sys.stdout.write("\a")
                sys.stdout.flush()
                return

            self._spin_start_ts.valueChanged.disconnect()
            if value > start_min:
                start_ts = value - 5
                self._spin_start_ts.setValue(start_ts)
            self._spin_start_ts.valueChanged.connect(self.set_start_timestep)

        self._plt_widget.set_timestep_range(start_ts, value)

    def set_saturation_map_type_tlchart(self, opt):
        """
        DOCSTRING GOES HERE
        """
        self._plt_widget.set_saturation_map_type_tlchart(
            self.TLCHART_SATURATION_OPTIONS_MAPPING[opt]
        )

    def set_glyph_size_type_tlchart(self, opt):
        self._plt_widget.set_glyph_size_type_tlchart(
            self.TLCHART_GLYPH_SIZE_OPTIONS_MAPPING[opt]
        )

    def update_data(self, **kwargs):
        """
        Gets the newly loaded data from the Time series ensemble and passes
        them to the plot widget.
        """
        if "data_changed" in kwargs:
            # Since changing the data is a lengthy operation, we change the
            # mouse cursor to indicate this to the user.
            QApplication.setOverrideCursor(Qt.WaitCursor)
            group_data = self._ensemble.get_group_data(
                well_type=self._well_type, well_prop=self.properties
            )
            self._plt_widget.set_curves(group_data[self.current_property].T[:, 132:])
            self.update_data(baseline_changed=True)
            self._plt_widget.set_property_name(
                self.current_property, update_charts=False
            )
            self._plt_widget.update_charts(data_changed=True)
            self._plt_widget.set_curvenames(sorted(self._ensemble.field_names))

            self._chk_show_p10.setChecked(self._plt_widget.fan_is_showing_p10())
            self._chk_show_p50.setChecked(self._plt_widget.fan_is_showing_p50())
            self._chk_show_p90.setChecked(self._plt_widget.fan_is_showing_p90())

            self._chk_show_p10_lamp.setChecked(self._plt_widget.lamp_is_showing_p10())
            self._chk_show_p50_lamp.setChecked(self._plt_widget.lamp_is_showing_p50())
            self._chk_show_p90_lamp.setChecked(self._plt_widget.lamp_is_showing_p90())

            start_ts, end_ts = self._plt_widget.max_timerange
            self._spin_start_ts.setMaximum(end_ts - 5)
            self._spin_start_ts.setValue(start_ts)

            self._spin_end_ts.setRange(5, end_ts)
            self._spin_end_ts.setValue(end_ts)

            QApplication.restoreOverrideCursor()
        if "baseline_changed" in kwargs:
            if not self._ensemble:
                return
            self._plt_widget.set_baseline_curve(self.current_baseline)

    # Private methods
    def _build_ui(self):
        self.setWindowTitle(self._title)
        self.setGeometry(self._left, self._top, self._width, self._height)

        self._plt_widget = PlotWidget(self)
        self._panel_widget = QWidget(self)

        self._main_widget = QWidget(self)
        lay = QHBoxLayout(self._main_widget)
        lay.setSpacing(2)
        lay.addWidget(self._plt_widget)

        # Building the graphics options panel section
        self._graphics_box = QGroupBox("Graphical Options", self._main_widget)
        self._graphics_box.setEnabled(False)

        self._global_graphical_box = self._build_global_graphical_options_box()
        self._timestep_box = self._build_timestep_options_box()
        self._tlchart_box = self._build_projection_options_box()
        self._fanchart_box = self._build_fanchart_options_box()
        self._rankchart_box = self._build_rankchart_options_box()
        self._distchart_box = self._build_distance_options_box()
        self._legend_box = self._build_percentile_legend_box()

        graphics_layout = QVBoxLayout()
        graphics_layout.setSpacing(2)
        graphics_layout.addWidget(self._global_graphical_box)
        graphics_layout.addWidget(self._timestep_box)
        graphics_layout.addWidget(self._fanchart_box)
        graphics_layout.addWidget(self._tlchart_box)
        graphics_layout.addWidget(self._rankchart_box)
        graphics_layout.addWidget(self._distchart_box)
        graphics_layout.addWidget(self._legend_box)
        self._graphics_box.setLayout(graphics_layout)

        self._alg_box = self._build_algorithm_options_box()
        self._main_panel_layout = QVBoxLayout(self._panel_widget)
        self._main_panel_layout.addWidget(self._alg_box)
        self._main_panel_layout.addWidget(self._graphics_box)
        self._main_panel_layout.addStretch()
        # lay.addLayout(self._main_panel_layout)
        self._panel_widget.setLayout(self._main_panel_layout)
        lay.addWidget(self._panel_widget)

        self._create_menus()
        self.setFocus()
        self.setCentralWidget(self._main_widget)
        self._plt_widget.set_fan_color_pallete(
            self.FANCHART_COLOR_OPTIONS_MAPPING["Grayscale"]
        )

    def _build_algorithm_options_box(self):
        """
        Creates a QGroupBox object containing the UI elements with the
        algorithm's parameters and returns that QGroupBox.

        Returns
        -------
        A QGroupBox instance containing the UI for controlling the global
        algorithm parameters.
        """
        box = QGroupBox("Algorithm Options", self)

        form_layout = QFormLayout()
        form_layout.setSpacing(1)
        form_layout.setRowWrapPolicy(QFormLayout.DontWrapRows)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
        form_layout.setFormAlignment(Qt.AlignHCenter | Qt.AlignTop)
        form_layout.setLabelAlignment(Qt.AlignRight)

        label_property = QLabel("Property:", self._main_widget)
        self._combo_property = QComboBox(self._main_widget)
        self._combo_property.currentIndexChanged.connect(self.property_changed)

        label_baseline = QLabel("Baseline: ", self._main_widget)
        self._combo_baseline = QComboBox(self._main_widget)
        self._combo_baseline.addItem("P10")
        self._combo_baseline.addItem("P50")
        self._combo_baseline.addItem("P90")
        self._combo_baseline.setCurrentIndex(1)
        self._combo_baseline.currentIndexChanged.connect(self.baseline_changed)

        form_layout.addRow(label_property, self._combo_property)
        form_layout.addRow(label_baseline, self._combo_baseline)

        clear_selected_data = QPushButton("Deselect all", self._main_widget)
        clear_selected_data.clicked.connect(self.clear_selected_data)

        box_layout = QVBoxLayout()
        box_layout.setSpacing(1)
        box_layout.addLayout(form_layout)
        box_layout.addWidget(clear_selected_data)
        box.setLayout(box_layout)
        box.setEnabled(False)
        return box

    def _build_global_graphical_options_box(self):
        """
        Builds a QGroupBox with the global graphical options.

        Returns
        -------
        A QGroupBox instance containing the UI for controlling the graphical
        options common to all plots.
        """
        box = QGroupBox("Global Options", self)

        self._combo_data_colormap = QComboBox(self)
        self._combo_data_colormap.currentIndexChanged.connect(
            self.data_colormap_changed
        )
        for k in self.DATA_COLOR_OPTIONS_MAPPING:
            self._combo_data_colormap.addItem(k)

        save_plots_btn = QPushButton("Save plots to PDF", self)
        save_plots_btn.clicked.connect(self.save_plots)

        colormap_label = QLabel("Data Color Pallete:")
        colormap_layout = QFormLayout()
        colormap_layout.setSpacing(1)
        colormap_layout.addRow(colormap_label, self._combo_data_colormap)

        box_layout = QVBoxLayout()
        box_layout.setSpacing(1)
        box_layout.addLayout(colormap_layout)
        box_layout.addWidget(save_plots_btn)
        box.setLayout(box_layout)
        box.setEnabled(False)
        return box

    def _build_timestep_options_box(self):
        """
        Builds a QGroupBox with the timestep selection controls.

        Returns
        -------
        A QGroupBox with the timestep selection UI elements.
        """
        box = QGroupBox("Timestep selection", self)

        lbl_start_ts = QLabel("Start time", self._main_widget)
        lbl_end_ts = QLabel("End time", self._main_widget)

        self._spin_start_ts = QSpinBox(self._main_widget)
        self._spin_start_ts.setMaximumSize(QSize(300, 25))
        self._spin_start_ts.setKeyboardTracking(False)
        self._spin_start_ts.setValue(0)
        self._spin_start_ts.setStyle(SpinBoxCustomStyle())
        self._spin_start_ts.valueChanged.connect(self.set_start_timestep)

        self._spin_end_ts = QSpinBox(self._main_widget)
        self._spin_end_ts.setMaximumSize(QSize(300, 25))
        self._spin_end_ts.setKeyboardTracking(False)
        self._spin_end_ts.setValue(0)
        self._spin_end_ts.setStyle(SpinBoxCustomStyle())
        self._spin_end_ts.valueChanged.connect(self.set_end_timestep)

        layout_ts = QFormLayout(self._main_widget)
        layout_ts.setSpacing(1)
        layout_ts.addRow(lbl_start_ts, self._spin_start_ts)
        layout_ts.addRow(lbl_end_ts, self._spin_end_ts)
        box.setLayout(layout_ts)
        box.setEnabled(False)
        return box

    def _build_projection_options_box(self):
        """
        Creates a QGroupBox object containing the UI elements with the
        graphical parameters of the time-lapsed projection plot.

        Returns
        -------
        A QGroupBox instance containing the UI for controlling the graphical
        options for the time-lapsed projection plot.
        """
        box = QGroupBox("Time-lapsed LAMP Chart", self)

        self._chk_plot_points = QCheckBox("Show points", self._main_widget)
        self._chk_plot_points.setChecked(self._plt_widget.get_plot_points_tlchart())

        self._chk_plot_lines = QCheckBox("Show lines", self._main_widget)
        self._chk_plot_lines.setChecked(self._plt_widget.get_plot_lines_tlchart())

        self._chk_plot_brush_strokes = QCheckBox(
            "Show brush strokes", self._main_widget
        )
        self._chk_plot_brush_strokes.setChecked(
            self._plt_widget.get_plot_brush_strokes_tlchart()
        )

        self._combo_saturation_map = QComboBox(self._main_widget)
        for k in self.TLCHART_SATURATION_OPTIONS_MAPPING:
            self._combo_saturation_map.addItem(k)
        self._combo_saturation_map.currentIndexChanged[str].connect(
            self.set_saturation_map_type_tlchart
        )

        self._combo_glyph_size = QComboBox(self._main_widget)
        for k in self.TLCHART_GLYPH_SIZE_OPTIONS_MAPPING:
            self._combo_glyph_size.addItem(k)
        self._combo_glyph_size.currentIndexChanged[str].connect(
            self.set_glyph_size_type_tlchart
        )
        self._combo_glyph_size.setEnabled(
            not self._plt_widget.get_plot_brush_strokes_tlchart()
        )
        # chk_ts_highlight = QCheckBox('Timestep highlight', self._main_widget)
        # chk_ts_highlight.setChecked(self._plt_widget.get_ts_highlight_tlchart())
        # chk_ts_highlight.stateChanged.connect(self.set_ts_highlight_tlchart)

        self._chk_plot_points.stateChanged.connect(self.set_plot_points_tlchart)
        self._chk_plot_lines.stateChanged.connect(self.set_plot_lines_tlchart)
        self._chk_plot_brush_strokes.stateChanged.connect(
            self.set_plot_brush_strokes_tlchart
        )

        self._chk_show_p10_lamp = QCheckBox("Show P10", box)
        self._chk_show_p10_lamp.clicked.connect(self._plt_widget.lamp_show_p10)

        self._chk_show_p50_lamp = QCheckBox("Show P50", box)
        self._chk_show_p50_lamp.clicked.connect(self._plt_widget.lamp_show_p50)

        self._chk_show_p90_lamp = QCheckBox("Show P90", box)
        self._chk_show_p90_lamp.clicked.connect(self._plt_widget.lamp_show_p90)

        glyph_layout = QVBoxLayout()
        glyph_layout.addWidget(self._chk_plot_points)
        glyph_layout.addWidget(self._chk_plot_lines)
        glyph_layout.addWidget(self._chk_plot_brush_strokes)
        glyph_layout.addWidget(self._combo_saturation_map)
        glyph_layout.addWidget(self._combo_glyph_size)

        box_layout = QVBoxLayout()
        box_layout.setSpacing(1)
        box_layout.addLayout(glyph_layout)
        box_layout.addWidget(self._chk_show_p90_lamp)
        box_layout.addWidget(self._chk_show_p50_lamp)
        box_layout.addWidget(self._chk_show_p10_lamp)
        # box_layout.addWidget(chk_ts_highlight)
        box.setLayout(box_layout)
        box.setEnabled(False)
        return box

    def _build_distance_options_box(self):
        """
        Creates a QGroupBox object containing the UI elements with the
        graphical parameters of the scenario/distance plot.

        Returns
        -------
        A QGroupBox instance containing the UI for controlling the graphical
        options for the scenario/distance plot.
        """
        box = QGroupBox("Distance Chart", self)

        chk_log_scale = QCheckBox("Logarithmic scale", self._main_widget)
        chk_log_scale.stateChanged.connect(self.set_log_scale_distchart)
        chk_log_scale.setChecked(self._plt_widget.get_log_scale_distchart())

        chk_group_selection = QCheckBox("Group selection", self._main_widget)
        chk_group_selection.stateChanged.connect(self.set_group_selection_distchart)
        chk_group_selection.setChecked(self._plt_widget.get_group_selection_distchart())

        box_layout = QVBoxLayout()
        box_layout.setSpacing(1)
        box_layout.addWidget(chk_log_scale)
        box_layout.addWidget(chk_group_selection)
        box.setLayout(box_layout)
        box.setEnabled(False)
        return box

    def _build_fanchart_options_box(self):
        """
        Creates a QGroupBox object containing the UI elements with the
        graphical parameters of the fanchart.

        Returns
        -------
        A QGroupBox instance containing the UI for controlling the graphical
        options for the fanchart.
        """
        box = QGroupBox("Fanchart", self)

        color_label = QLabel("Color pallete: ", box)
        self._combo_fan_color_pallete = QComboBox(box)
        for k in self.FANCHART_COLOR_OPTIONS_MAPPING:
            self._combo_fan_color_pallete.addItem(k)
        self._combo_fan_color_pallete.setCurrentText(
            self._plt_widget.get_fan_color_pallete()
        )
        self._combo_fan_color_pallete.currentIndexChanged.connect(
            self.fan_color_pallete_changed
        )

        self._chk_show_p10 = QCheckBox("Show P10", box)
        self._chk_show_p10.clicked.connect(self._plt_widget.fan_show_p10)

        self._chk_show_p50 = QCheckBox("Show P50", box)
        self._chk_show_p50.clicked.connect(self._plt_widget.fan_show_p50)

        self._chk_show_p90 = QCheckBox("Show P90", box)
        self._chk_show_p90.clicked.connect(self._plt_widget.fan_show_p90)

        form_layout = QFormLayout()
        form_layout.setSpacing(1)
        form_layout.setRowWrapPolicy(QFormLayout.DontWrapRows)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
        form_layout.setFormAlignment(Qt.AlignHCenter | Qt.AlignTop)
        form_layout.setLabelAlignment(Qt.AlignRight)
        form_layout.addRow(color_label, self._combo_fan_color_pallete)

        box_layout = QVBoxLayout()
        box_layout.setSpacing(1)
        box_layout.addLayout(form_layout)
        box_layout.addWidget(self._chk_show_p90)
        box_layout.addWidget(self._chk_show_p50)
        box_layout.addWidget(self._chk_show_p10)
        box.setLayout(box_layout)
        box.setEnabled(False)
        return box

    def _build_rankchart_options_box(self):
        """
        Creates a QGroupBox object containing the UI elements with the
        graphical parameters of the rank chart.

        Returns
        -------
        A QGroupBox instance containing the UI for controlling the graphical
        options for the rank chart.
        """
        box = QGroupBox("Bump Chart", self)

        chk_group_selection = QCheckBox("Group selection", self)
        chk_group_selection.stateChanged.connect(self.set_group_selection_rankchart)
        chk_group_selection.setChecked(self._plt_widget.get_group_selection_rankchart())

        box_layout = QVBoxLayout()
        box_layout.addWidget(chk_group_selection)
        box.setLayout(box_layout)
        box.setEnabled(False)
        return box

    def _build_percentile_legend_box(self):
        """
        Creates a QGroupBox object containing the legend for common plot items,
        such as the percentile glyphs.

        Returns
        -------
        A QGroupBox instance containing the UI elements for the plot legend.
        """
        box = QGroupBox("Plot Legend", self)

        p10_glyph = QLabel(box)
        p10_glyph.setPixmap(QPixmap("img/p10.png"))
        p50_glyph = QLabel(box)
        p50_glyph.setPixmap(QPixmap("img/p50.png"))
        p90_glyph = QLabel(box)
        p90_glyph.setPixmap(QPixmap("img/p90.png"))

        p10_label = QLabel("P10", box)
        p50_label = QLabel("P50", box)
        p90_label = QLabel("P90", box)

        box_layout = QFormLayout()
        box_layout.setSpacing(1)
        box_layout.setRowWrapPolicy(QFormLayout.DontWrapRows)
        box_layout.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
        box_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        box_layout.setLabelAlignment(Qt.AlignRight)
        box_layout.addRow(p90_glyph, p90_label)
        box_layout.addRow(p50_glyph, p50_label)
        box_layout.addRow(p10_glyph, p10_label)

        box.setLayout(box_layout)
        box.setEnabled(True)
        return box

    def _create_menus(self):
        """
        Method to populate the menubar.
        """
        menubar = self.menuBar()
        self._file_menu = QMenu("File", self)
        self._file_menu.addAction("Load data...", self.fileLoadData, Qt.CTRL + Qt.Key_O)
        self._file_menu.addAction("Quit", self.fileQuit, Qt.CTRL + Qt.Key_Q)

        self._help_menu = QMenu("Help", self)
        self._help_menu.addAction("About...", self.helpAbout)

        menubar.addMenu(self._file_menu)
        menubar.addSeparator()
        menubar.addMenu(self._help_menu)


def main():
    """
    App entry point.
    """
    from matplotlib import rcParams

    rcParams.update({"figure.autolayout": True})

    QApplication.setStyle(QStyleFactory.create("Fusion"))
    app = QApplication(sys.argv)

    rect = QDesktopWidget().screenGeometry(-1)
    width = 1400
    height = 1000
    if rect.width() > 1920 and rect.height() > 1080:
        app.font().setPointSize(16)
        app.setFont(app.font())
        width, height = (1650, 1080)

    window = MainWindow(width, height)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
