# Simulated sessions are recorded as FIT activity files

Each session is written as a standard FIT activity (via fit_tool) into the git-ignored
sessions/ directory: virtual distance/altitude/grade from the engine plus measured
power/HR/cadence at 1 Hz. Chosen over CSV/JSONL because a Session Recording then has
the same shape as a Reference Ride — one telemetry format across the project, the same
parsers and comparison tooling for both, third-party upload (Strava etc.) for free,
and future "ghost" opponents can be sourced from either kind of file.
