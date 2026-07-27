# Position advances via app-side physics, not trainer-reported speed

The Kickr's simulation mode receives only grade/wind/Crr/CdA — no rider mass — so its
reported speed embeds a weight assumption we don't control, and position or climb time
would silently disagree with the rider's real recordings. We instead integrate a small
rider model (`m·dv/dt = P/v − gravity − rolling − aero`) over the power the trainer
measures, with mass configured in the app and Crr/CdA calibratable against the
Reference Rides in resources/. Grade is still sent to the trainer, but only for feel;
trainer-reported speed is diagnostic only. Rejected: replaying the Reference Ride's
clock (effort would not matter) and trusting trainer speed (uncontrolled mass
assumption).
