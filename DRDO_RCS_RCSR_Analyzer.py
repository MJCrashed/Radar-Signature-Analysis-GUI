import sys
import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QVBoxLayout, QHBoxLayout, 
                            QPushButton, QFileDialog, QWidget, QLabel, QComboBox, QGroupBox,
                            QTableWidget, QTableWidgetItem, QProgressBar, QMessageBox, 
                            QAction, QMenuBar, QStatusBar, QDoubleSpinBox, QCheckBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon

class RCSAnalyzerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced RCS Analyzer")
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize data storage
        self.sphere_data = None
        self.measurement_data = None
        self.corrected_data = None
        self.dark_theme = False
        self.lines = {}  # To store plot lines for interactive removal
        self.plot_counter = 0  # To track multiple plots
        self.all_plots = []  # To store all plot data
        
        self.init_ui()
        self.create_menu()
        
    def init_ui(self):
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create tab widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Add tabs
        self.create_rcs_correction_tab()
        self.create_data_viewer_tab()
        
        # Add status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
    def create_menu(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        open_action = QAction('Open Measurement', self)
        open_action.triggered.connect(self.load_measurement_file)
        file_menu.addAction(open_action)
        
        export_action = QAction('Export Results', self)
        export_action.triggered.connect(self.export_results)
        file_menu.addAction(export_action)
        
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu('View')
        
        theme_action = QAction('Toggle Dark Theme', self)
        theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(theme_action)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        
        about_action = QAction('About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_rcs_correction_tab(self):
        """Create the RCS correction tab with all controls"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # File selection group
        file_group = QGroupBox("File Selection")
        file_layout = QVBoxLayout()
        
        self.sphere_label = QLabel("Sphere Reference: Not selected")
        self.measurement_label = QLabel("Measurement File: Not selected")
        
        file_layout.addWidget(self.sphere_label)
        file_layout.addWidget(QPushButton("Select Sphere Reference", clicked=self.load_sphere_file))
        file_layout.addWidget(self.measurement_label)
        file_layout.addWidget(QPushButton("Select Measurement File", clicked=self.load_measurement_file))
        
        file_group.setLayout(file_layout)
        
        # Parameters group
        param_group = QGroupBox("Correction Parameters")
        param_layout = QHBoxLayout()
        
        self.diameter_combo = QComboBox()
        self.diameter_combo.addItems(["Auto Detect", "12 inch (11.36 dB)", "8 inch (14.88 dB)"])
        
        self.manual_offset_check = QCheckBox("Manual Offset:")
        self.manual_offset_spin = QDoubleSpinBox()
        self.manual_offset_spin.setRange(-50, 50)
        self.manual_offset_spin.setValue(11.36)
        self.manual_offset_spin.setEnabled(False)
        
        self.manual_offset_check.stateChanged.connect(
            lambda: self.manual_offset_spin.setEnabled(self.manual_offset_check.isChecked())
        )
        
        param_layout.addWidget(QLabel("Sphere Size:"))
        param_layout.addWidget(self.diameter_combo)
        param_layout.addWidget(self.manual_offset_check)
        param_layout.addWidget(self.manual_offset_spin)
        param_layout.addStretch()
        
        param_group.setLayout(param_layout)
        
        # Plot area
        self.figure = Figure(figsize=(10, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.grid(True)
        
        # Connect click event for graph selection
        self.canvas.mpl_connect('pick_event', self.on_pick)
        
        # Controls
        controls_layout = QHBoxLayout()
        self.process_btn = QPushButton("Process and Plot", clicked=self.process_data)
        self.process_btn.setEnabled(False)
        self.clear_btn = QPushButton("Clear All Plots", clicked=self.clear_all_plots)
        self.clear_btn.setEnabled(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        controls_layout.addWidget(self.process_btn)
        controls_layout.addWidget(self.clear_btn)
        controls_layout.addWidget(self.progress_bar)
        controls_layout.addStretch()
        
        # Add all to tab layout
        layout.addWidget(file_group)
        layout.addWidget(param_group)
        layout.addWidget(self.canvas)
        layout.addLayout(controls_layout)
        
        self.tabs.addTab(tab, "RCS Correction")
    
    def create_data_viewer_tab(self):
        """Create tab for viewing data tables"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Frequency (GHz)", "Correction Factor", "Corrected RCS"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        layout.addWidget(self.table)
        self.tabs.addTab(tab, "Data Viewer")
    
    def load_sphere_file(self):
        """Load sphere reference file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Sphere Reference File", "", 
            "Data Files (*.csv *.txt *.dat);;All Files (*)"
        )
        
        if file_path:
            self.sphere_label.setText(f"Sphere Reference: {os.path.basename(file_path)}")
            self.sphere_data = self.load_data(file_path)
            
            # Try to auto-detect sphere size from filename
            if '12' in os.path.basename(file_path).lower():
                self.diameter_combo.setCurrentIndex(1)
            elif '8' in os.path.basename(file_path).lower():
                self.diameter_combo.setCurrentIndex(2)
            
            self.check_ready_state()
    
    def load_measurement_file(self):
        """Load measurement file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Measurement File", "", 
            "Data Files (*.csv *.txt *.dat);;All Files (*)"
        )
        
        if file_path:
            self.measurement_label.setText(f"Measurement File: {os.path.basename(file_path)}")
            self.measurement_data = self.load_data(file_path)
            self.check_ready_state()
    
    def load_data(self, file_path):
        """Load data from file with automatic separator detection"""
        try:
            with open(file_path, 'r') as f:
                first_line = f.readline()
            
            sep = ';' if ';' in first_line else r',\s*' if ',' in first_line else r'\s+'
            
            df = pd.read_csv(file_path, sep=sep, engine='python', header=None)
            if df.shape[1] >= 2:
                return df.iloc[:, :2].values  # Return only first two columns as numpy array
            else:
                QMessageBox.warning(self, "Error", "File must contain at least 2 columns")
                return None
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file:\n{str(e)}")
            return None
    
    def check_ready_state(self):
        """Enable process button when both files are loaded"""
        if self.sphere_data is not None and self.measurement_data is not None:
            self.process_btn.setEnabled(True)
            self.clear_btn.setEnabled(True)
            self.status_bar.showMessage("Ready to process")
        else:
            self.process_btn.setEnabled(False)
    
    def process_data(self):
        """Process the data and generate plots"""
        if self.sphere_data is None or self.measurement_data is None:
            return
        
        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        QApplication.processEvents()
        
        try:
            # Determine offset
            if self.manual_offset_check.isChecked():
                offset = self.manual_offset_spin.value()
            else:
                if self.diameter_combo.currentIndex() == 1:  # 12 inch
                    offset = 11.36
                elif self.diameter_combo.currentIndex() == 2:  # 8 inch
                    offset = 14.88
                else:  # Auto-detect
                    offset = 11.36 if '12' in self.sphere_label.text().lower() else 14.88
            
            self.progress_bar.setValue(20)
            
            # Check data lengths
            if len(self.sphere_data) != len(self.measurement_data):
                QMessageBox.warning(
                    self, "Data Mismatch", 
                    "Sphere and measurement data have different lengths. Results may be inaccurate."
                )
            
            self.progress_bar.setValue(40)
            
            # Process data
            freq = self.measurement_data[:, 0]
            sphere_amp = self.sphere_data[:, 1]
            meas_amp = self.measurement_data[:, 1]
            
            # Remove 1e10 from frequency values (convert GHz to Hz if needed)
            if np.all(freq > 1e9):  # If values are in Hz, convert to GHz
                freq = freq / 1e9
            
            correction_factors = -1 * (sphere_amp + offset)
            corrected_rcs = meas_amp + correction_factors
            
            # Store this plot's data
            plot_data = {
                'freq': freq,
                'correction_factors': correction_factors,
                'corrected_rcs': corrected_rcs,
                'offset': offset,
                'label': f"Measurement {self.plot_counter + 1}"
            }
            self.all_plots.append(plot_data)
            self.plot_counter += 1
            
            self.corrected_data = np.column_stack((freq, correction_factors, corrected_rcs))
            
            self.progress_bar.setValue(60)
            
            # Update table with latest data
            self.update_data_table()
            
            self.progress_bar.setValue(80)
            
            # Plot all available results
            self.plot_all_results()
            
            self.progress_bar.setValue(100)
            self.status_bar.showMessage("Processing complete")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Processing failed:\n{str(e)}")
        finally:
            QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))
    
    def update_data_table(self):
        """Update the data table with processed results"""
        if self.corrected_data is None:
            return
            
        self.table.setRowCount(len(self.corrected_data))
        
        for i, row in enumerate(self.corrected_data):
            for j, val in enumerate(row):
                item = QTableWidgetItem(f"{val:.4f}")
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, j, item)
    
    def plot_all_results(self):
        """Plot all available measurement results"""
        self.ax.clear()
        self.lines = {}  # Reset lines dictionary
        
        if not self.all_plots:
            return
            
        # Plot each measurement
        for i, plot in enumerate(self.all_plots):
            # Plot corrected RCS (with picker enabled for selection)
            line1, = self.ax.plot(plot['freq'], plot['corrected_rcs'], 
                                 label=f"{plot['label']} - Corrected RCS", 
                                 color=f"C{i}", linewidth=2, picker=5)
            line1.set_picker(5)  # 5 points tolerance
            self.lines[f"{plot['label']} - Corrected RCS"] = line1
            
            # Plot sphere reference (with picker enabled for selection)
            sphere_amp = -plot['correction_factors'] - plot['offset']
            line2, = self.ax.plot(plot['freq'], sphere_amp, ':', 
                                 label=f"{plot['label']} - Sphere Ref ({plot['offset']} dB)", 
                                 color=f"C{i}", linewidth=1.5, picker=5)
            line2.set_picker(5)
            self.lines[f"{plot['label']} - Sphere Ref"] = line2
        
        # Format plot
        self.ax.set_xlabel("Frequency (GHz)")
        self.ax.set_ylabel("RCS (dBsm)")
        self.ax.set_title("RCS Correction Results")
        
        # Ensure y-axis is negative
        y_min, y_max = self.ax.get_ylim()
        if y_max > 0:
            self.ax.set_ylim(top=0)
        if y_min > 0:
            self.ax.set_ylim(bottom=y_min-5)  # Add some padding
        
        self.ax.legend()
        self.ax.grid(True, alpha=0.3)
        
        if self.dark_theme:
            self.ax.set_facecolor('#2e2e2e')
            self.figure.patch.set_facecolor('#2e2e2e')
            self.ax.tick_params(colors='white')
            self.ax.xaxis.label.set_color('white')
            self.ax.yaxis.label.set_color('white')
            self.ax.title.set_color('white')
            for spine in self.ax.spines.values():
                spine.set_color('white')
        else:
            self.ax.set_facecolor('white')
            self.figure.patch.set_facecolor('white')
            self.ax.tick_params(colors='black')
            self.ax.xaxis.label.set_color('black')
            self.ax.yaxis.label.set_color('black')
            self.ax.title.set_color('black')
            for spine in self.ax.spines.values():
                spine.set_color('black')
        
        self.canvas.draw()
    
    def on_pick(self, event):
        """Handle graph selection for removal"""
        if not event.artist in self.lines.values():
            return
            
        # Find which line was clicked
        label = [k for k, v in self.lines.items() if v == event.artist][0]
        
        # Remove the line
        event.artist.remove()
        
        # Remove from legend
        legend = self.ax.get_legend()
        if legend:
            for text in legend.get_texts():
                if text.get_text() == label:
                    legend.remove()
                    break
        
        # Remove the corresponding data from all_plots
        plot_label = label.split(" - ")[0]
        self.all_plots = [p for p in self.all_plots if p['label'] != plot_label]
        
        # Redraw
        self.canvas.draw()
    
    def clear_all_plots(self):
        """Clear all plots and reset the plot counter"""
        self.all_plots = []
        self.plot_counter = 0
        self.ax.clear()
        self.ax.grid(True)
        self.canvas.draw()
        self.status_bar.showMessage("All plots cleared")
    
    def export_results(self):
        """Export processed results to file"""
        if not self.all_plots:
            QMessageBox.warning(self, "No Data", "No data to export. Please process data first.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Results", "", 
            "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                # Combine all data into one DataFrame
                all_data = []
                for plot in self.all_plots:
                    df = pd.DataFrame({
                        'Frequency (GHz)': plot['freq'],
                        'Correction_Factor': plot['correction_factors'],
                        'Corrected_RCS': plot['corrected_rcs'],
                        'Measurement': plot['label']
                    })
                    all_data.append(df)
                
                combined_df = pd.concat(all_data)
                combined_df.to_csv(file_path, index=False)
                QMessageBox.information(self, "Success", "Results exported successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed:\n{str(e)}")
    
    def toggle_theme(self):
        """Toggle between dark and light theme"""
        self.dark_theme = not self.dark_theme
        
        if self.dark_theme:
            self.setStyleSheet("""
                QWidget {
                    background-color: #3d3d3d;
                    color: #ffffff;
                }
                QGroupBox {
                    border: 1px solid #666;
                    border-radius: 5px;
                    margin-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 3px;
                }
                QTableWidget {
                    background-color: #2e2e2e;
                    color: #ffffff;
                    gridline-color: #555;
                }
                QHeaderView::section {
                    background-color: #555;
                    color: white;
                }
            """)
        else:
            self.setStyleSheet("")
        
        # Redraw plot with new theme if we have data
        if self.all_plots:
            self.plot_all_results()
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About RCS Analyzer",
            "<h2>Advanced RCS Analyzer</h2>"
            "<p>Version 1.0</p>"
            "<p>This application processes RCS measurements by applying "
            "correction factors based on sphere reference data.</p>"
            "<p>Features include:</p>"
            "<ul>"
            "<li>Automatic file format detection</li>"
            "<li>Interactive plotting with multiple measurements</li>"
            "<li>Click-to-remove graph functionality</li>"
            "<li>Data table view</li>"
            "<li>Dark/light theme</li>"
            "<li>Export capabilities</li>"
            "</ul>"
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show main window
    window = RCSAnalyzerApp()
    window.show()
    
    sys.exit(app.exec_())