import cv2
import argparse
import numpy as np
import time
import os
from detector import VehicleDetector
from traffic_controller import TrafficSignal
from utils import draw_boxes, draw_signal_info, load_zones, draw_zones, is_point_in_zone, draw_zone_signals

def main():
    parser = argparse.ArgumentParser(description="AI Traffic Control System - HUD Edition")
    parser.add_argument("--location", type=str, default="default", help="Location config name from configs/ folder")
    parser.add_argument("--sources", nargs='+', help="Override video sources (paths or camera indices)")
    parser.add_argument("--output", type=str, help="Path to save output video (e.g. output.mp4)")
    args = parser.parse_args()

    # 1. Load Location Configuration
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, "configs", f"{args.location}.json")
    if not os.path.exists(config_path) and args.location == "default":
        # Fallback to old zones.json if configs/default.json is missing
        config_path = os.path.join(project_root, "data", "zones.json")
    
    print(f"Loading configuration from: {config_path}")
    location_data = load_zones(config_path)
    
    if isinstance(location_data, dict):
        zones = location_data.get("intersections", [])
        sources = args.sources if args.sources else location_data.get("sources", ["0"])
    else:
        # Fallback for old list-only format
        zones = location_data
        sources = args.sources if args.sources else ["0"]

    # 2. Open Video Sources
    caps = []
    for src in sources:
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
            print(f"Warning: Could not open video source {src}")
        caps.append(cap)

    if not caps:
        print("Error: No valid video sources found.")
        return

    # Ensure number of zones is equal to number of sources (max 4)
    num_sources = min(len(caps), 4)
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

    # 3. Initialize Components
    print("Loading YOLO model...")
    detector = VehicleDetector()
    traffic_signal = TrafficSignal(zones)

    # 4. Video Recording Setup
    video_writer = None
    if args.output:
        # Use XVID for better compatibility on Windows
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        # Main canvas is 1280x720
        video_writer = cv2.VideoWriter(args.output, fourcc, 20.0, (1280, 720))
        if not video_writer.isOpened():
            print(f"Error: Could not initialize video writer for {args.output}")
        else:
            print(f"Recording output to: {args.output}")

    print(f"Starting Traffic Control System [{args.location}]...")
    cv2.namedWindow("AI Traffic Control System", cv2.WINDOW_NORMAL)

    fps_count = 0
    fps_start_time = time.time()
    fps = 0

    while True:
        num_sources = len(caps)
        frames = []
        for cap in caps:
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

        # Detection & Logic
        detections = detector.detect(canvas)
        zone_counts = {zone['id']: 0 for zone in zones}
        emergency_zone_id = None
        
        for det in detections:
            x1, y1, x2, y2, cls, conf = det
            # Use middle of bottom edge for point detection
            pt = (int((x1+x2)/2), int(y2))
            for zone in zones:
                if is_point_in_zone(pt, zone):
                    zone_counts[zone['id']] += 1
                    if detector.ambulance_id is not None and cls == detector.ambulance_id:
                        emergency_zone_id = zone['id']
                    break
        
        traffic_signal.update_counts(zone_counts)
        remaining_time = traffic_signal.update(emergency_zone_id)
        signal_states = traffic_signal.states
        
        # UI Rendering
        draw_zones(canvas, zones, zone_counts)
        draw_zone_signals(canvas, zones, signal_states)
        draw_boxes(canvas, detections, detector.model.names)
        
        # FPS Calculation
        fps_count += 1
        if time.time() - fps_start_time >= 1:
            fps = fps_count
            fps_count = 0
            fps_start_time = time.time()

        # System Info Overlay (Futuristic HUD style)
        active_idx = traffic_signal.active_index
        active_zone = traffic_signal.zone_ids[active_idx] if traffic_signal.zone_ids else "N/A"
        
        # Technical Footer
        status_text = f"LOC: {args.location.upper()} | FPS: {fps} | ACTIVE: {active_zone} | TIMER: {remaining_time}s"
        cv2.putText(canvas, status_text, (20, 700), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # Show & Record
        if video_writer:
            video_writer.write(canvas)
            
        try:
            cv2.imshow("AI Traffic Control System", canvas)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        except Exception as e:
            # Fallback for headless environments
            if not args.output:
                print(f"Display error and no output file specified. Exiting: {e}")
                break
            # If recording is active, just keep going without display
            pass

    for cap in caps: cap.release()
    if video_writer: video_writer.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
