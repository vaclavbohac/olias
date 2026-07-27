# Olias

An indoor trainer app that simulates the real ride from Málaga to Olías on a Wahoo Kickr, using the rider's own recorded telemetry as the reference.

## Language

**Route Profile**:
The canonical distance-indexed elevation model of the Olías loop (resources/olias-route.csv), synthesized from the reference ride.
_Avoid_: track, course, map

**Reference Ride**:
The recorded real-world ride a simulation is based on or compared against (a FIT file in resources/).
_Avoid_: activity, workout

**Remaining Ascent**:
The sum of positive altitude deltas from the rider's current position to the end of the Route Profile — the headline metric shown during a ride.
_Avoid_: climb left, elevation to go, (high point − current altitude)

**Position**:
The rider's current distance along the Route Profile, advanced by the Rider Model — never by trainer-reported speed.
_Avoid_: location, progress

**Rider Model**:
The physical parameters (rider + bike mass, Crr, CdA) used to compute speed from measured power and grade; calibratable against Reference Rides.
_Avoid_: physics engine, avatar

**Session Recording**:
A simulated ride persisted as a FIT activity file in sessions/, structurally identical to a Reference Ride.
_Avoid_: log, history, result

**The Climb**:
The named segment of the Route Profile covering the sustained ascent, km 8.5 to the 525 m shoulder at km 17.25 (olias/config.py); Olías village itself is the turnaround, in a saddle at 477 m past the climb end.
_Avoid_: the hill, the mountain, segment (unqualified), ending the climb at the village

**Climb Delta**:
Reference Ride's elapsed time minus the rider's elapsed time to reach the same position, both clocks zeroed at the Climb start; positive = rider is ahead. Shown only while on the Climb.
_Avoid_: ghost, gap, difference

**Replay Validation**:
The acceptance test for the Rider Model: feed a Reference Ride's recorded power through it over the Climb and require simulated moving time to match the ride's real moving time (001 in-sample ±2%; other rides out-of-sample with looser, condition-variance bounds).
_Avoid_: backtest, simulation test, full-route replay (unwinnable: power cannot distinguish braking from coasting)

## Relationships

- The **Route Profile** is synthesized from exactly one **Reference Ride** (currently olias-ride-001.fit)
- **Remaining Ascent** is computed from the **Route Profile** alone, never from live sensor altitude
- **Position** advances by integrating the **Rider Model** over measured power; grade sent to the trainer is for feel only
- The **Climb Delta** compares the rider against exactly one **Reference Ride** (default: olias-ride-001.fit)
- A **Session Recording** can later serve wherever a **Reference Ride** is expected (same file shape)

## Example dialogue

> **Dev:** "Can I show **Remaining Ascent** as the summit altitude minus current altitude?"
> **Domain expert:** "No — the route undulates, so you'd undercount. Sum the positive deltas ahead of the rider's position on the **Route Profile**."

## Flagged ambiguities

- "the summit": the profile shows two ~525 m peaks (km 17.2 and km 19.0), but they are the same physical shoulder crossed outbound and homebound on the out-and-back — resolved: "the shoulder" is the Climb end; the village saddle between them is the turnaround.
- Odometers drift between recordings (city routing varies), so cross-ride positions are aligned by GPS proximity to canonical coordinates, never by raw distance.
