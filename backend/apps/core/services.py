# eldplanner/services.py
import os
import requests
from math import floor
from datetime import datetime, timedelta
from dateutil import tz

from config import settings

OPENROUTE_URL = "https://api.openrouteservice.org/v2/directions/driving-car"
API_KEY = settings.OPEN_ROUTE_API_KEY


def geocode_with_ors(place_name):
    url = "https://api.openrouteservice.org/geocode/search"
    params = {"api_key": API_KEY, "text": place_name, "size": 1}

    try:
        response = requests.get(url, params=params)
        data = response.json()

        # validar que haya features
        features = data.get("features", [])
        if not features:
            raise ValueError(f"No geocode results for: {place_name}")

        coords = features[0]["geometry"]["coordinates"]
        label = features[0]["properties"].get("label", place_name)
        print("ESTA VERGA")
        print(f"Geocoded {place_name}: {coords}, label: {label}")

        return {"lon": coords[0], "lat": coords[1], "label": label}

    except requests.RequestException as e:
        # errores de request HTTP
        raise ValueError(f"Geocoding request failed for {place_name}: {e}")
    except Exception as e:
        # errores de parsing o estructura inesperada
        raise ValueError(f"Geocoding failed for {place_name}: {e}")


def route_with_ors(coords_list):
    url = "https://api.openrouteservice.org/v2/directions/driving-hgv"
    headers = {"Authorization": API_KEY}

    body = {"coordinates": coords_list, "units": "mi"}

    try:
        response = requests.post(url, json=body, headers=headers)
        data = response.json()

        route = data["routes"][0]
        distance_miles = route["summary"]["distance"]
        duration_hours = route["summary"]["duration"]
        return {
            "total_distance": distance_miles,
            "total_duration": duration_hours,
            "geometry": route["geometry"],
            "bbox": route["bbox"],
        }
    except Exception as e:
        print(f"Routing error: {e}")
        return None, None


# --- Planning algorithm ---
def meters_to_miles(m):
    return m / 1609.344


def seconds_to_hours(s):
    return s / 3600.0


