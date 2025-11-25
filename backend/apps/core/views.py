import json
import requests
import re

# Django
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from functools import lru_cache

# Third Party
from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

# Local
from core.serializers import (
    HealthSerializer,
    TripPlanRequestSerializer,
    TripPlanResponseSerializer,
)

MAX_DRIVE_SHIFT = 11 * 60
MAX_ON_DUTY_SHIFT = 14 * 60
REQ_BREAK_AFTER = 8 * 60
SLEEPER_SPLIT = 10 * 60
BREAK_DURATION = 30
FUEL_RANGE_MILES = 1000
AVG_MPH = 60

ORS_GEOCODE_URL = "https://api.openrouteservice.org/geocode/search"
ORS_ROUTE_URL = "https://api.openrouteservice.org/v2/directions/driving-hgv"
ORS_API_KEY = settings.OPEN_ROUTE_API_KEY

session = requests.Session()


@extend_schema(
    summary="Health",
    description="Endpoint to get the status of backend",
    tags=["Health"],
    responses=HealthSerializer
)
class HealthAPIView(ListAPIView):
    permission_classes = [AllowAny]
    pagination_class = None

    def list(self, request, *args, **kwargs):
        regex = re.compile("^HTTP_")
        headers = dict(
            (regex.sub("", header), value)
            for (header, value) in request.META.items()
            if header.startswith("HTTP_")
        )
        return JsonResponse({"status": "up", "meta": headers})


@lru_cache(maxsize=200)
def get_coordinates(address):
    """Geocodes an address to [lat, lon]."""
    try:
        params = {
            "api_key": ORS_API_KEY,
            "text": address,
            "size": 1,
            "boundary.country": "US",
        }

        r = session.get(ORS_GEOCODE_URL, params=params)
        r.raise_for_status()

        data = r.json()
        if data.get("features"):
            lon, lat = data["features"][0]["geometry"]["coordinates"]
            return (lat, lon)

    except Exception as e:
        print(f"Geocoding error: {e}")

    return None


def calculate_distance(coord1, coord2):
    """Returns driving distance in miles."""
    try:
        params = {
            "api_key": ORS_API_KEY,
            "start": f"{coord1[1]},{coord1[0]}",
            "end": f"{coord2[1]},{coord2[0]}",
        }

        r = session.get(ORS_ROUTE_URL, params=params)
        r.raise_for_status()

        data = r.json()
        meters = data["features"][0]["properties"]["segments"][0]["distance"]
        return meters * 0.000621371

    except Exception as e:
        print(f"Routing error: {e}")

    return None


def run_hos_simulation(dist_pickup, dist_drop, cycle_used_start):
    logs = []
    day = 1
    day_minutes = 0

    def new_day():
        nonlocal day_minutes, day
        logs.append({"date": f"Day {day}", "miles": 0, "entries": []})
        day += 1
        day_minutes = 0

    new_day()

    def add_entry(status, duration, note):
        nonlocal day_minutes
        duration = int(duration)

        while duration > 0:
            remaining = 1440 - day_minutes
            block = min(remaining, duration)

            logs[-1]["entries"].append(
                {
                    "status": status,
                    "startMinute": day_minutes,
                    "endMinute": day_minutes + block,
                    "duration": block,
                    "note": note,
                }
            )

            day_minutes += block
            duration -= block

            if day_minutes >= 1440:
                new_day()

    MIN_PER_MILE = 60 / AVG_MPH

    def simulate_segment(distance):
        nonlocal logs
        dist_left = distance

        on_duty = 0
        drive = 0
        since_break = 0
        fuel = 0

        while dist_left > 0:
            if fuel >= FUEL_RANGE_MILES:
                add_entry("ON", 30, "Refuel")
                fuel = 0
                continue

            if since_break >= REQ_BREAK_AFTER:
                add_entry("OFF", 30, "30m Break")
                since_break = 0
                continue

            if drive >= MAX_DRIVE_SHIFT or on_duty >= MAX_ON_DUTY_SHIFT:
                add_entry("SB", SLEEPER_SPLIT, "10h Reset")
                drive = on_duty = since_break = 0
                continue

            step = min(dist_left, 60)
            step_minutes = int(step * MIN_PER_MILE)

            add_entry("D", step_minutes, "Driving")

            drive += step_minutes
            on_duty += step_minutes
            since_break += step_minutes
            fuel += step
            dist_left -= step
            logs[-1]["miles"] += step

    add_entry("ON", 30, "Pre-trip")
    simulate_segment(dist_pickup)
    add_entry("ON", 60, "Loading")
    simulate_segment(dist_drop)
    add_entry("ON", 60, "Unloading")
    add_entry("ON", 15, "Post-trip")

    if day_minutes < 1440:
        add_entry("OFF", 1440 - day_minutes, "Off Duty")

    return logs


@extend_schema(
    summary="Generate Trip Plan",
    description="Calculates a compliant ELD route plan based on HOS rules.",
    request=TripPlanRequestSerializer,
    responses={200: TripPlanResponseSerializer},
    tags=["Planning"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def generate_trip_plan(request):
    try:
        # Validate request data using serializer
        serializer = TripPlanRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        data = serializer.validated_data
        start_addr = data["start"]
        pickup_addr = data["pickup"]
        drop_addr = data["dropoff"]
        cycle_used = data["cycleUsed"]

        start = get_coordinates(start_addr)
        pickup = get_coordinates(pickup_addr)
        drop = get_coordinates(drop_addr)

        if not all([start, pickup, drop]):
            return Response({"error": "Invalid address provided."}, status=400)

        dist1 = calculate_distance(start, pickup)
        dist2 = calculate_distance(pickup, drop)

        if dist1 is None or dist2 is None:
            return Response({"error": "Routing API failed."}, status=500)

        total = round(dist1 + dist2)

        logs = run_hos_simulation(dist1, dist2, cycle_used)

        if logs and not logs[-1]["entries"]:
            logs.pop()

        response_data = {
            "status": "success",
            "routeData": {
                "totalMiles": total,
                "locations": [start, pickup, drop],
            },
            "logs": logs,
        }
        return Response(response_data)

    except Exception as e:
        return Response({"error": str(e)}, status=500)
