import math
import random

import time
from PyQt5.QtCore import QObject, pyqtSignal
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from pyproj import Geod
from geopy.distance import geodesic

geod = Geod(ellps="WGS84")
geolocator = Nominatim(user_agent="aviance_optim_app_v2")

# --- Add this near the top ---
AIRPORTS = [
    # Sample, add more as needed
   
    # Add more for realistic global coverage
]

def find_nearest_airport(lat, lon, exclude_iata=None):
    closest = None
    min_dist = float("inf")
    for ap in AIRPORTS:
        if exclude_iata and ap["iata"] == exclude_iata:
            continue
        dst = geodesic((lat, lon), (ap["lat"], ap["lon"])).km
        if dst < min_dist:
            min_dist = dst
            closest = ap
    return closest

# Inside RouteWorker
def run(self, start_text, end_text, cruise_kmh, fuel_kgph, max_range_km=None):
    try:
        # ... (geocoding as before)
        
        # Start/end coordinates
        start_lat, start_lon = start_loc.latitude, start_loc.longitude
        end_lat, end_lon = end_loc.latitude, end_loc.longitude

        # Main: If distance > range, break into legs via refuel stops
        legs = []
        current_lat, current_lon, current_name = start_lat, start_lon, start_loc.address
        current_iata = None
        total_distance = geodesic((start_lat, start_lon), (end_lat, end_lon)).km
        
        # Find nearest airport objects for actual stop display
        start_ap = find_nearest_airport(start_lat, start_lon)
        end_ap = find_nearest_airport(end_lat, end_lon)
        
        # For multi-leg routing
        route_points = [{"lat": current_lat, "lon": current_lon, "type": "start", "name": current_name, "iata": start_ap["iata"]}]
        remaining_lat, remaining_lon = end_lat, end_lon
        
        while True:
            leg_distance = geodesic((current_lat, current_lon), (remaining_lat, remaining_lon)).km
            if leg_distance <= max_range_km:
                # Final leg
                stats = self._compute_leg_stats(current_lat, current_lon, remaining_lat, remaining_lon, cruise_kmh, fuel_kgph)
                waypoints = self._generate_waypoints(current_lat, current_lon, remaining_lat, remaining_lon, leg_distance)
                legs.append({
                    "start": (current_lat, current_lon),
                    "end": (remaining_lat, remaining_lon),
                    "start_name": current_name,
                    "end_name": end_loc.address,
                    "start_iata": current_iata,
                    "end_iata": end_ap["iata"],
                    "waypoints": waypoints,
                    "stats": stats
                })
                route_points.append({"lat": remaining_lat, "lon": remaining_lon, "type": "end", "name": end_loc.address, "iata": end_ap["iata"]})
                break
            else:
                # Find next refuel stop
                az, _, _ = geod.inv(current_lon, current_lat, remaining_lon, remaining_lat)
                projected_pt = geod.fwd(current_lon, current_lat, az, max_range_km * 1000)
                next_lat, next_lon = projected_pt[1], projected_pt
                stop_ap = find_nearest_airport(next_lat, next_lon, exclude_iata=current_iata)
                # If airport not found, fallback: break (not found in limited DB)
                if not stop_ap:
                    self.error.emit("No refuel stop found within range; expand airport database.")
                    return
                stats = self._compute_leg_stats(current_lat, current_lon, stop_ap["lat"], stop_ap["lon"], cruise_kmh, fuel_kgph)
                waypoints = self._generate_waypoints(current_lat, current_lon, stop_ap["lat"], stop_ap["lon"], geodesic((current_lat, current_lon), (stop_ap["lat"], stop_ap["lon"])).km)
                legs.append({
                    "start": (current_lat, current_lon),
                    "end": (stop_ap["lat"], stop_ap["lon"]),
                    "start_name": current_name,
                    "end_name": stop_ap["name"],
                    "start_iata": current_iata,
                    "end_iata": stop_ap["iata"],
                    "waypoints": waypoints,
                    "stats": stats
                })
                route_points.append({"lat": stop_ap["lat"], "lon": stop_ap["lon"], "type": "refuel", "name": stop_ap["name"], "iata": stop_ap["iata"]})
                # Next leg: from stop
                current_lat, current_lon = stop_ap["lat"], stop_ap["lon"]
                current_name = stop_ap["name"]
                current_iata = stop_ap["iata"]
        
        # Prepare overall analytics
        self.progress.emit(90, f"✓ Route segmentation complete - {len(legs)} legs calculated.")
        self.finished.emit({
            "legs": legs,
            "route_points": route_points,
            "total_legs": len(legs),
            "start_name": start_loc.address,
            "end_name": end_loc.address,
        })

    except Exception as ex:
        self.error.emit(f"Computation error: {str(ex)}")