def plan_eld_route(
    route_distance_m,
    route_duration_s,
    current_cycle_used,
    avg_speed_mph=55.0,
    max_drive_per_day=11.0,
    max_on_duty_per_day=14.0,
    pickup_time_h=1.0,
    dropoff_time_h=1.0,
    fueling_time_h=1.0,
    fueling_interval_miles=1000.0,
    break_after_continuous_drive=8.0,
    break_duration_h=0.5,
):
    """
    Simula día a día el ELD plan.
    Retorna: list of days with segments.
    """
    total_miles = meters_to_miles(route_distance_m)
    est_driving_hours = total_miles / avg_speed_mph

    # We'll split the trip mile-by-mile allocating chunks until total done.
    miles_remaining = total_miles
    pos_mile = 0.0

    days = []
    day_index = 1

    # initial on-duty used in cycle
    cycle_used = float(current_cycle_used)

    # For simplicity, assume pickup is at origin and two dropoffs: Denver and Chicago.
    # But since user provided only origin, pickup, destination, we will: pickup at start (pickup_time_h),
    # one dropoff at intermediate if detected by waypoint (we'll treat pickup/drops following original request: drop in denver and final destination).
    # To be generic, we add pickup at start and two dropoffs (one at an intermediate mark if route contains a mid-point)
    # In our endpoint the caller specified pickup city and destination, including a dropoff in Denver; the view will pass the required dropoff miles.
    #
    # For the algorithm here, we will not know where Denver is along the route; the view will pass dropoff_mile markers if needed.

    # We'll simulate driving in chunks day-by-day:
    avg_speed = avg_speed_mph
    fuel_next_at = fueling_interval_miles  # next fueling mile marker

    # start each day at 06:00 local (we won't assign concrete timezone offsets; use naive times)
    day_start_time = datetime.combine(
        datetime.utcnow().date(), datetime.min.time()
    ).replace(hour=6, minute=0, second=0)

    # helper to add a segment
    def add_day(day_idx, segments):
        days.append(
            {
                "day": day_idx,
                "segments": segments,
            }
        )

    # We'll track pickup/dropoffs externally; the view will insert dropoff events at the correct mile positions.
    # For this function we'll assume no mid-route dropoffs except final; the view can split route beforehand into legs and call plan per leg.
    # But here we simulate the whole route and will insert: pickup at start, final dropoff at the end, and fueling events when fuel_next_at reached.
    #
    # Implementation approach: consume miles each day up to driving limit, but ensure on-duty (driving + required on-duty events that day) <= max_on_duty_per_day.
    #
    # We'll mark pickup at day 1 start.
    remaining_miles = miles_remaining
    # For event scheduling we will create a simple loop:
    while remaining_miles > 0:
        segments = []
        day_driving_done = 0.0
        day_on_duty = 0.0  # includes driving + pickups/dropoffs/fueling
        # Start day: if day 1, add pickup
        if day_index == 1:
            # pickup on duty
            segments.append(
                {
                    "start_time": "06:00",
                    "end_time": (
                        day_start_time + timedelta(hours=pickup_time_h)
                    ).strftime("%H:%M"),
                    "status": "ON_DUTY",
                    "duration_h": round(pickup_time_h, 2),
                    "miles": 0.0,
                    "notes": "Pickup",
                }
            )
            day_on_duty += pickup_time_h

        # Now drive as much as possible this day
        # maximum driving we can still do today considering on-duty cap:
        max_additional_on_duty = max_on_duty_per_day - day_on_duty
        # from that, driving allowed is min(max_drive_per_day, max_additional_on_duty)
        allowed_drive_today = min(max_drive_per_day, max_additional_on_duty)
        # But if remaining miles convert to fewer hours, adjust
        possible_drive_hours = remaining_miles / avg_speed
        drive_hours_today = min(allowed_drive_today, possible_drive_hours)
        # We'll split driving maybe in two blocks to enforce break after 8h continuous
        blocks = []
        hours_left_to_allocate = drive_hours_today
        while hours_left_to_allocate > 0:
            block = min(hours_left_to_allocate, break_after_continuous_drive)
            blocks.append(block)
            hours_left_to_allocate -= block
            if hours_left_to_allocate > 0:
                # account for mandatory break
                blocks.append(-break_duration_h)  # negative indicates break
        # Build segments from blocks
        current_time = day_start_time + timedelta(hours=0)
        for blk in blocks:
            if blk < 0:
                b = -blk
                segments.append(
                    {
                        "start_time": current_time.strftime("%H:%M"),
                        "end_time": (current_time + timedelta(hours=b)).strftime(
                            "%H:%M"
                        ),
                        "status": "OFF_DUTY",
                        "duration_h": round(b, 2),
                        "miles": 0.0,
                        "notes": "Mandatory break",
                    }
                )
                current_time += timedelta(hours=b)
                day_on_duty += 0.0  # break is off-duty
            else:
                miles_chunk = blk * avg_speed
                if miles_chunk > remaining_miles:
                    miles_chunk = remaining_miles
                    blk = miles_chunk / avg_speed
                segments.append(
                    {
                        "start_time": current_time.strftime("%H:%M"),
                        "end_time": (current_time + timedelta(hours=blk)).strftime(
                            "%H:%M"
                        ),
                        "status": "DRIVING",
                        "duration_h": round(blk, 2),
                        "miles": round(miles_chunk, 2),
                        "notes": "",
                    }
                )
                current_time += timedelta(hours=blk)
                day_driving_done += blk
                day_on_duty += blk
                remaining_miles -= miles_chunk
                pos_mile += miles_chunk
                # check fueling
                if pos_mile >= fuel_next_at and remaining_miles > 0:
                    # insert fueling now (1h)
                    segments.append(
                        {
                            "start_time": current_time.strftime("%H:%M"),
                            "end_time": (
                                current_time + timedelta(hours=fueling_time_h)
                            ).strftime("%H:%M"),
                            "status": "ON_DUTY",
                            "duration_h": round(fueling_time_h, 2),
                            "miles": 0.0,
                            "notes": "Fuel",
                        }
                    )
                    current_time += timedelta(hours=fueling_time_h)
                    day_on_duty += fueling_time_h
                    fuel_next_at += fueling_interval_miles

        # if we finished route and need final dropoff
        if remaining_miles <= 0:
            # final dropoff
            segments.append(
                {
                    "start_time": current_time.strftime("%H:%M"),
                    "end_time": (
                        current_time + timedelta(hours=dropoff_time_h)
                    ).strftime("%H:%M"),
                    "status": "ON_DUTY",
                    "duration_h": round(dropoff_time_h, 2),
                    "miles": 0.0,
                    "notes": "Dropoff final",
                }
            )
            day_on_duty += dropoff_time_h
            current_time += timedelta(hours=dropoff_time_h)

        # End of day: add off duty rest until next day
        # We'll assume driver ends duty and sleeps 10 hours (or remainder to next day 06:00)
        # Compute day total times for reporting
        segments_summary = {
            "start_time_day": "06:00",
            "end_time_day": current_time.strftime("%H:%M"),
            "driving_hours": round(day_driving_done, 2),
            "on_duty_hours": round(day_on_duty, 2),
            "segments": segments,
        }
        add_day(day_index, segments_summary)

        # increment cycle used
        cycle_used += day_on_duty
        # prepare next day
        day_index += 1
        day_start_time = day_start_time + timedelta(days=1)
        # Stop if safety: avoid infinite loop
        if day_index > 30:
            break

    return {
        "total_miles": round(total_miles, 2),
        "estimated_driving_hours": round(est_driving_hours, 2),
        "planned_days": days,
        "final_cycle_used": round(cycle_used, 2),
    }
