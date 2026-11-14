"""One-second qualitative simulator for outdoor heat-pump temperatures."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .config import AMBIENT_MAX_C, AMBIENT_MIN_C, ARCHETYPE_COUNT, UnitParameters
from .scenarios import Scenario


@dataclass
class SimulationResult:
    features: dict[str, NDArray]
    truth: dict[str, NDArray]
    ambient_mean_c: float
    relative_humidity_pct: float
    heating_load: float
    fan_speed_fraction: float
    nominal_heating_delta_c: float
    frost_growth_factor: float
    defrost_effectiveness: float
    fault_start_second: int
    fault_severity: float
    defrost_count: int
    defrost_total_seconds: int


def sample_unit_parameters(
    rng: np.random.Generator, unit_archetype: int
) -> UnitParameters:
    """Draw equipment and sensor characteristics independently of class."""
    styles = ("delta_decreases", "delta_increases_then_falls", "delta_stable")
    delta_center = 3.0 + (unit_archetype % 6) * 0.8
    return UnitParameters(
        nominal_delta_c=float(rng.uniform(max(2.5, delta_center - 1.1), min(8.0, delta_center + 1.1))),
        airflow_sensitivity=float(rng.uniform(0.10, 0.42)),
        frost_delta_response=float(rng.uniform(0.25, 1.15)),
        probe_lag_seconds=float(rng.uniform(7.0 + unit_archetype % 4, 17.0 + unit_archetype % 4)),
        ambient_sensor_lag_seconds=float(rng.uniform(2.0 + unit_archetype % 3, 8.0 + unit_archetype % 3)),
        sensor_noise_c=float(rng.uniform(0.025, 0.11)),
        noise_correlation=float(rng.uniform(0.15, 0.78)),
        defrost_threshold=float(rng.uniform(0.18, 0.48)),
        response_style=styles[unit_archetype % len(styles)],
    )


def _bounded_weather(
    rng: np.random.Generator, duration: int, mean_c: float, changing: bool
) -> NDArray[np.float64]:
    weather = np.empty(duration, dtype=float)
    weather[0] = mean_c + rng.normal(0.0, 0.15)
    drift = rng.normal(0.0, 0.00045 if changing else 0.00012)
    weather_state = 0.0
    for second in range(1, duration):
        weather_state = 0.985 * weather_state + rng.normal(0.0, 0.018)
        weather[second] = mean_c + drift * second + weather_state
    return weather


def _sensor_trace(
    target: NDArray[np.float64],
    rng: np.random.Generator,
    lag_seconds: float,
    noise_std: float,
    noise_correlation: float,
) -> NDArray[np.float64]:
    observed = np.empty_like(target)
    observed[0] = target[0]
    noise_state = 0.0
    response = 1.0 / lag_seconds
    for second in range(1, target.size):
        noise_state = (
            noise_correlation * noise_state
            + rng.normal(0.0, noise_std * np.sqrt(1.0 - noise_correlation**2))
        )
        observed[second] = (
            observed[second - 1]
            + response * (target[second] - observed[second - 1])
            + noise_state
        )
    return np.round(observed, 3)


def _fault_severity(rng: np.random.Generator, scenario: Scenario) -> float:
    if scenario.label != "unhealthy":
        return 0.0
    return float(
        rng.uniform(0.12, 0.42)
        if scenario.subtle
        else rng.uniform(0.35, 0.92)
    )


def simulate_snippet(
    rng: np.random.Generator,
    scenario: Scenario,
    duration_seconds: int,
    unit_archetype: int,
) -> SimulationResult:
    """Simulate intake and local discharge-probe signals plus separate truth."""
    if duration_seconds < 2:
        raise ValueError("duration_seconds must be at least 2")
    if not 0 <= unit_archetype < ARCHETYPE_COUNT:
        raise ValueError(f"unit_archetype must be in [0, {ARCHETYPE_COUNT - 1}]")

    unit = sample_unit_parameters(rng, unit_archetype)
    duration = duration_seconds
    seconds = np.arange(duration, dtype=np.int64)
    ambient_mean = float(rng.uniform(AMBIENT_MIN_C, AMBIENT_MAX_C))
    humidity = float(rng.uniform(35.0, 100.0))
    if scenario.name == "steady_mild":
        ambient_mean = float(rng.uniform(4.0, 8.0))
        humidity = float(rng.uniform(35.0, 70.0))
    elif scenario.name == "cold_dry":
        ambient_mean = float(rng.uniform(-15.0, -5.0))
        humidity = float(rng.uniform(35.0, 52.0))
    elif scenario.name == "humid_near_freezing":
        ambient_mean = float(rng.uniform(-2.0, 4.0))
        humidity = float(rng.uniform(70.0, 100.0))
    elif scenario.name == "normal_multiple_defrosts":
        ambient_mean = float(rng.uniform(-5.0, 2.0))
        humidity = float(rng.uniform(80.0, 100.0))
    heating_load = float(rng.uniform(0.18, 0.96))
    base_fan_speed = float(rng.uniform(0.48, 1.0))
    growth_factor = float(rng.uniform(0.72, 1.30))
    fault_severity = _fault_severity(rng, scenario)
    fault_start = (
        int(rng.integers(0, max(1, duration // 3)))
        if fault_severity
        else -1
    )
    weather = _bounded_weather(
        rng,
        duration,
        ambient_mean,
        changing=scenario.name == "changing_weather",
    )
    humidity_trace = np.clip(
        humidity + np.cumsum(rng.normal(0.0, 0.006, duration)), 35.0, 100.0
    )
    ambient_target = weather + rng.normal(0.0, 0.08, duration)
    outside = _sensor_trace(
        ambient_target,
        rng,
        unit.ambient_sensor_lag_seconds,
        unit.sensor_noise_c * 0.48,
        unit.noise_correlation,
    )

    modes = np.full(duration, "heating", dtype="<U10")
    fan_on = np.zeros(duration, dtype=bool)
    fault_active = np.zeros(duration, dtype=bool)
    frost = np.zeros(duration, dtype=float)
    airflow = np.ones(duration, dtype=float)
    capacity = np.ones(duration, dtype=float)
    target_outgoing = np.empty(duration, dtype=float)

    startup_seconds = min(int(rng.integers(25, 241)), max(duration // 5, 1))
    if scenario.name == "normal_startup":
        state = "startup"
    else:
        state = str(rng.choice(("heating", "heating", "heating", "startup", "defrost")))
    if scenario.fault_kind == "no_defrost" and state == "defrost":
        state = "heating"
    state_remaining = (
        startup_seconds
        if state == "startup"
        else (int(rng.integers(35, 130)) if state == "defrost" else 0)
    )
    frost_state = float(rng.uniform(0.0, 0.30))
    if scenario.fault_kind == "no_defrost":
        frost_state = float(rng.uniform(0.14, 0.30))
    initial_frost_for_event = frost_state
    defrost_events: list[tuple[int, int, float, float]] = []
    active_defrost_start = 0 if state == "defrost" else -1
    active_defrost_duration = state_remaining if state == "defrost" else 0
    active_defrost_probe_rise = float(rng.uniform(1.0, 5.5)) if state == "defrost" else 0.0
    heating_since_defrost = 0
    recovery_remaining = 0
    recovery_duration = 0
    cycle_remaining = 0
    load_state = heating_load
    fan_state = base_fan_speed

    for second in range(duration):
        fault_active[second] = fault_start >= 0 and second >= fault_start

        if state == "startup" and state_remaining <= 0:
            state = "heating"
        elif state == "defrost" and state_remaining <= 0:
            if scenario.fault_kind == "ineffective":
                removal_fraction = 0.04 * (1.0 - 0.25 * fault_severity)
            elif scenario.fault_kind == "incomplete":
                removal_fraction = 0.28 * (1.0 - 0.25 * fault_severity)
            else:
                removal_fraction = float(rng.uniform(0.48, 0.88))
            frost_after = frost_state * (1.0 - removal_fraction)
            defrost_events.append(
                (
                    active_defrost_start,
                    second - active_defrost_start,
                    initial_frost_for_event,
                    frost_after,
                )
            )
            frost_state = frost_after
            state = "recovery"
            recovery_duration = int(
                rng.integers(70, 180)
                * (
                    1.0 + 0.9 * fault_severity
                    if scenario.fault_kind == "slow_recovery"
                    else 1.0
                )
            )
            recovery_remaining = recovery_duration
        elif state == "recovery" and recovery_remaining <= 0:
            state = "heating"
        elif state == "off" and cycle_remaining <= 0:
            state = "heating"

        if (
            state == "heating"
            and scenario.fault_kind != "no_defrost"
            and scenario.name in ("normal_cycling", "variable_fan_and_load")
            and cycle_remaining <= 0
            and rng.random() < 0.0009
        ):
            state = "off"
            cycle_remaining = int(rng.integers(70, 300))

        if state == "heating":
            frost_probability = 1.0 / (1.0 + np.exp((weather[second] - 3.0) / 2.8))
            moisture_factor = 0.10 + 0.90 * (humidity_trace[second] - 35.0) / 65.0
            growth = (
                0.000015
                + 0.00014 * frost_probability * moisture_factor * growth_factor
            )
            if fault_active[second] and scenario.fault_kind in (
                "rapid_growth",
                "incomplete",
                "ineffective",
                "no_defrost",
            ):
                growth *= 1.0 + 0.7 * fault_severity
            frost_state = float(
                np.clip(frost_state + growth * rng.uniform(0.45, 1.55), 0.0, 0.98)
            )
            if rng.random() < 0.0008:
                load_state = float(
                    np.clip(load_state + rng.normal(0.0, 0.12), 0.18, 0.96)
                )
            fan_change_probability = 0.0018 if scenario.name == "variable_fan_and_load" else 0.00025
            if rng.random() < fan_change_probability:
                fan_state = float(np.clip(fan_state + rng.normal(0.0, 0.18), 0.38, 1.0))

            style_scale = (
                -0.75
                if unit.response_style == "delta_decreases"
                else (0.35 if unit.response_style == "delta_increases_then_falls" else 0.0)
            )
            frost_response = (
                style_scale * unit.frost_delta_response * frost_state
                + (
                    0.5 * unit.frost_delta_response * frost_state * (1.0 - frost_state)
                    if unit.response_style == "delta_increases_then_falls"
                    else 0.0
                )
            )
            fault_airflow_loss = (
                fault_severity * 0.24
                if scenario.fault_kind == "airflow" and fault_active[second]
                else 0.0
            )
            airflow[second] = float(
                np.clip(
                    fan_state
                    * (1.0 - unit.airflow_sensitivity * frost_state)
                    * (1.0 - fault_airflow_loss),
                    0.28,
                    1.0,
                )
            )
            capacity[second] = float(
                np.clip(
                    (1.0 - 0.36 * frost_state)
                    * (1.0 - fault_severity * 0.12 * fault_active[second]),
                    0.35,
                    1.0,
                )
            )
            delta = (
                unit.nominal_delta_c
                * (0.62 + 0.72 * load_state)
                * (0.72 + 0.28 * airflow[second])
                * capacity[second]
                + frost_response
            )
            if unit.response_style == "delta_increases_then_falls":
                delta += unit.frost_delta_response * 1.4 * frost_state * (1.0 - frost_state)
            delta = float(np.clip(delta, 1.25, 10.0))
            target_outgoing[second] = outside[second] - delta
            fan_on[second] = True
            modes[second] = "heating"
            heating_since_defrost += 1

            trigger_threshold = unit.defrost_threshold
            if scenario.fault_kind == "frequent":
                trigger_threshold *= 0.68
            elif scenario.name == "normal_multiple_defrosts":
                trigger_threshold *= 0.70
            elif scenario.fault_kind in ("incomplete", "ineffective"):
                trigger_threshold *= 0.86
            may_defrost = (
                heating_since_defrost > 450
                and frost_state >= trigger_threshold
                and frost_probability * moisture_factor > 0.12
                and rng.random()
                < (
                    0.075
                    if scenario.fault_kind == "frequent"
                    else (0.06 if scenario.name == "normal_multiple_defrosts" else 0.035)
                )
            )
            if may_defrost:
                initial_frost_for_event = frost_state
                active_defrost_start = second + 1
                active_defrost_duration = int(
                    rng.integers(155, 310)
                    if scenario.fault_kind == "prolonged"
                    else rng.integers(55, 190)
                )
                active_defrost_probe_rise = float(rng.uniform(1.0, 5.5))
                state = "defrost"
                state_remaining = active_defrost_duration
                heating_since_defrost = 0
        elif state == "startup":
            fraction = 1.0 - state_remaining / max(startup_seconds, 1)
            target_outgoing[second] = outside[second] - unit.nominal_delta_c * max(fraction, 0.08)
            fan_on[second] = state_remaining < startup_seconds - 12
            modes[second] = "startup"
            state_remaining -= 1
        elif state == "defrost":
            progress = 1.0 - state_remaining / max(active_defrost_duration, 1)
            # With little airflow, the probe follows local warming and ambient
            # influence; it does not represent a mass-flow-weighted air stream.
            target_outgoing[second] = (
                outside[second]
                + 0.35
                + active_defrost_probe_rise * progress
                + 0.35 * np.sin(second / 29.0)
            )
            fan_on[second] = False
            modes[second] = "defrost"
            state_remaining -= 1
        elif state == "recovery":
            recovery_fraction = 1.0 - recovery_remaining / max(recovery_duration, 1)
            target_outgoing[second] = (
                outside[second] - 0.4 - (unit.nominal_delta_c - 0.4) * max(recovery_fraction, 0.0)
            )
            fan_on[second] = True
            modes[second] = "recovery"
            recovery_remaining -= 1
        else:
            target_outgoing[second] = outside[second]
            fan_on[second] = False
            modes[second] = "off"
            cycle_remaining -= 1

        frost[second] = frost_state

    if state == "defrost" and active_defrost_start >= 0:
        defrost_events.append(
            (
                active_defrost_start,
                duration - active_defrost_start,
                initial_frost_for_event,
                frost_state,
            )
        )
    for start, event_duration, _, _ in defrost_events:
        start = max(start, 0)
        stop = min(start + event_duration, duration)
        if event_duration > 0 and start < duration:
            modes[start:stop] = "defrost"
            fan_on[start:stop] = False

    outgoing = _sensor_trace(
        target_outgoing,
        rng,
        unit.probe_lag_seconds,
        unit.sensor_noise_c,
        unit.noise_correlation,
    )
    defrost_count = sum(1 for _, event_duration, _, _ in defrost_events if event_duration > 0)
    defrost_total = sum(event_duration for _, event_duration, _, _ in defrost_events)
    effectiveness = (
        float(
            np.clip(
                np.mean(
                    [
                        (start_frost - end_frost) / max(start_frost, 0.05)
                        for _, event_duration, start_frost, end_frost in defrost_events
                        if event_duration > 0
                    ]
                ),
                0.0,
                1.0,
            )
        )
        if defrost_events
        else 0.0
    )
    return SimulationResult(
        features={
            "second": seconds,
            "outside_temp_c": outside,
            "outgoing_temp_c": outgoing,
        },
        truth={
            "second": seconds,
            "mode": modes,
            "frost_index": np.round(frost, 5),
            "effective_airflow_fraction": np.round(airflow, 4),
            "fan_on": fan_on,
            "fault_active": fault_active,
            "heat_transfer_capacity": np.round(capacity, 4),
        },
        ambient_mean_c=float(np.mean(outside)),
        relative_humidity_pct=humidity,
        heating_load=heating_load,
        fan_speed_fraction=base_fan_speed,
        nominal_heating_delta_c=unit.nominal_delta_c,
        frost_growth_factor=growth_factor,
        defrost_effectiveness=effectiveness,
        fault_start_second=fault_start,
        fault_severity=fault_severity,
        defrost_count=defrost_count,
        defrost_total_seconds=defrost_total,
    )
