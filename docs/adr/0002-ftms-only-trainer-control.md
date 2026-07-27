# Trainer control via standard FTMS only

The trainer (Kickr 2018) is controlled exclusively through the standard BLE Fitness
Machine Service — grade via "Set Indoor Bike Simulation Parameters" — over `bleak`.
Wahoo's proprietary control point is deliberately not implemented: its one advantage
(setting rider weight on the trainer) is irrelevant because position comes from
app-side physics (ADR-0001), and a single standard protocol keeps the trainer adapter
thin and hardware-swappable. Heart rate uses the standard BLE Heart Rate service.
