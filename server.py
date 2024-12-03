import sys
import os
import folium
import subprocess
from PyQt5.QtCore import QUrl, pyqtSlot, pyqtSignal, pyqtProperty
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QHBoxLayout, QPushButton, QScrollArea, QFrame, QLabel, QInputDialog, QMessageBox, QFileDialog, QGroupBox, QSlider
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtGui import QCursor
from PyQt5.QtCore import Qt

from typing import Optional, Dict, List, Tuple, Union
from network_nodes import OLTNode, ONUNode, SplitterNode, Point, Connection, Node
from network_dump import dump_network_to_csv, load_network_from_csv
from simulation import UploadSimulation
import time

class MapApp(QMainWindow):
    
    addMarkerSignal = pyqtSignal(float, float, str, str, str)
    addConnectionSignal = pyqtSignal(float, float, float, float, str, str)
    highlightConnectionsSignal = pyqtSignal(str, str, str)
    selectedComponentTypeChanged = pyqtSignal()
    cleanMapSignal = pyqtSignal()
    
    def __init__(self):
        super().__init__()

        self.components: Dict[str, Node] = {}
        self.selected_node_class: Optional[Node] = None
        self.bandwidth: int = 0
        self.traffic_proportions: Dict[int, float] = {}
        self.selected_nodes: set[str] = set()
        self.current_menu: str = 'Create Net'
        self.upload_simulation: Optional[UploadSimulation] = None
        self.speed_slider_value: int = 10
        
        self.mapBounds = ((-33.16734, -70.32788), (-33.70830, -70.97311))
        self.center = (-33.43783, -70.65050)

        # Create a map centered on Santiago de Chile
        self.create_map()

        # Get the absolute path of the map file
        map_file_path = os.path.abspath('santiago_map.html')

        # Set up the GUI layout
        self.setWindowTitle("Interactive Map of Santiago de Chile")
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Create the lateral menu
        self.create_lateral_menu(main_layout)

        # Create and set up the web view
        self.web_view = QWebEngineView()
        file_url = QUrl.fromLocalFile(map_file_path)
        self.web_view.setUrl(file_url)
        main_layout.addWidget(self.web_view)

        # Web channel setup
        self.channel = QWebChannel()
        self.web_view.page().setWebChannel(self.channel)
        self.channel.registerObject("backend", self)

        # Handle right-click event to reset the cursor
        self.web_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.web_view.customContextMenuRequested.connect(self.reset_cursor)

    def create_lateral_menu(self, layout):
        # Create the scroll area for the lateral menu
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedWidth(250)  # Set fixed width for the lateral menu
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # Create collapsible group box for 'Create Net'
        self.create_net_group = QGroupBox("Create Net")
        create_net_layout = QVBoxLayout()
        self.create_net_group.setLayout(create_net_layout)

        # Add OLT button
        olt_button = QPushButton("OLT")
        olt_button.clicked.connect(lambda: self.add_component(OLTNode))
        olt_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                padding: 5px;
                margin: 2px;
            }
        """)
        create_net_layout.addWidget(olt_button)
        
        # Add Splitter button
        splitter_button = QPushButton("Splitter")
        splitter_button.clicked.connect(lambda: self.add_component(SplitterNode))
        splitter_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                padding: 5px;
                margin: 2px;
            }
        """)
        create_net_layout.addWidget(splitter_button)

        # Add ONU button
        onu_button = QPushButton("ONU")
        onu_button.clicked.connect(lambda: self.add_component(ONUNode))
        onu_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                padding: 5px;
                margin: 2px;
            }
        """)
        create_net_layout.addWidget(onu_button)

        # Add Connect button
        connect_button = QPushButton("Connect")
        connect_button.clicked.connect(self.select_connection_mode)
        connect_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                padding: 5px;
                margin: 2px;
            }
        """)
        create_net_layout.addWidget(connect_button)

        # Add Export button
        export_button = QPushButton("Export")
        export_button.clicked.connect(self.export_network)
        export_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                padding: 5px;
                margin: 2px;
            }
        """)
        create_net_layout.addWidget(export_button)

        # Add Load button
        load_button = QPushButton("Load")
        load_button.clicked.connect(self.load_network)
        load_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                padding: 5px;
                margin: 2px;
            }
        """)
        create_net_layout.addWidget(load_button)

        # Add Finish button
        finish_button = QPushButton("Finish")
        finish_button.clicked.connect(self.finish_net_creation)
        finish_button.setStyleSheet("""
            QPushButton {
                background-color: #ff0000;
                border: 1px solid #d0d0d0;
                padding: 5px;
                margin: 2px;
            }
        """)
        create_net_layout.addWidget(finish_button)

        # Add the collapsible group box to the scroll layout
        scroll_layout.addWidget(self.create_net_group)

        # Create collapsible group box for 'Simulation'
        self.simulation_group = QGroupBox("Simulation")
        self.simulation_group.setVisible(False)  # Initially hidden
        simulation_layout = QVBoxLayout()
        self.simulation_group.setLayout(simulation_layout)

        # Add Simulation Start button
        start_simulation_button = QPushButton("Start Simulation")
        start_simulation_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                padding: 5px;
                margin: 2px;
            }
        """)
        start_simulation_button.clicked.connect(self.start_upload_simulation)
        simulation_layout.addWidget(start_simulation_button)

        # Add Simulation Stop button
        stop_simulation_button = QPushButton("Stop Simulation")
        stop_simulation_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                padding: 5px;
                margin: 2px;
            }
        """)
        stop_simulation_button.clicked.connect(self.stop_upload_simulation)
        simulation_layout.addWidget(stop_simulation_button)

        # Add Export Simulation button
        export_simulation_button = QPushButton("Export Simulation")
        export_simulation_button.clicked.connect(self.export_simulation_history)
        export_simulation_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                padding: 5px;
                margin: 2px;
            }
        """)
        simulation_layout.addWidget(export_simulation_button)

        # Add Simulation Speed slider
        simulation_layout.addWidget(QLabel("Simulation Speed"))
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setMinimum(1)
        self.speed_slider.setMaximum(100)
        self.speed_slider.setValue(self.speed_slider_value if self.upload_simulation else 10)
        self.speed_slider.valueChanged.connect(self.change_simulation_speed)
        simulation_layout.addWidget(self.speed_slider)

        # Add Go Back button
        go_back_button = QPushButton("Go Back")
        go_back_button.clicked.connect(self.go_back_to_net_creation)
        go_back_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                padding: 5px;
                margin: 2px;
            }
        """)
        simulation_layout.addWidget(go_back_button)

        # Add the collapsible group box to the scroll layout
        scroll_layout.addWidget(self.simulation_group)

        # Set the scroll area content
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

    def finish_net_creation(self):
        self.create_net_group.setVisible(False)
        self.simulation_group.setVisible(True)
        self.current_menu = 'Simulation'
        self.selected_node_class = None
        QApplication.setOverrideCursor(Qt.ArrowCursor)
        
        for component in self.components.values():
            if isinstance(component, ONUNode):
                component.get_olt_connection_ids()

        # Connect the updatePathSignal to show_onu_path
        self.upload_simulation = UploadSimulation(
            onu_ids=[component.id for component in self.components.values() if isinstance(component, ONUNode)],
            components=self.components
        )
        self.upload_simulation.updatePathSignal.connect(self.show_onu_path)

    def go_back_to_net_creation(self):
        self.simulation_group.setVisible(False)
        self.create_net_group.setVisible(True)
        self.current_menu = 'Create Net'

    @pyqtSlot(object)
    def add_component(self, component_class):
        self.selected_node_class = component_class
        self.selectedComponentTypeChanged.emit()
        QApplication.setOverrideCursor(Qt.CrossCursor)  # Change cursor to cross

        if component_class == ONUNode:
            
            bandwidth, ok = QInputDialog.getInt(self, "Input Bandwidth", "Enter bandwidth for ONU (Mbps):")
            if ok:
                self.bandwidth = bandwidth
            
            else:
                self.selected_node_class = None
                QApplication.setOverrideCursor(Qt.ArrowCursor)
                return
                
            dialog = QInputDialog(self)
            dialog.setWindowTitle("Input Traffic Proportions")
            dialog.setLabelText("Enter traffic proportions for T-CONT 1 to 4:")
            dialog.setInputMode(QInputDialog.DoubleInput)
            dialog.setDoubleDecimals(2)
            dialog.setDoubleRange(0, 1)
            dialog.setDoubleStep(0.01)

            proportions = []
            for i in range(4):
                dialog.setLabelText(f"Enter traffic proportion for T-CONT {i + 1}:")
                if dialog.exec_() == QInputDialog.Accepted:
                    proportions.append(dialog.doubleValue())
                else:
                    self.selected_node_class = None
                    QApplication.setOverrideCursor(Qt.ArrowCursor)

            if len(proportions) == 4 and sum(proportions) == 1:
                self.traffic_proportions = {i + 1: proportions[i] for i in range(4)}
            else:
                QMessageBox.critical(self, "Input Error", "Invalid input. Please enter four values between 0 and 1 that sum to 1.")
                self.selected_node_class = None
                QApplication.setOverrideCursor(Qt.ArrowCursor)
                

    def select_connection_mode(self):
        self.selected_node_class = "Connection"
        self.selectedComponentTypeChanged.emit()
        QApplication.setOverrideCursor(Qt.PointingHandCursor)  # Change cursor to pointing hand

    @pyqtSlot(str)
    def log(self, msg):
        print(f"JS LOG: {msg}")

    @pyqtSlot(str)
    def handleMarkerClick(self, index):
        print(index)
        if self.selected_node_class == "Connection":
            if len(self.selected_nodes) < 2:
                self.selected_nodes.add(index)
                if len(self.selected_nodes) == 2:
                    self.create_connection()
        elif self.selected_node_class is None and self.current_menu == 'Simulation':
            if isinstance(self.components[index], ONUNode):
                if index not in self.selected_nodes:
                    self.selected_nodes = {index}
                    self.show_onu_path(index)
                    self.load_components_to_map()
            else:
                if len(self.selected_nodes) > 0:
                    self.selected_nodes.clear()
                    self.show_onu_path()
            

    @pyqtSlot(float, float)
    def handleMapClick(self, lat, lng):
        if self.selected_node_class == "Connection":
            pass
        elif self.selected_node_class is not None:
            if self.selected_node_class == ONUNode:
                component = self.selected_node_class(lat, lng, bandwidth=self.bandwidth, traffic_proportions=self.traffic_proportions)
            else:
                component = self.selected_node_class(lat, lng)
            self.components[component.id] = component
            self.addMarkerSignal.emit(lat, lng, self.selected_node_class.__name__, component.id, component.icon_url)
            print(self.components)
        else:
            if self.current_menu == 'Simulation':
                if len(self.selected_nodes) > 0:
                    self.selected_nodes.clear()
                    self.show_onu_path()

    def create_connection(self):
        if len(self.selected_nodes) == 2:
            component1 = self.components[self.selected_nodes.pop()]
            component2 = self.components[self.selected_nodes.pop()]

            try:
                connection = component1.connect(component2)
                self.components[connection.id] = connection
                self.addConnectionSignal.emit(component1.lat, component1.lon, component2.lat, component2.lon, connection.id, 'blue')
            except ValueError as e:
                QMessageBox.critical(self, "Connection Error", str(e))
            finally:
                self.selected_nodes.clear()
            print(self.components)

    def create_map(self):
        self.map = folium.Map(
            location=self.center,
            zoom_start=13,
            min_zoom=11,
            min_lat=self.mapBounds[1][0],
            max_lat=self.mapBounds[0][0],
            min_lon=self.mapBounds[1][1],
            max_lon=self.mapBounds[0][1],
            max_bounds=True
        )

        # Add existing components to the map
        for component in self.components.values():
            folium.Marker(location=component['coords'], popup=component['type'].name).add_to(self.map)

        # Add external JavaScript file to the HTML
        script_path = os.path.abspath('map_script.js')
        self.map.get_root().html.add_child(folium.Element(f"""
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <script src="file://{script_path}"></script>
        """))

        self.map.save('santiago_map.html')
        
    def load_components_to_map(self):
        self.cleanMapSignal.emit()
        for component in self.components.values():
            if isinstance(component, Connection):
                self.addConnectionSignal.emit(component.start_node.lat, component.start_node.lon, component.end_node.lat, component.end_node.lon, component.id, 'blue')
            else:
                self.addMarkerSignal.emit(component.lat, component.lon, component.__class__.__name__, component.id, component.icon_url)

    @pyqtSlot(str)
    def removeComponent(self, index):
        if index in self.components:
            component = self.components[index]
            if isinstance(component, Connection):
                component.remove()
            else:
                for connection in component.connections[:]:
                    del self.components[connection.id]
                    connection.remove()
            del self.components[index]
            self.load_components_to_map()
        print(index, self.components)
            
    def reset_cursor(self):
        QApplication.setOverrideCursor(Qt.ArrowCursor)
        self.selected_node_class = None
        self.selectedComponentTypeChanged.emit()
        
    def show_onu_path(self, onu_id = None):
        for connections in self.components.values():
            if isinstance(connections, Connection):
                connections.selected = False
        
        selected = []
        
        if onu_id is not None:
            for connection_id in self.components[onu_id].olt_connection_ids:
                self.components[connection_id].selected = True 
                selected.append(connection_id)

        self.highlightConnectionsSignal.emit(','.join(selected), 'red', 'blue')

    def open_csv_file(self):
        import tempfile
        csv_file_path = tempfile.NamedTemporaryFile(suffix='.csv', delete=False).name
        components = list(self.components.values())
        dump_network_to_csv(components, csv_file_path)

        if sys.platform == "win32":
            os.startfile(csv_file_path)
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.call([opener, csv_file_path])

    def export_network(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save CSV File", "", "CSV Files (*.csv)")
        if file_path:
            components = list(self.components.values())
            dump_network_to_csv(components, file_path)
            QMessageBox.information(self, "Export Successful", f"Network exported to {file_path}")

    def load_network(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open CSV File", "", "CSV Files (*.csv)")
        if file_path:
            self.components = load_network_from_csv(file_path)
            self.load_components_to_map()

    def start_upload_simulation(self):
        onu_ids = [component.id for component in self.components.values() if isinstance(component, ONUNode)]
        if onu_ids:
            self.upload_simulation = UploadSimulation(onu_ids, self.components, speed=self.speed_slider_value*10)
            self.upload_simulation.updatePathSignal.connect(self.show_onu_path)
            self.upload_simulation.start()
            self.selected_node_class = None 
            self.selected_nodes.clear()

    def stop_upload_simulation(self):
        if self.upload_simulation:
            self.upload_simulation.stop()
            # self.upload_simulation = None
            self.show_onu_path()  
            self.selected_node_class = None 

    def export_simulation_history(self):
        if self.upload_simulation:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Simulation History", "", "CSV Files (*.csv)")
            if file_path:
                self.upload_simulation.export_history(file_path)
                QMessageBox.information(self, "Export Successful", f"Simulation history exported to {file_path}")
        else:
            QMessageBox.warning(self, "No Data", "No simulation history to export.")

    def change_simulation_speed(self, value):
        self.speed_slider_value = value
        if self.upload_simulation:
            self.upload_simulation.speed = value*10

    @pyqtSlot(str, result=int)
    def getBandwidth(self, index):
        component = self.components.get(index)
        if isinstance(component, ONUNode):
            return component.bandwidth
        return 0

if __name__ == "__main__":
    app = QApplication(sys.argv)
    map_app = MapApp()
    map_app.show()
    sys.exit(app.exec_())
