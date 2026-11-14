"""Scenario catalogs and latent fault settings; none are feature columns."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    name: str
    label: str
    mechanism: str
    fault_kind: str = "none"
    subtle: bool = False


HEALTHY_SCENARIOS = (
    Scenario("steady_mild", "healthy", "steady operation with modest ambient drift"),
    Scenario("cold_dry", "healthy", "cold, comparatively dry conditions limit frost growth"),
    Scenario("humid_near_freezing", "healthy", "gradual frost accumulation with successful defrost"),
    Scenario("normal_multiple_defrosts", "healthy", "variable, successful defrost cycles"),
    Scenario("normal_startup", "healthy", "startup transient followed by heating"),
    Scenario("normal_cycling", "healthy", "demand-driven compressor and fan cycling"),
    Scenario("changing_weather", "healthy", "weather drift and humidity change"),
    Scenario("variable_fan_and_load", "healthy", "normal fan and load changes resemble faults"),
)

UNHEALTHY_SCENARIOS = (
    Scenario(
        "rapid_frost_accumulation",
        "unhealthy",
        "frost grows faster than this simulator's ordinary baseline",
        "rapid_growth",
    ),
    Scenario(
        "frequent_defrost",
        "unhealthy",
        "short heating intervals and unnecessary-looking defrost attempts",
        "frequent",
    ),
    Scenario(
        "prolonged_defrost",
        "unhealthy",
        "longer reverse-cycle periods with a slow return to heating",
        "prolonged",
    ),
    Scenario(
        "incomplete_defrost",
        "unhealthy",
        "partial frost removal leaves elevated latent frost",
        "incomplete",
    ),
    Scenario(
        "ineffective_defrost",
        "unhealthy",
        "defrost attempts remove little latent frost",
        "ineffective",
    ),
    Scenario(
        "slow_recovery",
        "unhealthy",
        "slow post-defrost temperature recovery",
        "slow_recovery",
        subtle=True,
    ),
    Scenario(
        "frost_related_airflow_restriction",
        "unhealthy",
        "frost affects airflow and heat transfer with varied temperature responses",
        "airflow",
    ),
    Scenario(
        "progressive_frost_degradation",
        "unhealthy",
        "subtle frost-related degradation without an in-window defrost",
        "no_defrost",
        subtle=True,
    ),
)

SCENARIOS_BY_LABEL = {
    "healthy": HEALTHY_SCENARIOS,
    "unhealthy": UNHEALTHY_SCENARIOS,
}


def scenario_by_name(name: str) -> Scenario:
    for scenarios in SCENARIOS_BY_LABEL.values():
        for scenario in scenarios:
            if scenario.name == name:
                return scenario
    raise ValueError(f"Unknown synthetic scenario: {name}")
