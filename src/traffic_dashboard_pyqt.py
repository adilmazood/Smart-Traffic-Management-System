import os
if os.name == 'nt':
    try:
        import site
        for site_pkg in site.getsitepackages():
            torch_lib = os.path.join(site_pkg, "torch", "lib")
            if os.path.exists(torch_lib):
                os.add_dll_directory(torch_lib)
    except Exception:
        pass

import torch
from detector import VehicleDetector

import sys
import threading

import sqlite3
import bcrypt
import cv2
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTabWidget, QFrame, QMessageBox, QComboBox, 
                             QSpinBox, QProgressBar, QTextEdit, QScrollArea, 
                             QGridLayout, QSizePolicy, QFileDialog, QInputDialog,
                             QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QImage, QPixmap

from traffic_controller import TrafficSignal
from utils import draw_boxes, draw_signal_info, load_zones, draw_zones, is_point_in_zone, draw_zone_signals
from traffic_engine import TrafficEngineThread

matplotlib.rcParams['figure.facecolor'] = '#1a1a2e'
matplotlib.rcParams['axes.facecolor'] = '#16213e'
matplotlib.rcParams['axes.labelcolor'] = '#e0e0e0'
matplotlib.rcParams['text.color'] = '#e0e0e0'
matplotlib.rcParams['xtick.color'] = '#e0e0e0'
matplotlib.rcParams['ytick.color'] = '#e0e0e0'
matplotlib.rcParams['axes.edgecolor'] = '#0f3460'

# --- Colors ---
BG_DARK = "#0d0d1a"
BG_PANEL = "#1a1a2e"
BG_CARD = "#16213e"
BG_ACCENT = "#0f3460"
CLR_RED = "#e94560"
CLR_YELLOW = "#f5a623"
CLR_GREEN = "#2ecc71"
CLR_BLUE = "#4ac9e3"
CLR_TEXT = "#e0e0e0"
CLR_SUBTEXT = "#8888aa"
CLR_CORRIDOR = "#00ff99"

def get_db_path():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, "data", "traffic_users.db")

