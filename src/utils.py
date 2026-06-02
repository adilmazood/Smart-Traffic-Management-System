import cv2
import numpy as np
import json
import os

def load_zones(config_path=None):
    """
    Loads zone configurations from a JSON file.
    Supports both list-only and location-based dictionary formats.
    """
    if config_path is None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, "data", "zones.json")
    try:
        if not os.path.exists(config_path):
            return []
        with open(config_path, 'r') as f:
            data = json.load(f)
            return data
    except Exception as e:
        print(f"Error loading zones from {config_path}: {e}")
        return []

def draw_boxes(frame, detections, names):
    """
    Draws futuristic neon corner brackets instead of full rectangles.
    """
    for det in detections:
        x1, y1, x2, y2, cls, conf = det
        cls_id = int(cls)
        label = names[cls_id] if cls_id in names else f"ID {cls_id}"
        
        # Futuristic Neon Color (Cyan for vehicle, Red for emergency vehicle)
        color = (0, 255, 255) # Cyan
        if 'ambulance' in label.lower():
            color = (0, 0, 255) # Bright Red
            label = "emergency vehicle"
        
        # Corner Brackets
        length = 20
        t = 2 # thickness
        # TL
        cv2.line(frame, (x1, y1), (x1 + length, y1), color, t)
        cv2.line(frame, (x1, y1), (x1, y1 + length), color, t)
        # TR
        cv2.line(frame, (x2, y1), (x2 - length, y1), color, t)
        cv2.line(frame, (x2, y1), (x2, y1 + length), color, t)
        # BL
        cv2.line(frame, (x1, y2), (x1 + length, y2), color, t)
        cv2.line(frame, (x1, y2), (x1, y2 - length), color, t)
        # BR
        cv2.line(frame, (x2, y2), (x2 - length, y2), color, t)
        cv2.line(frame, (x2, y2), (x2, y2 - length), color, t)
        
        # Tech Label
        cv2.rectangle(frame, (x1, y1 - 25), (x1 + 100, y1), color, -1)
        cv2.putText(frame, f"{label.upper()} {conf:.2f}", (x1 + 5, y1 - 7), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1, cv2.LINE_AA)

def draw_zones(frame, zones, zone_counts=None):
    """
    Draws zone borders and labels with vehicle counts.
    """
    for zone in zones:
        coords = np.array(zone['coords'], np.int32)
        # Use neutral white for borders
        color = (255, 255, 255)
        
        # Borders (Outer)
        cv2.polylines(frame, [coords], True, color, 1)
        
        # Text positioning
        M = cv2.moments(coords)
        if M["m00"] != 0:
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
            
            # Label
            name = zone.get('name', 'Zone').upper()
            cv2.putText(frame, name, (cX - 50, cY - 5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            if zone_counts:
                count = zone_counts.get(zone['id'], 0)
                cv2.putText(frame, f"TRK: {count:02d}", (cX - 50, cY + 15), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

def draw_zone_signals(frame, zones, states):
    """
    Draw futuristic digital signal bars in the top-right of each zone.
    """
    for zone in zones:
        zid = zone['id']
        state = states.get(zid, "RED").upper()
        
        coords = np.array(zone['coords'], np.int32)
        maxX = np.max(coords[:, 0])
        minY = np.min(coords[:, 1])
        
        lx, ly = maxX - 40, minY + 20
        
        # Background Bar
        cv2.rectangle(frame, (lx, ly), (lx + 30, ly + 80), (30, 30, 30), -1)
        cv2.rectangle(frame, (lx, ly), (lx + 30, ly + 80), (100, 100, 100), 1)
        
        # Glow Colors
        if state == "RED":
            cv2.rectangle(frame, (lx+5, ly+5), (lx+25, ly+25), (0, 0, 255), -1)
            cv2.rectangle(frame, (lx+2, ly+2), (lx+28, ly+28), (0, 0, 150), 1)
        elif state == "YELLOW":
            cv2.rectangle(frame, (lx+5, ly+30), (lx+25, ly+50), (0, 255, 255), -1)
            cv2.rectangle(frame, (lx+2, ly+27), (lx+28, ly+53), (0, 150, 150), 1)
        elif state == "GREEN":
            cv2.rectangle(frame, (lx+5, ly+55), (lx+25, ly+75), (0, 255, 0), -1)
            cv2.rectangle(frame, (lx+2, ly+52), (lx+28, ly+78), (0, 150, 0), 1)

def is_point_in_zone(point, zone):
    """
    Checks if a point is inside a zone's polygon.
    """
    coords = np.array(zone['coords'], np.int32)
    return cv2.pointPolygonTest(coords, (float(point[0]), float(point[1])), False) >= 0

def draw_signal_info(frame, phase, zone_id, remaining, count, emergency_zone_id=None):
    """
    Kept for backward compatibility.
    """
    pass
