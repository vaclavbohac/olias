"""Fit Crr against the in-sample Reference Ride (001) on the Climb.

Mass is measured, never fitted. CdA is not fitted either — at climbing speeds
aero is a few watts, below the fit's resolution — so it stays at the road
default until brake-free fast data exists. After running, copy the fitted
value into olias/config.py (CRR) and re-run the test suite: the replay
validation tests are the guardrail.

Run:  uv run tools/calibrate.py
"""

from olias import config
from olias.physics import RiderModel
from olias.reference import ReferenceRide
from olias.replay import climb_replay_time_s, real_climb_moving_time_s


def main():
    profile = config.load_route_profile()
    rides = {
        name: ReferenceRide.load(config.RESOURCES / f"olias-ride-{name}.fit")
        for name in ("001", "002", "003", "004")
    }

    def error(crr):
        model = RiderModel(mass_kg=config.MASS_KG, crr=crr, cda_m2=config.CDA_M2)
        return climb_replay_time_s(model, rides["001"], profile) - real_climb_moving_time_s(
            rides["001"], profile
        )

    lo, hi = 0.002, 0.040
    for _ in range(30):
        mid = (lo + hi) / 2
        if error(mid) > 0:  # too slow: resistance too high
            hi = mid
        else:
            lo = mid
    crr = (lo + hi) / 2

    print(f"fitted crr = {crr:.4f} (mass fixed at {config.MASS_KG} kg, cda at {config.CDA_M2})")
    print(f"config.py currently has CRR = {config.CRR}")
    model = RiderModel(mass_kg=config.MASS_KG, crr=crr, cda_m2=config.CDA_M2)
    for name, ride in rides.items():
        sim = climb_replay_time_s(model, ride, profile)
        real = real_climb_moving_time_s(ride, profile)
        tag = "in-sample" if name == "001" else "out-of-sample"
        error_pct = (sim / real - 1) * 100
        print(f"ride {name} ({tag}): sim {sim:.0f}s vs real {real:.0f}s ({error_pct:+.1f}%)")


if __name__ == "__main__":
    main()