def init_db():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash BLOB,
            role TEXT
        )
    """)
    conn.commit()
    try:
        create_user("admin", "admin123", "Traffic Officer")
        create_user("developer", "dev123", "Project Developer")
    except Exception:
        pass
    conn.close()

def create_user(username, password, role):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    c.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
              (username, hashed, role))
    conn.commit()
    conn.close()

def authenticate(username, password):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("SELECT password_hash, role FROM users WHERE username=?", (username,))
    result = c.fetchone()
    conn.close()
    if result:
        stored_hash, role = result
        if bcrypt.checkpw(password.encode(), stored_hash):
            return role
    return None

class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Traffic Authority — Login")
        self.setFixedSize(480, 560)
        self.setStyleSheet(f"background-color: {BG_DARK}; color: {CLR_TEXT};")
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Icon/Title
        title_lbl = QLabel("🚦 TRAFFIC AUTHORITY")
        title_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {CLR_BLUE};")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)
        
        sub_lbl = QLabel("Control Dashboard")
        sub_lbl.setFont(QFont("Segoe UI", 11))
        sub_lbl.setStyleSheet(f"color: {CLR_SUBTEXT};")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub_lbl)
        
        # Card Layout
        card = QFrame()
        card.setStyleSheet(f"background-color: {BG_PANEL}; border: 1px solid {BG_ACCENT}; border-radius: 8px;")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 36, 36, 36)
        
        restr_lbl = QLabel("Restricted Access")
        restr_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        restr_lbl.setStyleSheet("border: none;")
        card_layout.addWidget(restr_lbl)
        
        # Username
        u_lbl = QLabel("USERNAME")
        u_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        u_lbl.setStyleSheet(f"color: {CLR_SUBTEXT}; border: none;")
        card_layout.addWidget(u_lbl)
        self.u_input = QLineEdit()
        self.u_input.setStyleSheet(f"background-color: {BG_CARD}; padding: 8px; border: 1px solid {BG_ACCENT};")
        card_layout.addWidget(self.u_input)
        
        # Password
        p_lbl = QLabel("PASSWORD")
        p_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        p_lbl.setStyleSheet(f"color: {CLR_SUBTEXT}; border: none;")
        card_layout.addWidget(p_lbl)
        self.p_input = QLineEdit()
        self.p_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.p_input.setStyleSheet(f"background-color: {BG_CARD}; padding: 8px; border: 1px solid {BG_ACCENT};")
        card_layout.addWidget(self.p_input)
        
        # Login Btn
        login_btn = QPushButton("LOGIN")
        login_btn.setStyleSheet(f"background-color: {CLR_BLUE}; color: {BG_DARK}; font-weight: bold; padding: 10px; border: none;")
        login_btn.clicked.connect(self.login)
        card_layout.addWidget(login_btn)
        
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet(f"color: {CLR_RED}; border: none;")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.status_lbl)
        
        layout.addWidget(card)
        self.u_input.returnPressed.connect(self.login)
        self.p_input.returnPressed.connect(self.login)

    def login(self):
        user = self.u_input.text().strip()
        pw = self.p_input.text()
        if not user or not pw:
            self.status_lbl.setText("Please fill in all fields.")
            self.status_lbl.setStyleSheet(f"color: {CLR_YELLOW}; border: none;")
            return
            
        role = authenticate(user, pw)
        if role:
            self.dashboard = Dashboard(user, role)
            self.dashboard.show()
            self.close()
        else:
            self.status_lbl.setText("Invalid credentials. Try again.")
            self.status_lbl.setStyleSheet(f"color: {CLR_RED}; border: none;")

CORRIDOR_ROUTES = {
    "Route A — City Centre": ["Jct A1\n(Main St)", "Jct A2\n(Park Ave)", "Jct A3\n(Ring Rd)", "Jct A4\n(Hospital)"],
    "Route B — Northern Bypass": ["Jct B1\n(North Gate)", "Jct B2\n(Mill Rd)", "Jct B3\n(East Sq)", "Jct B4\n(Clinic)"],
    "Route C — Southern Express": ["Jct C1\n(South St)", "Jct C2\n(Bridge Rd)", "Jct C3\n(Metro Hub)", "Jct C4\n(Med Ctr)"]
}

class Dashboard(QMainWindow):
    def __init__(self, username, role):
        super().__init__()
        self.setWindowTitle("Traffic Authority — Control Dashboard")
        self.setMinimumSize(1000, 640)
        self.resize(1240, 760)
        self.setStyleSheet(f"background-color: {BG_DARK}; color: {CLR_TEXT};")
        self.username = username
        self.role = role
        
        # State
        self.engine = None
        self.current_light = "Green"
        self.timer = 15
        self.ambulance_active = False
        self.vip_active = False
        self.vehicle_counts = [0, 0, 0, 0]
        self.lane_states = ["RED", "RED", "RED", "RED"]
        self.running = True
        self.corridor_active = False
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Top bar
        topbar = QFrame()
        topbar.setFixedHeight(54)
        topbar.setStyleSheet(f"background-color: {BG_PANEL};")
        top_layout = QHBoxLayout(topbar)
        top_layout.setContentsMargins(18, 0, 14, 0)
        
        lbl_title = QLabel("🚦  Traffic Authority Control Dashboard")
        lbl_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl_title.setStyleSheet(f"color: {CLR_BLUE};")
        top_layout.addWidget(lbl_title)
        
        top_layout.addStretch()
        
        badge_bg = CLR_RED if "Officer" in self.role else BG_ACCENT
        lbl_role = QLabel(f" {self.role} ")
        lbl_role.setStyleSheet(f"background-color: {badge_bg}; color: white; padding: 4px; border-radius: 4px;")
        top_layout.addWidget(lbl_role)
        
        lbl_user = QLabel(self.username)
        lbl_user.setStyleSheet(f"color: {CLR_TEXT}; margin-left: 10px; margin-right: 10px;")
        top_layout.addWidget(lbl_user)
        
        # Source Selection Button
        btn_source = QPushButton("📁 Video Files")
        btn_source.setStyleSheet(f"background-color: {BG_CARD}; color: {CLR_BLUE}; padding: 6px; border-radius: 4px; border: 1px solid {BG_ACCENT}; margin-right: 5px;")
        btn_source.clicked.connect(self.select_source)
        top_layout.addWidget(btn_source)
        
        btn_cameras = QPushButton("📷 Cameras")
        btn_cameras.setStyleSheet(f"background-color: {BG_CARD}; color: {CLR_BLUE}; padding: 6px; border-radius: 4px; border: 1px solid {BG_ACCENT}; margin-right: 15px;")
        btn_cameras.clicked.connect(self.select_cameras)
        top_layout.addWidget(btn_cameras)
        
        # Location Selection
        lbl_loc = QLabel("Location:")
        lbl_loc.setStyleSheet(f"color: {CLR_SUBTEXT}; font-weight: bold; margin-left: 10px;")
        top_layout.addWidget(lbl_loc)
        
        self.combo_location = QComboBox()
        self.combo_location.setStyleSheet(f"background-color: {BG_CARD}; color: {CLR_BLUE}; padding: 6px; border-radius: 4px; border: 1px solid {BG_ACCENT}; margin-right: 15px;")
        self.load_available_locations()
        self.combo_location.currentIndexChanged.connect(self.on_location_changed)
        top_layout.addWidget(self.combo_location)
        
        btn_logout = QPushButton("Logout")
        btn_logout.setStyleSheet(f"background-color: {CLR_RED}; color: white; padding: 6px; border-radius: 4px;")
        btn_logout.clicked.connect(self.logout)
        top_layout.addWidget(btn_logout)
        
        main_layout.addWidget(topbar)
        
        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 0; }}
            QTabBar::tab {{ background: {BG_PANEL}; color: {CLR_SUBTEXT}; padding: 12px 20px; }}
            QTabBar::tab:selected {{ background: {BG_ACCENT}; color: {CLR_BLUE}; }}
        """)
        main_layout.addWidget(self.tabs)
        
        self.tab_signal = QWidget()
        self.tab_density = QWidget()
        self.tab_zones = QWidget()
        self.tab_logs = QWidget()
        
        self.tabs.addTab(self.tab_signal, "  🚦  Signals  ")
        self.tabs.addTab(self.tab_density, "  📊  Density Stats  ")
        self.tabs.addTab(self.tab_zones, "  📍  Zones Config  ")
        self.tabs.addTab(self.tab_logs, "  📋  Event Logs  ")
        
        self._build_signal_tab()
        self._build_density_tab()
        self._build_zones_tab()
        self._build_logs_tab()
        
    def select_source(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Video Files", "", "Video Files (*.mp4 *.avi *.mkv);;All Files (*)")
        if file_paths:
            self.start_engine(location=self.combo_location.currentText(), sources=file_paths)
            
    def select_cameras(self):
        text, ok = QInputDialog.getText(self, "Camera Sources", "Enter camera indices or streams (comma separated, e.g. 0,1):")
        if ok and text:
            indices = [x.strip() for x in text.split(",") if x.strip()]
            if indices:
                self.start_engine(location=self.combo_location.currentText(), sources=indices)
            else:
                self.log_event("No valid camera sources provided.", "yellow")
    def start_engine(self, location="default", sources=["0"]):
        if self.engine and self.engine.isRunning():
            self.engine.stop()
            
        self.engine = TrafficEngineThread(location=location, sources=sources)
        self.engine.frame_ready.connect(self.on_frame_ready)
        self.engine.stats_ready.connect(self.on_stats_ready)
        self.engine.start()
        self.log_event(f"Started OpenCV backend engine -> Src: {', '.join(sources)} | Loc: {location}", "green")

    def _build_signal_tab(self):
        layout = QHBoxLayout(self.tab_signal)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Left Panel (Signal Graphic)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.lbl_timer = QLabel("15 s")
        self.lbl_timer.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        self.lbl_timer.setStyleSheet(f"color: {CLR_GREEN};")
        self.lbl_timer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.lbl_timer)
        
        self.alert_label = QLabel("")
        self.alert_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.alert_label.setStyleSheet(f"color: {CLR_YELLOW};")
        self.alert_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.alert_label)
        
        # Add live camera feed
        self.lbl_camera = QLabel()
        self.lbl_camera.setFixedSize(640, 360) # Scaled down for UI embedded preview
        self.lbl_camera.setStyleSheet(f"background-color: #000; border: 2px solid {BG_ACCENT};")
        self.lbl_camera.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.lbl_camera)
        
        layout.addWidget(left_panel)
        
        # Right Panel (Controls)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.lane_selector = QComboBox()
        self.lane_selector.setStyleSheet(f"background-color: {BG_CARD}; color: {CLR_TEXT}; padding: 8px; border: 1px solid {BG_ACCENT}; margin-top: 5px; font-weight: bold;")
        self.lane_selector.addItem("Select Target Lane...")
        right_layout.addWidget(self.lane_selector)
        
        btn_green = QPushButton("🟢  Force Green")
        btn_green.setStyleSheet("background-color: #1a5c3a; color: #2ecc71; padding: 10px; margin-top: 10px;")
        btn_green.clicked.connect(self.force_green)
        right_layout.addWidget(btn_green)
        
        btn_red = QPushButton("🔴  Force Red")
        btn_red.setStyleSheet("background-color: #5c1a1a; color: #e94560; padding: 10px; margin-top: 5px;")
        btn_red.clicked.connect(self.force_red)
        right_layout.addWidget(btn_red)
        
        btn_amb = QPushButton("🚑  Manual Emergency Override")
        btn_amb.setStyleSheet("background-color: #5c3a00; color: #f5a623; padding: 10px; margin-top: 5px;")
        btn_amb.clicked.connect(self.trigger_ambulance)
        right_layout.addWidget(btn_amb)
        
        btn_vip = QPushButton("🚓  VIP Override")
        btn_vip.setStyleSheet("background-color: #3b1a5c; color: #a55cff; padding: 10px; margin-top: 5px;")
        btn_vip.clicked.connect(self.trigger_vip)
        right_layout.addWidget(btn_vip)
        
        self.lane_labels = []
        for i in range(4):
            lane_lbl = QLabel(f"Lane {i+1}: --")
            lane_lbl.setStyleSheet(f"background-color: {BG_PANEL}; padding: 10px; margin-top: 5px; color: {CLR_BLUE}; font-weight: bold;")
            self.lane_labels.append(lane_lbl)
            right_layout.addWidget(lane_lbl)
            
        layout.addWidget(right_panel)


    def _build_density_tab(self):
        layout = QVBoxLayout(self.tab_density)
        layout.setContentsMargins(24, 20, 24, 20)
        self.figure, self.ax = plt.subplots(figsize=(6, 4))
        self.canvas_graph = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas_graph)

    def _build_logs_tab(self):
        layout = QVBoxLayout(self.tab_logs)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(f"background-color: #0a0a15; color: {CLR_TEXT}; font-family: Consolas;")
        layout.addWidget(self.log_text)

    def _update_graph(self):
        self.ax.clear()

        num_lanes = len(self.vehicle_counts)
        lanes = [f"Lane {i+1}" for i in range(num_lanes)]
        colors = [CLR_RED if v > 18 else CLR_YELLOW if v > 12 else CLR_BLUE for v in self.vehicle_counts]

        if num_lanes > 0:
            bars = self.ax.bar(lanes, self.vehicle_counts, color=colors, width=0.5, edgecolor="none")

        self.ax.set_title("Vehicle Density per Lane", pad=12)
        self.ax.set_ylim(0, 30)
        self.ax.spines["top"].set_visible(False)
        self.ax.spines["right"].set_visible(False)
        self.canvas_graph.draw()
    
    def on_frame_ready(self, frame_data):
        # Convert OpenCV frame to PyQt pixel map
        h, w, ch = frame_data.shape
        bytes_per_line = ch * w
        # Color converting BGR to RGB
        rgb_image = cv2.cvtColor(frame_data, cv2.COLOR_BGR2RGB)
        q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img).scaled(640, 360, Qt.AspectRatioMode.KeepAspectRatio)
        self.lbl_camera.setPixmap(pixmap)
        
    def on_stats_ready(self, stats):
        self.timer = stats.get("time", 0)
        
        # Parse states -> determine color of UI indicator
        states = stats.get("states", {})
        active = stats.get("active_zone", "N/A")
        if active in states:
            self.current_light = states[active]
            
        counts = stats.get("counts", {})
        self.vehicle_counts = list(counts.values())
        self.lane_states = list(states.values())
        
        num_lanes = len(self.vehicle_counts)
        if hasattr(self, 'lane_selector') and self.lane_selector.count() - 1 != num_lanes:
            self.lane_selector.clear()
            self.lane_selector.addItem("Select Target Lane...")
            for i in range(num_lanes):
                self.lane_selector.addItem(f"Lane {i+1}")
            
        if stats.get("ambulance_detected") and not self.ambulance_active:
            self.ambulance_active = True
            self.alert_label.setText("🚑  EMERGENCY VEHICLE DETECTED")
            self.log_event("Emergency vehicle auto-detected by AI — adjusting lights", "yellow")
            QTimer.singleShot(8000, self._clear_ambulance)
            
        self._update_ui_data()

    def _update_ui_data(self):
        # Dedicated method separated from manual random ticks
        light = self.current_light
        fg_map = {"Green": CLR_GREEN, "Yellow": CLR_YELLOW, "Red": CLR_RED, "GREEN": CLR_GREEN, "YELLOW": CLR_YELLOW, "RED": CLR_RED}
        
        self.lbl_timer.setText(f"{self.timer} s")
        if light in fg_map or light.capitalize() in fg_map:
            color = fg_map.get(light, fg_map.get(light.capitalize(), CLR_GREEN))
            self.lbl_timer.setStyleSheet(f"color: {color};")
            
        for i, lbl in enumerate(self.lane_labels):
            if i < len(self.vehicle_counts):
                count = self.vehicle_counts[i]
                state = self.lane_states[i] if i < len(self.lane_states) else "RED"
                state_color = fg_map.get(state, fg_map.get(state.capitalize(), CLR_BLUE))
                
                lbl.setText(f"Lane {i+1} [{state.upper()}]: {count} Vehicles")
                lbl.setStyleSheet(f"background-color: {BG_PANEL}; padding: 10px; margin-top: 5px; color: {state_color}; font-weight: bold; border-left: 4px solid {state_color};")
                lbl.show()
            else:
                lbl.hide()
                
        self._update_graph()

    def get_selected_lane(self):
        idx = self.lane_selector.currentIndex()
        if idx > 0:
            return f"lane_{idx}"
        return None

    def force_green(self):
        target = self.get_selected_lane()
        if target and self.engine:
            self.engine.force_green_lane = target
            self.log_event(f"Manual override: Force Green on {target.replace('_', ' ').capitalize()}", "green")
        else:
            self.log_event("Select a target lane from the dropdown first", "yellow")

    def force_red(self):
        target = self.get_selected_lane()
        if target and self.engine:
            self.engine.force_red_lane = target
            self.log_event(f"Manual override: Force Red on {target.replace('_', ' ').capitalize()}", "red")
        else:
            self.log_event("Select a target lane from the dropdown first", "yellow")

    def trigger_ambulance(self):
        target = self.get_selected_lane()
        if target and self.engine:
            self.ambulance_active = True
            self.engine.ambulance_override_lane = target
            self.alert_label.setText(f"🚑  MANUAL EMERGENCY OVERRIDE ({target.replace('_', ' ').capitalize()})")
            self.log_event(f"Manual Emergency vehicle override to {target.replace('_', ' ').capitalize()}", "yellow")
            QTimer.singleShot(8000, self._clear_ambulance)
        else:
            self.log_event("Select a target lane from the dropdown first", "yellow")

    def _clear_ambulance(self):
        if self.ambulance_active:
            self.ambulance_active = False
            if self.engine:
                self.engine.ambulance_override_lane = None
            if not self.vip_active:
                self.alert_label.setText("")
            self.log_event("Emergency vehicle override timer expired", "blue")

    def trigger_vip(self):
        target = self.get_selected_lane()
        if target and self.engine:
            self.vip_active = True
            self.engine.vip_override_lane = target
            self.alert_label.setText(f"🚓  VIP PRIORITY ({target.replace('_', ' ').capitalize()})")
            self.log_event(f"VIP override activated for {target.replace('_', ' ').capitalize()}", "#a55cff")
            QTimer.singleShot(8000, self._clear_vip)
        else:
            self.log_event("Select a target lane from the dropdown first", "yellow")

    def _clear_vip(self):
        if self.vip_active:
            self.vip_active = False
            if self.engine:
                self.engine.vip_override_lane = None
            if not self.ambulance_active:
                self.alert_label.setText("")
            self.log_event("VIP override timer expired", "blue")

    def log_event(self, message, color="blue"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"<span style='color:{CLR_SUBTEXT};'>[{timestamp}]</span> <span style='color:{color};'>{message}</span>")

    def load_available_locations(self):
        self.combo_location.clear()
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        configs_dir = os.path.join(project_root, "configs")
        if os.path.exists(configs_dir):
            for file in os.listdir(configs_dir):
                if file.endswith(".json"):
                    loc_name = file[:-5]
                    self.combo_location.addItem(loc_name)
        if self.combo_location.count() == 0:
            self.combo_location.addItem("default")
            
    def on_location_changed(self):
        loc = self.combo_location.currentText()
        if not loc:
            return
        if self.engine and self.engine.isRunning():
            sources = self.engine.sources
            self.start_engine(location=loc, sources=sources)
        else:
            self.update_zones_display()
            
    def get_active_config_path(self):
        loc = self.combo_location.currentText()
        if not loc:
            loc = "default"
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, "configs", f"{loc}.json")
        if not os.path.exists(config_path) and loc == "default":
            config_path = os.path.join(project_root, "data", "zones.json")
        return config_path
        
    def _build_zones_tab(self):
        layout = QHBoxLayout(self.tab_zones)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Left Panel - Table of Zones
        left_panel = QFrame()
        left_panel.setStyleSheet(f"background-color: {BG_PANEL}; border: 1px solid {BG_ACCENT}; border-radius: 8px;")
        left_layout = QVBoxLayout(left_panel)
        
        lbl_list = QLabel("📋 Active Detection Zones")
        lbl_list.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_list.setStyleSheet("border: none; color: white;")
        left_layout.addWidget(lbl_list)
        
        self.zones_table = QTableWidget()
        self.zones_table.setColumnCount(4)
        self.zones_table.setHorizontalHeaderLabels(["ID", "Name", "Coordinates", "Color"])
        self.zones_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.zones_table.setStyleSheet(f"""
            QTableWidget {{ background-color: {BG_CARD}; color: {CLR_TEXT}; gridline-color: {BG_ACCENT}; border: none; }}
            QHeaderView::section {{ background-color: {BG_PANEL}; color: {CLR_BLUE}; border: 1px solid {BG_ACCENT}; padding: 6px; font-weight: bold; }}
            QTableWidget::item:selected {{ background-color: {BG_ACCENT}; color: white; }}
        """)
        self.zones_table.itemSelectionChanged.connect(self.on_zone_selection_changed)
        left_layout.addWidget(self.zones_table)
        
        layout.addWidget(left_panel, 2)
        
        # Right Panel - Form to Add/Edit Zones
        right_panel = QFrame()
        right_panel.setStyleSheet(f"background-color: {BG_PANEL}; border: 1px solid {BG_ACCENT}; border-radius: 8px;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        lbl_form = QLabel("📍 Add / Edit Zone")
        lbl_form.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_form.setStyleSheet("border: none; color: white; margin-bottom: 10px;")
        right_layout.addWidget(lbl_form)
        
        # ID Field
        u_lbl = QLabel("ZONE ID")
        u_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        u_lbl.setStyleSheet(f"color: {CLR_SUBTEXT}; border: none;")
        right_layout.addWidget(u_lbl)
        self.zone_id_input = QLineEdit()
        self.zone_id_input.setStyleSheet(f"background-color: {BG_CARD}; padding: 8px; border: 1px solid {BG_ACCENT}; color: white;")
        right_layout.addWidget(self.zone_id_input)
        
        # Name Field
        n_lbl = QLabel("ZONE NAME")
        n_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        n_lbl.setStyleSheet(f"color: {CLR_SUBTEXT}; border: none; margin-top: 10px;")
        right_layout.addWidget(n_lbl)
        self.zone_name_input = QLineEdit()
        self.zone_name_input.setStyleSheet(f"background-color: {BG_CARD}; padding: 8px; border: 1px solid {BG_ACCENT}; color: white;")
        right_layout.addWidget(self.zone_name_input)
        
        # Coordinates Field
        c_lbl = QLabel("COORDINATES (e.g. [[0,0],[640,0],[640,360],[0,360]])")
        c_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        c_lbl.setStyleSheet(f"color: {CLR_SUBTEXT}; border: none; margin-top: 10px;")
        right_layout.addWidget(c_lbl)
        self.zone_coords_input = QLineEdit()
        self.zone_coords_input.setStyleSheet(f"background-color: {BG_CARD}; padding: 8px; border: 1px solid {BG_ACCENT}; color: white;")
        right_layout.addWidget(self.zone_coords_input)
        
        # Color Field
        cl_lbl = QLabel("COLOR (RGB, e.g. [255, 0, 0])")
        cl_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        cl_lbl.setStyleSheet(f"color: {CLR_SUBTEXT}; border: none; margin-top: 10px;")
        right_layout.addWidget(cl_lbl)
        self.zone_color_input = QLineEdit()
        self.zone_color_input.setStyleSheet(f"background-color: {BG_CARD}; padding: 8px; border: 1px solid {BG_ACCENT}; color: white;")
        right_layout.addWidget(self.zone_color_input)
        
        # Buttons
        btn_save = QPushButton("💾 Save Zone")
        btn_save.setStyleSheet(f"background-color: {CLR_BLUE}; color: {BG_DARK}; font-weight: bold; padding: 10px; border: none; margin-top: 20px;")
        btn_save.clicked.connect(self.save_zone)
        right_layout.addWidget(btn_save)
        
        btn_delete = QPushButton("🗑️ Delete Selected Zone")
        btn_delete.setStyleSheet(f"background-color: {CLR_RED}; color: white; font-weight: bold; padding: 10px; border: none; margin-top: 10px;")
        btn_delete.clicked.connect(self.delete_zone)
        right_layout.addWidget(btn_delete)
        
        btn_clear = QPushButton("🧹 Clear Form")
        btn_clear.setStyleSheet(f"background-color: {BG_ACCENT}; color: white; padding: 8px; border: none; margin-top: 10px;")
        btn_clear.clicked.connect(self.clear_zone_form)
        right_layout.addWidget(btn_clear)
        
        layout.addWidget(right_panel, 1)
        
        self.update_zones_display()
        
    def update_zones_display(self):
        config_path = self.get_active_config_path()
        location_data = load_zones(config_path)
        
        if isinstance(location_data, dict):
            zones = location_data.get("intersections", [])
        else:
            zones = location_data
            
        self.zones_table.setRowCount(len(zones))
        for idx, zone in enumerate(zones):
            self.zones_table.setItem(idx, 0, QTableWidgetItem(str(zone.get('id', ''))))
            self.zones_table.setItem(idx, 1, QTableWidgetItem(str(zone.get('name', ''))))
            self.zones_table.setItem(idx, 2, QTableWidgetItem(str(zone.get('coords', ''))))
            self.zones_table.setItem(idx, 3, QTableWidgetItem(str(zone.get('color', ''))))
            
    def on_zone_selection_changed(self):
        selected_rows = self.zones_table.selectedItems()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        self.zone_id_input.setText(self.zones_table.item(row, 0).text())
        self.zone_name_input.setText(self.zones_table.item(row, 1).text())
        self.zone_coords_input.setText(self.zones_table.item(row, 2).text())
        self.zone_color_input.setText(self.zones_table.item(row, 3).text())
        
    def clear_zone_form(self):
        self.zone_id_input.clear()
        self.zone_name_input.clear()
        self.zone_coords_input.clear()
        self.zone_color_input.clear()
        self.zones_table.clearSelection()
        
    def save_zone(self):
        zid = self.zone_id_input.text().strip()
        name = self.zone_name_input.text().strip()
        coords_str = self.zone_coords_input.text().strip()
        color_str = self.zone_color_input.text().strip()
        
        if not zid or not name or not coords_str or not color_str:
            QMessageBox.warning(self, "Validation Error", "All fields are required.")
            return
            
        try:
            import json
            coords = json.loads(coords_str)
            color = json.loads(color_str)
        except Exception as e:
            QMessageBox.warning(self, "Validation Error", f"Failed to parse Coordinates or Color JSON: {e}")
            return
            
        config_path = self.get_active_config_path()
        location_data = load_zones(config_path)
        
        is_dict = isinstance(location_data, dict)
        zones = location_data.get("intersections", []) if is_dict else location_data
        
        existing_idx = -1
        for idx, z in enumerate(zones):
            if z.get('id') == zid:
                existing_idx = idx
                break
                
        new_zone = {
            "id": zid,
            "name": name,
            "coords": coords,
            "color": color
        }
        
        if existing_idx >= 0:
            zones[existing_idx] = new_zone
        else:
            zones.append(new_zone)
            
        if is_dict:
            location_data["intersections"] = zones
        else:
            location_data = zones
            
        try:
            with open(config_path, 'w') as f:
                json.dump(location_data, f, indent=4)
            QMessageBox.information(self, "Success", f"Zone '{name}' saved successfully to {os.path.basename(config_path)}!")
            self.update_zones_display()
            self.clear_zone_form()
            if self.engine and self.engine.isRunning():
                self.on_location_changed()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to write to file: {e}")
            
    def delete_zone(self):
        selected_rows = self.zones_table.selectedItems()
        if not selected_rows:
            QMessageBox.warning(self, "Selection Error", "Please select a zone to delete from the table.")
            return
            
        row = selected_rows[0].row()
        zid = self.zones_table.item(row, 0).text()
        
        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete zone '{zid}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
            
        config_path = self.get_active_config_path()
        location_data = load_zones(config_path)
        
        is_dict = isinstance(location_data, dict)
        zones = location_data.get("intersections", []) if is_dict else location_data
        
        zones = [z for z in zones if z.get('id') != zid]
        
        if is_dict:
            location_data["intersections"] = zones
        else:
            location_data = zones
            
        try:
            import json
            with open(config_path, 'w') as f:
                json.dump(location_data, f, indent=4)
            QMessageBox.information(self, "Success", f"Zone '{zid}' deleted successfully!")
            self.update_zones_display()
            self.clear_zone_form()
            if self.engine and self.engine.isRunning():
                self.on_location_changed()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to write to file: {e}")

    def logout(self):
        self.running = False
        if self.engine:
            self.engine.stop()
        self.close()

def main():
    init_db()
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
