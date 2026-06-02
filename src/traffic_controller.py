import time

class TrafficSignal:
    def __init__(self, zones, min_green=15, max_green=60, yellow_time=3):
        """
        Traffic Signal Controller for Multiple Lanes.
        :param zones: List of zone dictionaries (from zones.json)
        """
        self.min_green = min_green
        self.max_green = max_green
        self.yellow_time = yellow_time
        
        self.zones = zones
        self.zone_ids = [z['id'] for z in zones]
        
        # State: Dictionary mapping zone_id -> "RED", "YELLOW", "GREEN"
        self.states = {zid: "RED" for zid in self.zone_ids}
        
        # Logic: Round Robin
        self.active_index = 0 # Index of the zone currently GREEN or going YELLOW
        if self.zone_ids:
            self.states[self.zone_ids[0]] = "GREEN"
            
        self.start_time = time.time()
        self.duration = min_green # Init with min green
        self.lane_counts = {zid: 0 for zid in self.zone_ids}

    def update_counts(self, counts):
        """
        Update vehicle counts for the current logic cycle.
        """
        self.lane_counts = counts

    def calculate_green_time(self, vehicle_count):
        """
        Dynamic Green Time Algorithm
        Calculates time based on vehicle density.
        """
        # Linear increase: 15s base + 3s per vehicle
        # This makes it more responsive to even small changes
        factor = 3 
        calculated_time = self.min_green + (vehicle_count * factor)
        return min(calculated_time, self.max_green)

    def update(self, emergency_zone_id=None):
        """
        Main logic loop. Call this every frame.
        :param emergency_zone_id: The ID of the zone with an ambulance (priority).
        """
        if not self.zone_ids:
            return

        active_zone = self.zone_ids[self.active_index]
        current_state = self.states[active_zone]

        # 1. Emergency Override Logic
        if emergency_zone_id is not None:
            if active_zone == emergency_zone_id:
                # Ambulance in green lane: Keep it GREEN
                if current_state == "GREEN":
                    self.start_time = time.time()
                    self.duration = self.min_green
                elif current_state == "YELLOW":
                    self.states[active_zone] = "GREEN"
                    self.start_time = time.time()
            else:
                # Ambulance waiting in another lane: Switch ASAP
                if current_state == "GREEN":
                     self.switch_phase()
                     self.duration = 2 # Fast yellow
                elif current_state == "YELLOW":
                    elapsed = time.time() - self.start_time
                    if elapsed >= 0.5:
                        try:
                            target_index = self.zone_ids.index(emergency_zone_id)
                            self.switch_phase(target_index=target_index)
                        except ValueError:
                            pass

        # 2. Dynamic Green Extension
        # If we are in GREEN, check if current vehicle count justifies a longer light
        if current_state == "GREEN":
            current_count = self.lane_counts.get(active_zone, 0)
            potential_duration = self.calculate_green_time(current_count)
            
            # If the new count suggests more time, extend the duration
            if potential_duration > self.duration:
                self.duration = potential_duration

        elapsed = time.time() - self.start_time
        remaining = max(0, self.duration - elapsed)
        
        if remaining == 0:
            self.switch_phase()
            
        return int(remaining)

    def switch_phase(self, target_index=None):
        current_zone_id = self.zone_ids[self.active_index]
        current_state = self.states[current_zone_id]
        
        self.start_time = time.time()
        
        if current_state == "GREEN":
            self.states[current_zone_id] = "YELLOW"
            self.duration = self.yellow_time
            
        elif current_state == "YELLOW":
            self.states[current_zone_id] = "RED"
            
            if target_index is not None:
                self.active_index = target_index
            else:
                self.active_index = (self.active_index + 1) % len(self.zone_ids)
                
            next_zone_id = self.zone_ids[self.active_index]
            self.states[next_zone_id] = "GREEN"
            
            # Initial calculation for the new green phase
            count = self.lane_counts.get(next_zone_id, 0)
            self.duration = self.calculate_green_time(count)
            
        # If somehow RED (shouldn't happen in this logic flow), recover
        elif current_state == "RED":
            self.states[current_zone_id] = "GREEN"
            self.duration = self.min_green

    def force_green(self, zone_id):
        if zone_id in self.zone_ids:
            idx = self.zone_ids.index(zone_id)
            current_zone = self.zone_ids[self.active_index]
            if current_zone != zone_id:
                self.states[current_zone] = "RED"
                self.active_index = idx
                self.states[zone_id] = "GREEN"
            elif self.states[zone_id] != "GREEN":
                self.states[zone_id] = "GREEN"
            self.start_time = time.time()
            self.duration = 15

    def force_red(self, zone_id):
        if zone_id in self.zone_ids:
            idx = self.zone_ids.index(zone_id)
            if self.active_index == idx and self.states[zone_id] in ["GREEN", "YELLOW"]:
                self.states[zone_id] = "YELLOW"
                self.start_time = time.time()
                self.duration = 2
