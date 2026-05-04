import os
import json
import datetime
from PyQt5.QtCore import Qt, QUrl, QThread, QTimer
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QComboBox, QProgressBar, QListWidget,
    QFileDialog, QGroupBox, QCheckBox, QSpinBox, QSizePolicy
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from worker import RouteWorker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class MainWindow(QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aviance Flight Route Optimizer — Professional Edition")
        self.setMinimumSize(1200, 800)
        self.setStyleSheet(self._get_stylesheet())
        self._build_ui()

        self.worker_thread = None
        self.worker = None
        self._last_result = None
        self._setup_auto_refresh()

    def _get_stylesheet(self):
        return """
        QWidget {
            background-color: #1e1e1e;
            color: #fff;
            font-family: 'Segoe UI', Arial, sans-serif;
            border: none;
        }

        QLineEdit, QTextEdit, QListWidget {
            background-color: #2d2d2d;
            border: 2px solid #404040;
            border-radius: 5px;
            padding: 8px;
        }

        QPushButton {
            background-color: #0b87ff;
            color: #fff;
            border: none;
            border-radius: 5px;
            padding: 10px;
            font-weight: bold;
            font-size: 12px;
        }

        QPushButton:hover {
            background-color: #0d95ff;
        }

        QPushButton:pressed {
            background-color: #0975d9;
        }

        QProgressBar {
            border: 2px solid #404040;
            border-radius: 5px;
            text-align: center;
            background-color: #2d2d2d;
        }

        QProgressBar::chunk {
            background-color: #0b87ff;
            border-radius: 3px;
        }

        QGroupBox {
            font-weight: bold;
            border: 2px solid #404040;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 10px 0 10px;
        }

        /* Remove any borders from the web engine view */
        QWebEngineView {
            border: none;
            background-color: #000011;
        }
        """

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # Remove margins to eliminate gaps
        layout.setSpacing(0)                   # Remove spacing between panels

        self.left_panel = self._create_left_panel()
        # Remove fixed width, allow shrink
        self.left_panel.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.right_panel = self._create_right_panel()
        self.right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout.addWidget(self.left_panel)
        layout.addWidget(self.right_panel, stretch=1)

    def _create_left_panel(self):
        widget = QWidget()
        widget.setStyleSheet("border: none;")  # Ensure no border on left panel
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        title = QLabel("✈️ Aviance Flight Route Optimizer")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #0b87ff; border: none;")
        subtitle = QLabel("Professional geodesic routing • Real-time 3D visualization • Advanced analytics")
        subtitle.setStyleSheet("color: #99ccee; font-size: 11px; border: none;")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Route group
        route_group = QGroupBox("Flight Route Configuration")
        route_layout = QVBoxLayout(route_group)
        route_layout.addWidget(QLabel("Departure Location:"))
        self.start_input = QLineEdit()
        self.start_input.setPlaceholderText("City, Airport, or IATA code (e.g., DEL, Delhi, Indira Gandhi)")
        route_layout.addWidget(self.start_input)
        route_layout.addWidget(QLabel("Arrival Location:"))
        self.end_input = QLineEdit()
        self.end_input.setPlaceholderText("City, Airport, or IATA code (e.g., JFK, New York)")
        route_layout.addWidget(self.end_input)
        layout.addWidget(route_group)

        # Aircraft group
        aircraft_group = QGroupBox("Aircraft Configuration")
        aircraft_layout = QVBoxLayout(aircraft_group)
        aircraft_layout.addWidget(QLabel("Aircraft Type:"))
        self.aircraft_combo = QComboBox()
        self.aircrafts = {
            "Airbus A320-200": (840, 2500, 6150, 37000),
            "Boeing 737-800": (830, 2600, 5765, 39000),
            "Boeing 787-9 Dreamliner": (900, 5000, 14140, 43000),
            "Airbus A350-900": (910, 5800, 15000, 43000),
            "Boeing 777-300ER": (890, 7500, 13649, 43000),
            "Embraer E190": (830, 1800, 4260, 41000),
            "Bombardier CRJ-900": (850, 1400, 2956, 41000),
            "Boeing 747-8F": (850, 10500, 8130, 43000),
        }
        for name, (speed, fuel, rng, alt) in self.aircrafts.items():
            self.aircraft_combo.addItem(f"{name} (Range: {rng:,} km, {speed} km/h)", name)
        aircraft_layout.addWidget(self.aircraft_combo)

        self.enable_animation = QCheckBox("Enable route animation")
        self.enable_animation.setChecked(True)
        aircraft_layout.addWidget(self.enable_animation)

        aircraft_layout.addWidget(QLabel("Animation Speed:"))
        self.animation_speed = QSpinBox()
        self.animation_speed.setRange(1, 10)
        self.animation_speed.setValue(3)
        self.animation_speed.setSuffix("x")
        aircraft_layout.addWidget(self.animation_speed)

        layout.addWidget(aircraft_group)

        # Buttons
        btn_layout = QVBoxLayout()
        self.optimize_btn = QPushButton("🚀 Optimize Route & Visualize")
        self.optimize_btn.clicked.connect(self.on_optimize)
        btn_layout.addWidget(self.optimize_btn)

        self.export_btn = QPushButton("💾 Export Route Data")
        self.export_btn.clicked.connect(self.on_export)
        self.export_btn.setEnabled(False)
        btn_layout.addWidget(self.export_btn)

        self.clear_btn = QPushButton("🗑️ Clear Route")
        self.clear_btn.clicked.connect(self.on_clear)
        btn_layout.addWidget(self.clear_btn)

        layout.addLayout(btn_layout)

        # Computation Progress
        diag_group = QGroupBox("Computation Progress")
        diag_layout = QVBoxLayout(diag_group)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(True)
        diag_layout.addWidget(self.progress)
        diag_layout.addWidget(QLabel("Computation Log:"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)
        diag_layout.addWidget(self.log)
        layout.addWidget(diag_group)

        # Route Analytics
        analytics_group = QGroupBox("Route Analytics")
        analytics_layout = QVBoxLayout(analytics_group)
        self.summary_list = QListWidget()
        self.summary_list.setMaximumHeight(200)
        analytics_layout.addWidget(self.summary_list)
        layout.addWidget(analytics_group)

        return widget

    def _create_right_panel(self):
        widget = QWidget()
        widget.setStyleSheet("border: none; background-color: #000011;")  # Remove any borders
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)  # Remove spacing
        
        self.web = QWebEngineView()
        self.web.setContentsMargins(0, 0, 0, 0)
        self.web.setStyleSheet("border: none; background-color: #000011;")  # Ensure no border
        
        index_html = os.path.join(BASE_DIR, "web", "index.html")
        if not os.path.exists(index_html):
            self.append_log("⚠️ Warning: web/index.html not found. Creating directory structure...")
            os.makedirs(os.path.join(BASE_DIR, "web"), exist_ok=True)
        self.web.load(QUrl.fromLocalFile(index_html))
        layout.addWidget(self.web)
        return widget

    def _setup_auto_refresh(self):
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._update_ui_state)
        self.refresh_timer.start(1000)

    def _update_ui_state(self):
        try:
            is_computing = self.worker_thread and self.worker_thread.isRunning()
        except RuntimeError:
            is_computing = False
        self.worker_thread = None if not is_computing else self.worker_thread
        self.optimize_btn.setEnabled(not is_computing)
        self.export_btn.setEnabled(self._last_result is not None and not is_computing)

    def append_log(self, text):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log.append(f"[{timestamp}] {text}")
        scrollbar = self.log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def on_optimize(self):
        start = self.start_input.text().strip()
        end = self.end_input.text().strip()
        if not start or not end:
            self.append_log("❌ Error: Please specify both departure and arrival locations.")
            return
        aircraft_key = self.aircraft_combo.currentData()
        if not aircraft_key:
            aircraft_key = list(self.aircrafts.keys())[0]
        cruise_kmh, fuel_kgph, max_range_km, altitude_ft = self.aircrafts[aircraft_key]
        self.summary_list.clear()
        self.progress.setValue(0)
        self._last_result = None
        self.append_log(f"🔄 Starting route optimization for {aircraft_key}...")
        self.worker_thread = QThread()
        self.worker = RouteWorker()
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(
            lambda: self.worker.run(start, end, cruise_kmh, fuel_kgph, max_range_km)
        )
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.error.connect(self._on_worker_error)
        self.worker.finished.connect(self._cleanup_worker)
        self.worker.error.connect(self._cleanup_worker)
        self.worker_thread.start()

    def _cleanup_worker(self):
        try:
            if self.worker_thread:
                self.worker_thread.quit()
                self.worker_thread.wait(2000)
            if hasattr(self.worker_thread, 'deleteLater'):
                self.worker_thread.deleteLater()
            self.worker_thread = None
            if self.worker and hasattr(self.worker, 'deleteLater'):
                self.worker.deleteLater()
            self.worker = None
        except RuntimeError:
            self.worker_thread = None
            self.worker = None

    def _on_worker_progress(self, pct, message):
        self.progress.setValue(pct)
        if message:
            self.append_log(message)

    def _on_worker_error(self, message):
        self.append_log(f"❌ ERROR: {message}")
        self.progress.setValue(0)

    def _on_worker_finished(self, result):
        if not result:
            self.append_log("❌ Route computation failed.")
            self.progress.setValue(0)
            return
        self.append_log("✅ Route computation completed successfully!")
        self.progress.setValue(85)
        self._last_result = result
        self._update_route_summary(result)
        self._send_to_globe(result)
        self.progress.setValue(100)
        self.append_log("🌍 Route visualization ready on 3D globe")

    def _update_route_summary(self, result):
        self.summary_list.clear()
        stats = result.get("stats", {})
        self.summary_list.addItem(f"🛫 Departure: {result['start_name'][:40]}...")
        self.summary_list.addItem(f"🛬 Arrival: {result['end_name'][:40]}...")
        self.summary_list.addItem(f"📏 Geodesic Distance: {stats.get('geodesic_km', 0):,.1f} km")
        self.summary_list.addItem(f"🎯 Route Accuracy: ±{stats.get('haversine_error_pct', 0):.3f}% (vs Haversine)")
        self.summary_list.addItem(f"⏱️ Est. Flight Time: {stats.get('eta_hr', 0):.1f}h (adj: {stats.get('eta_hr_adjusted', 0):.1f}h)")
        self.summary_list.addItem(f"⛽ Est. Fuel Consumption: {stats.get('fuel_kg', 0):,.0f} kg (adj: {stats.get('fuel_kg_adjusted', 0):,.0f} kg)")
        self.summary_list.addItem(f"🌪️ Wind Factor: {stats.get('wind_factor', 1):.2f} ({((stats.get('wind_factor', 1)-1)*100):+.1f}%)")
        self.summary_list.addItem(f"🛣️ Waypoints Generated: {len(result.get('waypoints', [])):,}")
        self.summary_list.addItem(f"🧭 Initial Bearing: {stats.get('az12', 0):.1f}°")
        self.summary_list.addItem(f"🧭 Final Bearing: {stats.get('az21', 0):.1f}°")

    def _send_to_globe(self, result):
        try:
            payload = {
                "waypoints": result["waypoints"],
                "start": {
                    "lat": result["start_coords"][0],
                    "lon": result["start_coords"][1],
                    "name": result["start_name"]
                },
                "end": {
                    "lat": result["end_coords"][0],
                    "lon": result["end_coords"][1],
                    "name": result["end_name"]
                },
                "stats": result["stats"],
                "animationEnabled": self.enable_animation.isChecked(),
                "animationSpeed": self.animation_speed.value() / 3.0
            }
            json_payload = json.dumps(payload, separators=(',', ':'))
            js_code = f"if(window.addRouteAndAnimate){{window.addRouteAndAnimate({json_payload});}}"
            self.web.page().runJavaScript(js_code)
        except Exception as e:
            self.append_log(f"❌ Error sending data to globe: {str(e)}")

    def on_export(self):
        if not self._last_result:
            self.append_log("❌ No route data available for export.")
            return
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"aviance_route_{timestamp}"
            self._export_geojson(base_filename)
            self._export_detailed_json(base_filename)
        except Exception as e:
            self.append_log(f"❌ Export error: {str(e)}")

    def _export_geojson(self, base_filename):
        waypoints = self._last_result["waypoints"]
        coords = [[pt["lon"], pt["lat"]] for pt in waypoints]
        geojson = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {
                    "route_type": "flight_path",
                    "departure": self._last_result["start_name"],
                    "arrival": self._last_result["end_name"],
                    "distance_km": self._last_result["stats"]["geodesic_km"],
                    "estimated_time_hours": self._last_result["stats"]["eta_hr_adjusted"],
                    "generated_by": "Aviance Flight Route Optimizer",
                    "timestamp": datetime.datetime.now().isoformat()
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords
                }
            }]
        }
        filename, _ = QFileDialog.getSaveFileName(self, "Export Route as GeoJSON",
                                                  f"{base_filename}.geojson",
                                                  "GeoJSON files (*.geojson);;All files (*)")
        if filename:
            with open(filename, "w", encoding="utf8") as f:
                json.dump(geojson, f, indent=2)
            self.append_log(f"✅ Route exported as GeoJSON: {os.path.basename(filename)}")

    def _export_detailed_json(self, base_filename):
        export_data = {
            "route_analysis": self._last_result,
            "export_metadata": {
                "generated_by": "Aviance Flight Route Optimizer",
                "export_time": datetime.datetime.now().isoformat(),
                "version": "2.0"
            }
        }
        filename, _ = QFileDialog.getSaveFileName(self, "Export Detailed Route Analysis",
                                                  f"{base_filename}_detailed.json",
                                                  "JSON files (*.json);;All files (*)")
        if filename:
            with open(filename, "w", encoding="utf8") as f:
                json.dump(export_data, f, indent=2)
            self.append_log(f"✅ Detailed analysis exported: {os.path.basename(filename)}")

    def on_clear(self):
        self.start_input.clear()
        self.end_input.clear()
        self.summary_list.clear()
        self.log.clear()
        self.progress.setValue(0)
        self._last_result = None
        self.web.page().runJavaScript("if(window.clearRoute){window.clearRoute();}")
        self.append_log("🔄 Interface cleared - Ready for new route")

    def closeEvent(self, event):
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait(3000)
        event.accept()