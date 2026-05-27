#!/usr/bin/env python3
"""
Analyze whether a Prokhorovka simulation run qualitatively matches the desired
historical pattern:

- Soviet/Red side should not win overwhelmingly.
- Red should suffer substantially larger tank losses than Blue.
- Both sides should retain some combat power.
- Contacts, artillery targeting, and shell impacts should occur.

Inputs:
- A timeseries JSON exported from PowerShell.
- Optionally an events JSON exported from PowerShell.

Example:
python scripts/analyze_historical_run.py \
  --timeseries /mnt/c/Users/myoon/wargame_analysis/historical_v1_timeseries.json \
  --events /mnt/c/Users/myoon/wargame_analysis/historical_v1_events.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def safe_div(a: float, b: float) -> float | None:
    if abs(b) < 1e-12:
        return None
    return a / b


def count_events(events_data: Any) -> dict[str, int]:
    if not events_data:
        return {}

    events = events_data.get("events", events_data if isinstance(events_data, list) else [])
    counts: dict[str, int] = {}

    for e in events:
        cat = str(e.get("category", "unknown"))
        counts[cat] = counts.get(cat, 0) + 1

    return counts


def verdict_label(score: int) -> str:
    if score >= 80:
        return "GOOD historical-style match"
    if score >= 60:
        return "USABLE but needs tuning"
    if score >= 40:
        return "WEAK match"
    return "BAD match"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeseries", required=True, type=Path)
    parser.add_argument("--events", type=Path, default=None)
    args = parser.parse_args()

    frames = load_json(args.timeseries)
    if not isinstance(frames, list) or len(frames) < 2:
        raise ValueError("Timeseries JSON must be a list with at least two frames.")

    events_data = load_json(args.events) if args.events and args.events.exists() else None
    event_counts = count_events(events_data)

    first = frames[0]
    last = frames[-1]

    init_blue_tank = float(first["blue_tank_strength"])
    init_red_tank = float(first["red_tank_strength"])
    final_blue_tank = float(last["blue_tank_strength"])
    final_red_tank = float(last["red_tank_strength"])

    blue_tank_loss = init_blue_tank - final_blue_tank
    red_tank_loss = init_red_tank - final_red_tank

    blue_loss_frac = safe_div(blue_tank_loss, init_blue_tank)
    red_loss_frac = safe_div(red_tank_loss, init_red_tank)
    red_to_blue_loss_ratio = safe_div(red_tank_loss, blue_tank_loss)

    final_red_to_blue_tank_ratio = safe_div(final_red_tank, final_blue_tank)

    max_contacts = max(float(f.get("active_contacts", 0.0)) for f in frames)
    final_contacts = float(last.get("active_contacts", 0.0))

    # Scoring rules for the desired qualitative picture.
    score = 100
    notes: list[str] = []

    # 1. Red should not be annihilated.
    if final_red_tank <= 0:
        score -= 30
        notes.append("BAD: Red tank force was annihilated.")
    elif red_loss_frac is not None and red_loss_frac > 0.80:
        score -= 15
        notes.append("WARNING: Red tank loss fraction is extremely high.")

    # 2. Blue should not be annihilated either.
    if final_blue_tank <= 0:
        score -= 25
        notes.append("BAD: Blue tank force was annihilated; this looks too one-sided.")
    elif blue_loss_frac is not None and blue_loss_frac > 0.60:
        score -= 10
        notes.append("WARNING: Blue tank loss fraction is high.")

    # 3. Desired: Red loses much more than Blue, roughly 3-5x in tank strength loss.
    if red_to_blue_loss_ratio is None:
        score -= 20
        notes.append("BAD: Blue tank loss is nearly zero, so loss ratio cannot match historical pattern.")
    else:
        if 3.0 <= red_to_blue_loss_ratio <= 5.5:
            notes.append("GOOD: Red/Blue tank loss ratio is in the desired 3-5.5 range.")
        elif 2.0 <= red_to_blue_loss_ratio < 3.0 or 5.5 < red_to_blue_loss_ratio <= 7.0:
            score -= 10
            notes.append("OK: Red/Blue tank loss ratio is close but not ideal.")
        else:
            score -= 25
            notes.append("BAD: Red/Blue tank loss ratio is far from the desired historical pattern.")

    # 4. Desired: Red should not win overwhelmingly.
    if final_red_to_blue_tank_ratio is None:
        score -= 20
        notes.append("BAD: Final Blue tank strength is near zero.")
    else:
        if 1.0 <= final_red_to_blue_tank_ratio <= 2.5:
            notes.append("GOOD: Red ends ahead, but not overwhelmingly.")
        elif 0.7 <= final_red_to_blue_tank_ratio < 1.0:
            score -= 10
            notes.append("OK: Blue slightly ahead or near parity; this may still be plausible depending on objective scoring.")
        elif 2.5 < final_red_to_blue_tank_ratio <= 4.0:
            score -= 15
            notes.append("WARNING: Red ends too dominant.")
        else:
            score -= 25
            notes.append("BAD: Final tank balance is too one-sided.")

    # 5. Contacts should occur.
    if max_contacts <= 0:
        score -= 25
        notes.append("BAD: No direct-fire contact occurred.")
    else:
        notes.append(f"GOOD: Direct-fire contacts occurred; max active_contacts = {max_contacts:.0f}.")

    # 6. Artillery/detection system should be active.
    if events_data:
        if event_counts.get("fire_order_pending", 0) <= 0:
            score -= 10
            notes.append("WARNING: No fire_order_pending events found.")
        if event_counts.get("shell_impact", 0) <= 0:
            score -= 10
            notes.append("WARNING: No shell_impact events found.")
        if event_counts.get("engagement_start", 0) <= 0:
            score -= 10
            notes.append("WARNING: No engagement_start events found.")

    score = max(0, min(100, score))

    print("\n=== Historical Fit Report ===")
    print(f"Score: {score}/100  ({verdict_label(score)})")
    print()

    print("[Tank strength]")
    print(f"Initial Blue tank strength : {init_blue_tank:.3f}")
    print(f"Final   Blue tank strength : {final_blue_tank:.3f}")
    print(f"Blue tank loss             : {blue_tank_loss:.3f}", end="")
    if blue_loss_frac is not None:
        print(f"  ({blue_loss_frac*100:.1f}%)")
    else:
        print()

    print(f"Initial Red tank strength  : {init_red_tank:.3f}")
    print(f"Final   Red tank strength  : {final_red_tank:.3f}")
    print(f"Red tank loss              : {red_tank_loss:.3f}", end="")
    if red_loss_frac is not None:
        print(f"  ({red_loss_frac*100:.1f}%)")
    else:
        print()

    print()
    print("[Ratios]")
    print(f"Red / Blue tank loss ratio : {red_to_blue_loss_ratio if red_to_blue_loss_ratio is not None else 'undefined'}")
    print(f"Final Red / Blue tank ratio: {final_red_to_blue_tank_ratio if final_red_to_blue_tank_ratio is not None else 'undefined'}")

    print()
    print("[Contacts]")
    print(f"Max active contacts        : {max_contacts:.0f}")
    print(f"Final active contacts      : {final_contacts:.0f}")

    if event_counts:
        print()
        print("[Event counts]")
        for key in sorted(event_counts):
            print(f"{key:24s}: {event_counts[key]}")

    print()
    print("[Interpretation]")
    for note in notes:
        print(f"- {note}")

    print()
    print("[Tuning direction]")
    if red_to_blue_loss_ratio is not None:
        if red_to_blue_loss_ratio < 3.0:
            print("- Red is not taking enough relative tank loss. Increase Blue effectiveness, improve Blue defensive positioning, or reduce Red armor/morale.")
        elif red_to_blue_loss_ratio > 5.5:
            print("- Red is taking too much relative tank loss. Reduce Blue effectiveness, slow Blue artillery, or improve Red dispersion/pathing.")

    if final_red_to_blue_tank_ratio is not None:
        if final_red_to_blue_tank_ratio > 2.5:
            print("- Red final advantage is too large. Strengthen Blue or reduce Red starting strength/path concentration.")
        elif final_red_to_blue_tank_ratio < 1.0:
            print("- Red does not end ahead. Increase Red starting strength, improve Red paths, or reduce Blue defensive advantage.")

    if max_contacts <= 0:
        print("- Move opposing tank paths closer to the target front line or increase lanchester_range_m.")

    print()


if __name__ == "__main__":
    main()
