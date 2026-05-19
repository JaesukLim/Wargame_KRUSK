"""Lanchester Square Law integration helpers."""

from __future__ import annotations

from dataclasses import dataclass


def compute_lanchester_step(
    a_strength: float,
    b_strength: float,
    dt: float,
    k_ab: float,
    k_ba: float,
    terrain_factor_a: float = 1.0,
    terrain_factor_b: float = 1.0,
    fatigue_a: float = 1.0,
    fatigue_b: float = 1.0,
) -> tuple[float, float]:
    """Discrete step for two opposing tank groups.

    Uses square-law form:
        dA/dt = -k_ba * B * B_effectiveness
        dB/dt = -k_ab * A * A_effectiveness

    Naming convention:
        k_ab = lethality of force A against force B
        k_ba = lethality of force B against force A

    Terrain and fatigue factors modify the firing side, not the target side.
    """

    if a_strength <= 0 or b_strength <= 0:
        return max(a_strength, 0.0), max(b_strength, 0.0)

    loss_a = k_ba * b_strength * dt * terrain_factor_b * fatigue_b
    loss_b = k_ab * a_strength * dt * terrain_factor_a * fatigue_a

    new_a = max(0.0, a_strength - loss_a)
    new_b = max(0.0, b_strength - loss_b)
    return new_a, new_b


@dataclass
class LanchesterResult:
    attacker_new: float
    defender_new: float
    kill_a: float
    kill_b: float

    @property
    def total_kill(self) -> float:
        return self.kill_a + self.kill_b


def square_step_with_report(
    a_strength: float,
    b_strength: float,
    dt: float,
    k_ab: float,
    k_ba: float,
    terrain_factor_a: float = 1.0,
    terrain_factor_b: float = 1.0,
    fatigue_a: float = 1.0,
    fatigue_b: float = 1.0,
) -> LanchesterResult:
    if a_strength <= 0 or b_strength <= 0:
        return LanchesterResult(max(a_strength, 0.0), max(b_strength, 0.0), 0.0, 0.0)

    new_a, new_b = compute_lanchester_step(
        a_strength,
        b_strength,
        dt,
        k_ab,
        k_ba,
        terrain_factor_a,
        terrain_factor_b,
        fatigue_a,
        fatigue_b,
    )
    return LanchesterResult(
        attacker_new=new_a,
        defender_new=new_b,
        kill_a=a_strength - new_a,
        kill_b=b_strength - new_b,
    )
