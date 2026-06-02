import cv2
import numpy as np
import os
import time
from PyQt6.QtCore import QThread, pyqtSignal
from detector import VehicleDetector
from traffic_controller import TrafficSignal
from utils import load_zones, draw_zones, is_point_in_zone, draw_zone_signals, draw_boxes

class TrafficEngineThread(QThread):
    frame_ready = pyqtSignal(np.ndarray)
    stats_ready = pyqtSignal(dict)
    
    def __init__(self, location="default", sources=None):
        super().__init__()
        self.location = location
        self.sources = sources if sources else ["0"]
        self.running = True
        
        # Override flags from the UI
        self.force_green_lane = None
        self.force_red_lane = None
        self.ambulance_override_lane = None
        self.vip_override_lane = None
        
    def run(self):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, "configs", f"{self.location}.json")
        if not os.path.exists(config_path) and self.location == "default":
            config_path = os.path.join(project_root, "data", "zones.json")
            
        location_data = load_zones(config_path)
        if isinstance(location_data, dict):
            zones = location_data.get("intersections", [])
        else:
            zones = location_data
            
        self.caps = []
        for src in self.sources:
            if str(src).isdigit():
                src_val = int(src)
            else:
                if not os.path.isabs(str(src)) and not os.path.exists(str(src)):
                    resolved = os.path.join(project_root, str(src))
                    if os.path.exists(resolved):
                        src_val = resolved
                    else:
                        # Fallback check if it's in assets/videos/
                        fallback = os.path.join(project_root, "assets", "videos", os.path.basename(str(src)))
                        if os.path.exists(fallback):
                            src_val = fallback
                        else:
                            src_val = str(src)
                else:
                    src_val = str(src)
            cap = cv2.VideoCapture(src_val)
            if not cap.isOpened():
                print(f"Warning: Could not open video source {src_val}")
            else:
                self.caps.append(cap)
                
        if not self.caps:
            print("Error: No valid video sources found.")
            return
            
        # Ensure number of zones is equal to number of sources (max 4)
        num_sources = min(len(self.caps), 4)
        if len(zones) > num_sources:
            zones = zones[:num_sources]
        elif len(zones) < num_sources:
            for i in range(len(zones), num_sources):
                zones.append({
                    "id": f"lane_{i+1}",
                    "name": f"Lane {i+1}",
                    "coords": [[0, 0], [0, 0], [0, 0], [0, 0]],
                    "color": [255, 255, 255]
                })
        
        if num_sources == 1 and len(zones) == 1:
            zones[0]['coords'] = [[0, 0], [1280, 0], [1280, 720], [0, 720]]
        elif num_sources == 2 and len(zones) == 2:
            zones[0]['coords'] = [[0, 0], [640, 0], [640, 720], [0, 720]]
            zones[1]['coords'] = [[640, 0], [1280, 0], [1280, 720], [640, 720]]
        elif num_sources >= 3:
            quad_coords = [
                [[0, 0], [640, 0], [640, 360], [0, 360]],       # TL
                [[640, 0], [1280, 0], [1280, 360], [640, 360]],   # TR
                [[640, 360], [1280, 360], [1280, 720], [640, 720]],# BR
                [[0, 360], [640, 360], [640, 720], [0, 720]]      # BL
            ]
            for idx in range(len(zones)):
                if idx < 4:
                    zones[idx]['coords'] = quad_coords[idx]
            
        detector = VehicleDetector()
        traffic_signal = TrafficSignal(zones)
        
        while self.running:
            num_sources = len(self.caps)
            frames = []
            for cap in self.caps:
                ret, frame = cap.read()
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret:
                        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
                
                # Intelligent resizing based on layout
                if num_sources == 1:
                    frames.append(cv2.resize(frame, (1280, 720)))
                elif num_sources == 2:
                    frames.append(cv2.resize(frame, (640, 720)))
                else:
                    frames.append(cv2.resize(frame, (640, 360)))

            # Stitching Logic
            canvas = np.zeros((720, 1280, 3), dtype=np.uint8)
            if num_sources == 1:
                canvas = frames[0]
            elif num_sources == 2:
                canvas[:, 0:640] = frames[0]
                canvas[:, 640:1280] = frames[1]
            else:
                positions = [(0, 0), (0, 640), (360, 640), (360, 0)] # TL, TR, BR, BL
                for i, f in enumerate(frames):
                    if i < 4:
                        y, x = positions[i]
                        canvas[y:y+360, x:x+640] = f
            
            # Detect
            detections = detector.detect(canvas)
            zone_counts = {zone['id']: 0 for zone in zones}
            emergency_zone_id = None
            
            for det in detections:
                x1, y1, x2, y2, cls, conf = det
                pt = (int((x1+x2)/2), int(y2))
                for zone in zones:
                    if is_point_in_zone(pt, zone):
                        zone_counts[zone['id']] += 1
                        if detector.ambulance_id is not None and cls == detector.ambulance_id:
                            emergency_zone_id = zone['id']
                        break
                        
            ai_ambulance_detected = emergency_zone_id is not None

            # Apply Manual UI Overrides if triggered
            if self.ambulance_override_lane:
                emergency_zone_id = self.ambulance_override_lane
            if self.vip_override_lane:
                emergency_zone_id = self.vip_override_lane
                
            traffic_signal.update_counts(zone_counts)
            remaining_time = traffic_signal.update(emergency_zone_id)
            
            # Direct UI force
            if self.force_green_lane:
                traffic_signal.force_green(self.force_green_lane)
                remaining_time = traffic_signal.duration
                self.force_green_lane = None
            elif self.force_red_lane:
                traffic_signal.force_red(self.force_red_lane)
                remaining_time = traffic_signal.duration
                self.force_red_lane = None
                
            signal_states = traffic_signal.states
            
            draw_zones(canvas, zones, zone_counts)
            draw_zone_signals(canvas, zones, signal_states)
            draw_boxes(canvas, detections, detector.model.names)
            
            # Emit data to UI
            active_idx = traffic_signal.active_index
            active_zone = traffic_signal.zone_ids[active_idx] if traffic_signal.zone_ids else "N/A"
            stats = {
                "counts": zone_counts,
                "states": signal_states,
                "active_zone": active_zone,
                "time": remaining_time,
                "ambulance_detected": ai_ambulance_detected
            }
            
            self.stats_ready.emit(stats)
            self.frame_ready.emit(canvas)
            
            # ~20 FPS limit for GUI responsiveness
            time.sleep(0.05)
            
        for cap in self.caps:
            cap.release()

    def stop(self):
        self.running = False
        self.wait()