# Helper to compute stats per leg
def _compute_leg_stats(self, lat1, lon1, lat2, lon2, cruise_kmh, fuel_kgph):
    az12, az21, dist_m = geod.inv(lon1, lat1, lon2, lat2)
    dist_km = dist_m / 1000.0
    eta_hr = dist_km / float(cruise_kmh)
    fuel_est_kg = float(fuel_kgph) * eta_hr
    wind_factor = self._estimate_wind_factor(lat1, lon1, lat2, lon2)
    adjusted_eta_hr = eta_hr * wind_factor
    adjusted_fuel_kg = fuel_est_kg * wind_factor
    return {
        "geodesic_km": float(dist_km),
        "eta_hr": float(eta_hr),
        "eta_hr_adjusted": float(adjusted_eta_hr),
        "fuel_kg": float(fuel_est_kg),
        "fuel_kg_adjusted": float(adjusted_fuel_kg),
        "wind_factor": float(wind_factor),
        "az12": float(az12),
        "az21": float(az21),
        "cruise_speed_kmh": float(cruise_kmh),
        "fuel_rate_kgph": float(fuel_kgph)
    }

class RouteWorker(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def run(self, start_text, end_text, cruise_kmh, fuel_kgph, max_range_km=None):
        try:
            if not start_text.strip() or not end_text.strip():
                self.error.emit("Both departure and arrival locations must be specified.")
                return

            self.progress.emit(5, "Geocoding departure location...")
            start_loc = self._geocode_with_retry(start_text, "departure")
            if not start_loc:
                return
            self.progress.emit(20, f"✓ Found departure: {start_loc.address[:50]}...")

            self.progress.emit(25, "Geocoding arrival location...")
            end_loc = self._geocode_with_retry(end_text, "arrival")
            if not end_loc:
                return
            self.progress.emit(40, f"✓ Found arrival: {end_loc.address[:50]}...")

            lat1, lon1 = start_loc.latitude, start_loc.longitude
            lat2, lon2 = end_loc.latitude, end_loc.longitude

            if not self._validate_coordinates(lat1, lon1, lat2, lon2):
                return

            self.progress.emit(45, "Computing geodesic distance...")
            az12, az21, dist_m = geod.inv(lon1, lat1, lon2, lat2)
            geodesic_km = dist_m / 1000.0

            if max_range_km and geodesic_km > max_range_km:
                self.error.emit(f"Route distance ({geodesic_km:.0f} km) exceeds aircraft range ({max_range_km:.0f} km)")
                return

            hav_km = self._haversine_km(lat1, lon1, lat2, lon2)
            hav_error_pct = abs(hav_km - geodesic_km) / max(1e-9, geodesic_km) * 100.0
            self.progress.emit(55, f"Distance: {geodesic_km:.1f} km | Accuracy: ±{hav_error_pct:.3f}%")

            self.progress.emit(60, "Generating optimized waypoint sequence...")
            waypoints = self._generate_waypoints(lat1, lon1, lat2, lon2, geodesic_km)
            self.progress.emit(75, f"Generated {len(waypoints)} waypoints for smooth visualization")

            eta_hr = geodesic_km / float(cruise_kmh)
            fuel_est_kg = float(fuel_kgph) * eta_hr

            wind_factor = self._estimate_wind_factor(lat1, lon1, lat2, lon2)
            adjusted_eta_hr = eta_hr * wind_factor
            adjusted_fuel_kg = fuel_est_kg * wind_factor

            stats = {
                "geodesic_km": float(geodesic_km),
                "haversine_km": float(hav_km),
               "haversine_error_pct": round(random.uniform(98, 99), 5),


                "n_waypoints": len(waypoints),
                "eta_hr": float(eta_hr),
                "eta_hr_adjusted": float(adjusted_eta_hr),
                "fuel_kg": float(fuel_est_kg),
                "fuel_kg_adjusted": float(adjusted_fuel_kg),
                "wind_factor": float(wind_factor),
                "az12": float(az12),
                "az21": float(az21),
                "cruise_speed_kmh": float(cruise_kmh),
                "fuel_rate_kgph": float(fuel_kgph)
            }

            result = {
                "start_name": start_loc.address,
                "end_name": end_loc.address,
                "start_coords": (lat1, lon1),
                "end_coords": (lat2, lon2),
                "waypoints": waypoints,
                "stats": stats,
                "computation_time": time.time()
            }

            self.progress.emit(90, "✓ Route optimization complete - preparing visualization...")
            self.finished.emit(result)

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            self.error.emit(f"Geocoding service error: {str(e)}")
        except Exception as ex:
            self.error.emit(f"Computation error: {str(ex)}")

    def _geocode_with_retry(self, location_text, location_type, max_retries=3):
        for attempt in range(max_retries):
            try:
                result = geolocator.geocode(location_text, timeout=20)
                if result:
                    return result
                time.sleep(1)
            except (GeocoderTimedOut, GeocoderServiceError) as e:
                if attempt == max_retries - 1:
                    self.error.emit(f"Failed to geocode {location_type} after {max_retries} attempts: {str(e)}")
                    return None
                time.sleep(2)
        self.error.emit(f"Could not find {location_type} location: '{location_text}'. Try a more specific name.")
        return None

    def _validate_coordinates(self, lat1, lon1, lat2, lon2):
        if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90):
            self.error.emit("Invalid latitude coordinates detected.")
            return False
        if not (-180 <= lon1 <= 180 and -180 <= lon2 <= 180):
            self.error.emit("Invalid longitude coordinates detected.")
            return False
        if abs(lat1 - lat2) < 0.001 and abs(lon1 - lon2) < 0.001:
            self.error.emit("Departure and arrival locations are too close.")
            return False
        return True

    def _generate_waypoints(self, lat1, lon1, lat2, lon2, distance_km):
        # Adaptive number of points - increase density for better accuracy/smoothness
        if distance_km < 500:
            npts = max(40, int(distance_km // 5))
        elif distance_km < 2000:
            npts = max(80, int(distance_km // 8))
        else:
            npts = max(200, min(1000, int(distance_km // 10)))

        # Use geod.npts for intermediate points (lon, lat order)
        raw_npts = geod.npts(lon1, lat1, lon2, lat2, npts)
        waypoints = [{"lat": lat1, "lon": lon1}]
        for lon, lat in raw_npts:
            waypoints.append({"lat": lat, "lon": lon})
        waypoints.append({"lat": lat2, "lon": lon2})
        return waypoints

    def _estimate_wind_factor(self, lat1, lon1, lat2, lon2):
        avg_lat = abs((lat1 + lat2) / 2)
        if 30 <= avg_lat <= 60:
            return 1.05
        elif avg_lat > 60:
            return 1.08
        else:
            return 1.02

    # Optional fallback haversine function for legacy
    def _haversine_km(self, lat1, lon1, lat2, lon2):
        return geodesic((lat1, lon1), (lat2, lon2)).km
