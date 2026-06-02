from ultralytics import YOLO
import cv2
import numpy as np
import os

class VehicleDetector:
    def __init__(self, model_path=None):
        """
        Initialize YOLOv8 model for vehicle detection.
        Uses OpenImages V7 Medium model for high accuracy detection.
        """
        if model_path is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            model_path = os.path.join(project_root, "assets", "models", "yolov8m-oiv7.pt")
        self.model = YOLO(model_path)
        
        self.vehicle_classes = []
        self.ambulance_id = None
        
        target_names = ['car', 'motorcycle', 'bus', 'truck', 'land vehicle', 'ambulance']
        
        for class_id, name in self.model.names.items():
            name = name.lower()
            if any(target in name for target in target_names):
                self.vehicle_classes.append(class_id)
                if 'ambulance' in name:
                    self.ambulance_id = class_id

    def detect(self, frame, conf_threshold=0.3):
        """
        Detect vehicles in a frame.
        Returns a list of boxes: [x1, y1, x2, y2, class_id, conf]
        """
        results = self.model(frame, conf=conf_threshold, verbose=False, classes=self.vehicle_classes)
        detections = []

        for result in results:
            boxes = result.boxes
            for box in boxes:
                cls_id = int(box.cls[0])
                # No longer need to check if cls_id is in vehicle_classes here 
                # because the model call already filters them for us.
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                detections.append([x1, y1, x2, y2, cls_id, conf])
        
        return detections
