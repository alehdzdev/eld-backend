import json
import requests
import re

# Django
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# Third Party
from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

ORS_API_KEY = settings.OPEN_ROUTE_API_KEY
MAX_DRIVE_SHIFT = 11 * 60
MAX_ON_DUTY_SHIFT = 14 * 60
REQ_BREAK_AFTER = 8 * 60
SLEEPER_SPLIT = 10 * 60
BREAK_DURATION = 30
FUEL_RANGE_MILES = 1000
AVG_MPH = 60


@extend_schema(
    summary="Health",
    description="Endpoint to get the status of backend",
    tags=["Health"],
)
class HealthAPIView(ListAPIView):
    permission_classes = [AllowAny]

    def list(self, request, *args, **kwargs):
        regex = re.compile("^HTTP_")
        headers = dict(
            (regex.sub("", header), value)
            for (header, value) in request.META.items()
            if header.startswith("HTTP_")
        )
        return JsonResponse({"status": "up", "meta": headers})


def get_coordinates(address):
    """
    Geocodes an address string to [lat, lon] using OpenRouteService.
    Strictly uses API; requires valid ORS_API_KEY.
    """

    try:
        url = "https://api.openrouteservice.org/geocode/search"
        params = {
            "api_key": ORS_API_KEY,
            "text": address,
            "size": 1,
            "boundary.country": "US",
        }
        response = requests.get(url, params=params)

        if response.status_code == 200:
            data = response.json()
            if data.get("features"):
                lon, lat = data["features"][0]["geometry"]["coordinates"]
                return [lat, lon]
        else:
            print(f"ORS API Error (Geocode): {response.status_code} - {response.text}")

    except Exception as e:
        print(f"Geocoding error for {address}: {e}")

    return None


def calculate_distance(coord1, coord2):
    """
    Calculates driving distance for Heavy Goods Vehicles (Trucks) in miles.
    coord1, coord2 are [lat, lon]
    """
    try:
        start_str = f"{coord1[1]},{coord1[0]}"
        end_str = f"{coord2[1]},{coord2[0]}"

        url = "https://api.openrouteservice.org/v2/directions/driving-hgv"
        params = {"api_key": ORS_API_KEY, "start": start_str, "end": end_str}

        response = requests.get(url, params=params)

        if response.status_code == 200:
            data = response.json()
            if "features" in data:
                meters = data["features"][0]["properties"]["segments"][0]["distance"]
                miles = meters * 0.000621371
                return miles
        else:
            print(f"ORS API Error (Routing): {response.status_code} - {response.text}")

    except Exception as e:
        print(f"Routing error: {e}")

    return None


@csrf_exempt
@require_POST
def generate_trip_plan(request):
    try:
        data = json.loads(request.body)
        start_loc = data.get("start")
        pickup_loc = data.get("pickup")
        dropoff_loc = data.get("dropoff")
        cycle_used = float(data.get("cycleUsed", 0))

        start_coords = get_coordinates(start_loc)
        pickup_coords = get_coordinates(pickup_loc)
        dropoff_coords = get_coordinates(dropoff_loc)
        print(start_coords, pickup_coords, dropoff_coords)

        if not all([start_coords, pickup_coords, dropoff_coords]):
            return JsonResponse(
                {
                    "error": "Could not geocode one of the locations. Please check input spelling."
                },
                status=400,
            )

        dist_start_pick = calculate_distance(start_coords, pickup_coords)
        dist_pick_drop = calculate_distance(pickup_coords, dropoff_coords)

        if dist_start_pick is None or dist_pick_drop is None:
            return JsonResponse(
                {"error": "Could not calculate route distance via API."}, status=500
            )

        total_miles = round(dist_start_pick + dist_pick_drop)

        logs = run_hos_simulation(dist_start_pick, dist_pick_drop, cycle_used)

        response_data = {
            "status": "success",
            "routeData": {
                "totalMiles": total_miles,
                "locations": [start_coords, pickup_coords, dropoff_coords],
            },
            "logs": logs,
        }
        return JsonResponse(response_data)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def run_hos_simulation(dist_to_pickup, dist_to_drop, cycle_used_start):
    """
    Simulates the truck driver's journey while adhering to HOS regulations.
    Returns a list of daily logs.
    """
    generated_logs = []
    current_day_log = {"date": "Day 1", "miles": 0, "entries": []}
    day_minute = 0
    on_duty_shift = 0
    drive_shift = 0
    drive_since_break = 0
    fuel_tank = 0

    def add_log_entry(status, duration, note):
        nonlocal day_minute, current_day_log

        duration = int(duration)
        if duration <= 0:
            return

        if day_minute + duration > 1440:
            remainder = (day_minute + duration) - 1440
            fit = 1440 - day_minute

            current_day_log["entries"].append(
                {
                    "status": status,
                    "startMinute": day_minute,
                    "endMinute": 1440,
                    "duration": fit,
                    "note": note,
                }
            )
            generated_logs.append(current_day_log)

            current_day_log = {
                "date": f"Day {len(generated_logs) + 1}",
                "miles": 0,
                "entries": [],
            }
            day_minute = 0

            add_log_entry(status, remainder, note)
        else:
            current_day_log["entries"].append(
                {
                    "status": status,
                    "startMinute": day_minute,
                    "endMinute": day_minute + duration,
                    "duration": duration,
                    "note": note,
                }
            )
            day_minute += duration

    add_log_entry("ON", 30, "Pre-Trip Inspection")
    on_duty_shift += 30

    def simulate_segment(distance):
        nonlocal \
            on_duty_shift, \
            drive_shift, \
            drive_since_break, \
            fuel_tank, \
            current_day_log

        dist_remaining = distance

        while dist_remaining > 0:
            if fuel_tank >= FUEL_RANGE_MILES:
                add_log_entry("ON", 30, "Refuel")
                on_duty_shift += 30
                fuel_tank = 0
                continue

            if drive_since_break >= REQ_BREAK_AFTER:
                add_log_entry("OFF", 30, "Mandated 30m Break")
                on_duty_shift += 30
                drive_since_break = 0
                continue

            if drive_shift >= MAX_DRIVE_SHIFT or on_duty_shift >= MAX_ON_DUTY_SHIFT:
                add_log_entry("SB", SLEEPER_SPLIT, "10h Reset (Sleeper Berth)")
                on_duty_shift = 0
                drive_shift = 0
                drive_since_break = 0
                continue

            step_dist = min(dist_remaining, 60)
            step_time = (step_dist / AVG_MPH) * 60  # Minutes

            # Optimization: Don't drive if it violates limits in the middle of step
            # (Simplified: we assume we stop exactly at limit in real app)

            add_log_entry("D", step_time, "Driving")

            on_duty_shift += step_time
            drive_shift += step_time
            drive_since_break += step_time
            fuel_tank += step_dist
            current_day_log["miles"] += step_dist
            dist_remaining -= step_dist

    simulate_segment(dist_to_pickup)

    add_log_entry("ON", 60, "Loading at Pickup")
    on_duty_shift += 60

    simulate_segment(dist_to_drop)

    add_log_entry("ON", 60, "Unloading at Dropoff")
    on_duty_shift += 60

    add_log_entry("ON", 15, "Post-Trip Inspection")

    if day_minute < 1440:
        add_log_entry("OFF", 1440 - day_minute, "Off Duty")

    generated_logs.append(current_day_log)

    return generated_logs
