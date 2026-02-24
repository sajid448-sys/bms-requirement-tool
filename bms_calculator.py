#!/usr/bin/env python3
"""
BMS requirement snippet generator.

Computes required usable capacity, average C-rate during eclipse, and
recommended SOC operating window for two mission cases. Aligned with
concepts from NASA BMS (MSC-TOPS-40) and Aerospace TOR-2013-00295
(Li-ion power subsystem architectures).
"""

from dataclasses import dataclass, field
from typing import Literal
import json

@dataclass
class MissionInputs:
    """User-supplied mission parameters."""
    orbital_period_min: float   # min
    eclipse_duration_min: float  # min
    average_payload_power_W: float  # W
    nominal_battery_voltage_V: float  # V


@dataclass
class MissionCaseConfig:
    """Config for one mission class (short-lived vs long-lived)."""
    name: str
    description: str
    capacity_margin: float  # e.g. 1.15 = 15% margin
    soc_min_end_of_eclipse: float  # min SOC at end of eclipse (0–1)
    soc_max_charge: float  # max SOC at end of charge (0–1)
    reserve_fraction: float  # energy reserve / usable (e.g. 0.25 for GEO)


@dataclass
class BMSRequirementSnippet:
    """Computed BMS requirement snippet for one mission case."""
    case_name: str
    case_description: str
    inputs: dict
    required_usable_capacity_Wh: float
    required_usable_capacity_Ah: float
    average_c_rate_during_eclipse: float  # C (e.g. 1.5 = 1.5C)
    soc_operating_window: dict  # {"min": 0.25, "max": 0.90, "min_end_of_eclipse": 0.30}
    margin_and_reserve: dict
    snippet_md: str = field(default="")
    snippet_json: str = field(default="")

SHORT_LIVED_HIGH_POWER = MissionCaseConfig(
    name="short_lived_high_power",
    description="Short-lived, high-power (e.g. LEO, high DOD acceptable)",
    capacity_margin=1.10,
    soc_min_end_of_eclipse=0.20,  
    soc_max_charge=1.00,
    reserve_fraction=0.10,
)

LONG_LIVED_LOW_POWER = MissionCaseConfig(
    name="long_lived_low_power",
    description="Long-lived, low-power (e.g. GEO, conservative for life)",
    capacity_margin=1.20,
    soc_min_end_of_eclipse=0.30,   
    soc_max_charge=0.90,          
    reserve_fraction=0.25,
)

def energy_during_eclipse_Wh(P_W: float, t_eclipse_min: float) -> float:
    """Energy (Wh) required during eclipse at constant power."""
    return P_W * (t_eclipse_min / 60.0)


def required_usable_capacity_Wh(
    E_eclipse_Wh: float,
    margin: float,
    reserve_fraction: float,
) -> float:
    """
    Usable capacity (Wh) = eclipse energy × margin, with reserve interpreted
    as already reflected in soc_min_end_of_eclipse (reserve_fraction kept for docs).
    """
    return E_eclipse_Wh * margin


def required_usable_capacity_Ah(C_Wh: float, V_nom: float) -> float:
    """Usable capacity in Ah at nominal voltage."""
    return C_Wh / V_nom if V_nom > 0 else 0.0


def average_c_rate_during_eclipse(
    P_W: float,
    V_nom: float,
    C_usable_Ah: float,
) -> float:
    """Average discharge C-rate during eclipse: I/C_usable."""
    if C_usable_Ah <= 0 or V_nom <= 0:
        return 0.0
    I_avg_A = P_W / V_nom
    return I_avg_A / C_usable_Ah


def build_snippet(
    inp: MissionInputs,
    config: MissionCaseConfig,
) -> BMSRequirementSnippet:
    """Build BMS requirement snippet for one mission case."""
    E_eclipse = energy_during_eclipse_Wh(
        inp.average_payload_power_W,
        inp.eclipse_duration_min,
    )
    C_Wh = required_usable_capacity_Wh(
        E_eclipse,
        config.capacity_margin,
        config.reserve_fraction,
    )
    C_Ah = required_usable_capacity_Ah(C_Wh, inp.nominal_battery_voltage_V)
    C_rate = average_c_rate_during_eclipse(
        inp.average_payload_power_W,
        inp.nominal_battery_voltage_V,
        C_Ah,
    )

    soc_window = {
        "min": config.soc_min_end_of_eclipse,
        "max": config.soc_max_charge,
        "min_end_of_eclipse": config.soc_min_end_of_eclipse,
    }

    margin_reserve = {
        "capacity_margin": config.capacity_margin,
        "reserve_fraction": config.reserve_fraction,
    }

    inputs_dict = {
        "orbital_period_min": inp.orbital_period_min,
        "eclipse_duration_min": inp.eclipse_duration_min,
        "average_payload_power_W": inp.average_payload_power_W,
        "nominal_battery_voltage_V": inp.nominal_battery_voltage_V,
    }

    data = {
        "case_name": config.name,
        "case_description": config.description,
        "inputs": inputs_dict,
        "required_usable_capacity_Wh": round(C_Wh, 2),
        "required_usable_capacity_Ah": round(C_Ah, 2),
        "average_c_rate_during_eclipse": round(C_rate, 3),
        "soc_operating_window": soc_window,
        "margin_and_reserve": margin_reserve,
        "eclipse_energy_Wh": round(E_eclipse, 2),
    }

    snippet = BMSRequirementSnippet(
        case_name=config.name,
        case_description=config.description,
        inputs=inputs_dict,
        required_usable_capacity_Wh=round(C_Wh, 2),
        required_usable_capacity_Ah=round(C_Ah, 2),
        average_c_rate_during_eclipse=round(C_rate, 3),
        soc_operating_window=soc_window,
        margin_and_reserve=margin_reserve,
        snippet_md=format_markdown(data),
        snippet_json=json.dumps(data, indent=2),
    )
    return snippet


