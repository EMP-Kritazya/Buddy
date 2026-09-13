"""Google Maps: how far away something is, and when to leave for it.

The only Maps-aware file, the same way db.py is the only Postgres-aware one. One API is used -
Routes - because it accepts a plain address string as the destination, so a separate geocoding
step is not needed.

Where "here" comes from: the dashboard reads the browser's geolocation and POSTs it to
/api/users/location, which stores it on the profile. On macOS that is Wi-Fi triangulation, good
to roughly ten metres. The engine cannot work this out on its own - a laptop has no GPS, the
Wi-Fi scanning tools were removed from macOS, and an IP lookup only gets you the city.

Everything here fails soft: no key, no location, or an unreachable API returns a reason rather
than raising, because this runs inside a spoken conversation.
"""
from __future__ import annotations

import asyncio
import logging

from engine.config import LOCATION_MAX_AGE_S, MAPS_API_KEY
from engine.store_helpers import now

log = logging.getLogger("uvicorn.error")

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

# What the user says -> what Routes calls it.
MODES = {"walk": "WALK", "walking": "WALK", "foot": "WALK",
         "drive": "DRIVE", "driving": "DRIVE", "car": "DRIVE",
         "bike": "BICYCLE", "cycling": "BICYCLE", "bicycle": "BICYCLE",
         "transit": "TRANSIT", "bus": "TRANSIT", "train": "TRANSIT"}

# Beyond this, the destination almost certainly resolved to the wrong place.
#
# Routes geocodes a bare address string with no idea where the user is, so "Central Library"
# can land in another state - it answered a 318 km, 72-hour WALK for a building four minutes
# away. A wrong answer delivered confidently is worse than admitting the name was ambiguous,
# so anything past these limits is reported as ambiguous rather than spoken as fact.
IMPLAUSIBLE_KM = {"WALK": 10, "BICYCLE": 40, "TRANSIT": 150, "DRIVE": 500}


async def travel(pool, destination: str, mode: str = "walk") -> dict:
    """How long from where the laptop last was, to `destination`.

    Returns {"ok": True, minutes, km, destination, mode} or {"ok": False, "reason": ...}.
    """
    if not MAPS_API_KEY:
        return {"ok": False, "reason": "no_key",
                "detail": "MAPS_API is not set in .env"}

    profile = await where_am_i(pool)
    if not profile or profile.get("lat") is None:
        return {"ok": False, "reason": "no_location",
                "detail": "Buddy does not know where the laptop is. Open the dashboard once "
                          "and allow location access."}

    age = (now() - profile["location_at"]).total_seconds() if profile["location_at"] else None
    if age is not None and age > LOCATION_MAX_AGE_S:
        return {"ok": False, "reason": "stale_location",
                "detail": f"the last location fix is {age / 3600:.0f} hours old"}

    travel_mode = MODES.get((mode or "walk").strip().lower(), "WALK")
    payload = {
        "origin": {"location": {"latLng": {"latitude": profile["lat"],
                                           "longitude": profile["lng"]}}},
        "destination": {"address": destination},
        "travelMode": travel_mode,
    }
    # Traffic-aware routing is only offered for driving; asking for it on a walk is rejected.
    if travel_mode == "DRIVE":
        payload["routingPreference"] = "TRAFFIC_AWARE"

    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                ROUTES_URL, json=payload,
                headers={"X-Goog-Api-Key": MAPS_API_KEY,
                         "X-Goog-FieldMask": "routes.duration,routes.distanceMeters"})
    except Exception as exc:
        log.warning("maps: request failed (%s: %s)", type(exc).__name__, exc)
        return {"ok": False, "reason": "unreachable", "detail": str(exc)}

    if response.status_code != 200:
        detail = response.text[:160].replace("\n", " ")
        log.warning("maps: HTTP %d %s", response.status_code, detail)
        return {"ok": False, "reason": "api_error", "detail": detail}

    routes = (response.json() or {}).get("routes") or []
    if not routes:
        return {"ok": False, "reason": "no_route",
                "detail": f"no {travel_mode.lower()} route to {destination!r}"}

    route = routes[0]
    seconds = float(str(route.get("duration", "0s")).rstrip("s") or 0)
    km = round(float(route.get("distanceMeters") or 0) / 1000, 1)

    limit = IMPLAUSIBLE_KM.get(travel_mode, 500)
    if km > limit:
        return {"ok": False, "reason": "ambiguous_destination",
                "detail": f"the closest match to {destination!r} is {km} km away, which is "
                          f"not a {travel_mode.lower()} anyone means. Ask which one they meant, "
                          f"or for a fuller address."}

    return {"ok": True, "destination": destination, "mode": travel_mode.lower(),
            "minutes": round(seconds / 60), "km": km}


async def where_am_i(pool) -> dict | None:
    """The best location we have, preferring a fresh one.

    The browser fix is the reliable source, but it only arrives while the dashboard is open.
    If the stored one is missing or stale, try macOS directly first - that works without any
    browser at all, when the terminal holds Location Services permission.
    """
    from engine import db, locate

    profile = await db.get_profile(pool)
    fresh = (
        profile
        and profile.get("lat") is not None
        and profile.get("location_at") is not None
        and (now() - profile["location_at"]).total_seconds() <= LOCATION_MAX_AGE_S
    )
    if fresh:
        return profile

    # Blocking native call with a run loop - keep it off the event loop.
    found = await asyncio.to_thread(locate.fix)
    if found is None:
        return profile        # may be stale or empty; the caller reports which
    await db.save_location(pool, found["lat"], found["lng"], found["accuracy_m"])
    log.info("maps: fix from macOS  %.5f, %.5f  +/-%.0fm",
             found["lat"], found["lng"], found["accuracy_m"])
    return await db.get_profile(pool)
