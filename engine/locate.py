"""Ask macOS where this laptop is, without going through a browser.

Best-effort on purpose. CoreLocation only raises its permission dialog for a bundled
application with a usage description in its Info.plist; a plain Python process started from a
terminal cannot trigger it. It works only when the TERMINAL itself already holds location
permission, which the user grants once in:

    System Settings > Privacy & Security > Location Services > (their terminal app)

When that is not the case this returns None quickly and the browser fix stays the source of
truth. Run it directly to see what it can do:

    venv/bin/python -m engine.locate
"""
from __future__ import annotations

import logging
import time

log = logging.getLogger("uvicorn.error")

AUTHORIZED = (3, 4)          # always, when-in-use
STATUS = {0: "not determined (terminal has not been granted Location Services)",
          1: "restricted", 2: "denied", 3: "authorized always", 4: "authorized when in use"}


def fix(timeout_s: float = 4.0) -> dict | None:
    """A location fix from macOS, or None. Blocking - call it off the event loop."""
    try:
        import CoreLocation
        from Foundation import NSDate, NSRunLoop
    except ImportError:
        return None

    try:
        if not CoreLocation.CLLocationManager.locationServicesEnabled():
            return None
        manager = CoreLocation.CLLocationManager.alloc().init()
        manager.setDesiredAccuracy_(CoreLocation.kCLLocationAccuracyHundredMeters)
        manager.requestWhenInUseAuthorization()
        manager.startUpdatingLocation()

        deadline = time.time() + timeout_s
        while time.time() < deadline:
            NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.25))
            if manager.authorizationStatus() not in AUTHORIZED and manager.location() is None:
                continue
            found = manager.location()
            if found is not None:
                coord = found.coordinate()
                return {"lat": float(coord.latitude), "lng": float(coord.longitude),
                        "accuracy_m": float(found.horizontalAccuracy())}
        return None
    except Exception as exc:
        log.debug("locate: %s: %s", type(exc).__name__, exc)
        return None


def status() -> str:
    try:
        import CoreLocation
    except ImportError:
        return "pyobjc-framework-CoreLocation is not installed"
    manager = CoreLocation.CLLocationManager.alloc().init()
    return STATUS.get(manager.authorizationStatus(), "unknown")


if __name__ == "__main__":
    print("authorization:", status())
    found = fix()
    print("fix:", found if found else
          "none - grant Location Services to your terminal, or open the dashboard instead")