def calculate_api(
    orbital_period_min: float,
    eclipse_duration_min: float,
    average_payload_power_W: float,
    nominal_battery_voltage_V: float,
) -> dict:
    """
    Compute both mission cases and return API-friendly dict.
    Returns {"short": <snippet_dict>, "long": <snippet_dict>}.
    """
    inp = MissionInputs(
        orbital_period_min=orbital_period_min,
        eclipse_duration_min=eclipse_duration_min,
        average_payload_power_W=average_payload_power_W,
        nominal_battery_voltage_V=nominal_battery_voltage_V,
    )
    short = build_snippet(inp, SHORT_LIVED_HIGH_POWER)
    long_ = build_snippet(inp, LONG_LIVED_LOW_POWER)
    short_dict = json.loads(short.snippet_json)
    long_dict = json.loads(long_.snippet_json)
    short_dict["snippet_md"] = short.snippet_md
    long_dict["snippet_md"] = long_.snippet_md
    return {"short": short_dict, "long": long_dict}


def format_markdown(data: dict) -> str:
    """Format one requirement snippet as Markdown."""
    lines = [
        f"## BMS requirement snippet: {data['case_name']}",
        "",
        f"*{data['case_description']}*",
        "",
        "### Inputs",
        f"- Orbital period: {data['inputs']['orbital_period_min']} min",
        f"- Eclipse duration: {data['inputs']['eclipse_duration_min']} min",
        f"- Average payload power: {data['inputs']['average_payload_power_W']} W",
        f"- Nominal battery voltage: {data['inputs']['nominal_battery_voltage_V']} V",
        "",
        "### Derived requirements",
        f"- **Required usable capacity:** {data['required_usable_capacity_Wh']} Wh ({data['required_usable_capacity_Ah']} Ah)",
        f"- **Average C-rate during eclipse:** {data['average_c_rate_during_eclipse']} C",
        f"- **SOC operating window:** {data['soc_operating_window']['min']*100:.0f}% (min, EOE) to {data['soc_operating_window']['max']*100:.0f}% (max, EOC)",
        f"- **Eclipse energy:** {data['eclipse_energy_Wh']} Wh",
        "",
        "### Margin / reserve",
        f"- Capacity margin: {data['margin_and_reserve']['capacity_margin']}",
        f"- Reserve fraction: {data['margin_and_reserve']['reserve_fraction']}",
    ]
    return "\n".join(lines)

def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="BMS requirement snippet generator")
    p.add_argument("--period", type=float, required=True, help="Orbital period (min)")
    p.add_argument("--eclipse", type=float, required=True, help="Eclipse duration (min)")
    p.add_argument("--power", type=float, required=True, help="Average payload power (W)")
    p.add_argument("--voltage", type=float, required=True, help="Nominal battery voltage (V)")
    p.add_argument("--format", choices=["both", "json", "md"], default="both")
    p.add_argument("--out", type=str, default=None, help="Write snippets to directory (one .json + one .md per case)")
    args = p.parse_args()

    inp = MissionInputs(
        orbital_period_min=args.period,
        eclipse_duration_min=args.eclipse,
        average_payload_power_W=args.power,
        nominal_battery_voltage_V=args.voltage,
    )

    cases = [
        ("Short-lived high-power", SHORT_LIVED_HIGH_POWER),
        ("Long-lived low-power", LONG_LIVED_LOW_POWER),
    ]

    for label, config in cases:
        snippet = build_snippet(inp, config)
        print(f"\n{'='*60}\n{label}\n{'='*60}")
        if args.format in ("both", "md"):
            print(snippet.snippet_md)
        if args.format in ("both", "json"):
            print("\n```json\n" + snippet.snippet_json + "\n```")

        if args.out:
            from pathlib import Path
            out_dir = Path(args.out)
            out_dir.mkdir(parents=True, exist_ok=True)
            base = config.name
            (out_dir / f"{base}.json").write_text(snippet.snippet_json, encoding="utf-8")
            (out_dir / f"{base}.md").write_text(snippet.snippet_md, encoding="utf-8")
            print(f"\nWrote {out_dir / f'{base}.json'} and {out_dir / f'{base}.md'}")


if __name__ == "__main__":
    main()
