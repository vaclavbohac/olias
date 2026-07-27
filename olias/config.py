"""Canonical constants: route, climb markers, and the calibrated Rider Model."""

from pathlib import Path

from olias.physics import RiderModel
from olias.profile import RouteProfile, Segment

RESOURCES = Path(__file__).parent.parent / "resources"
ROUTE_CSV = RESOURCES / "olias-route.csv"

# The Climb: from where the sustained ascent begins to the 525 m shoulder.
# The route then descends ~50 m into Olias village (the turnaround, in a
# saddle at 477 m) — the climb must end at the shoulder, not the village.
CLIMB = Segment(start_m=8500, end_m=17250)

MASS_KG = 92.3  # 82 rider + 9 bike + 1.3 equipment (weighed 2026-07)
CRR = 0.0122  # fitted by tools/calibrate.py against ride 001 on the Climb
CDA_M2 = 0.32  # road default; not identifiable at climbing speeds


def default_rider_model() -> RiderModel:
    return RiderModel(mass_kg=MASS_KG, crr=CRR, cda_m2=CDA_M2)


def load_route_profile() -> RouteProfile:
    return RouteProfile.load(ROUTE_CSV, climb=CLIMB)
