
from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------------------
# More sizing terms
# ---------------------------------------------------------------------------

def capacity_after_pack_loss_wh(capacity_wh: float, pack_loss_pct: float) -> float:
    """I²R internal pack losses (fraction 0–1 from percentage)."""
    return capacity_wh * (1.0 - pack_loss_pct / 100.0)


def capacity_after_divergence_wh(capacity_wh: float, divergence_pct: float) -> float:
    """Cell voltage divergence loss (fraction from percentage)."""
    return capacity_wh * (1.0 - divergence_pct / 100.0)


def capacity_after_redundancy_wh(capacity_wh: float, redundancy_n: float) -> float:
    """Redundancy N+1: factor = 1 + N (e.g. N=1 → 2x)."""
    return capacity_wh * (1.0 + redundancy_n)


def capacity_after_ageing_wh(capacity_wh: float, ageing_pct: float) -> float:
    """Ageing derating (fraction from percentage)."""
    return capacity_wh * (1.0 - ageing_pct / 100.0)


def capacity_after_temp_wh(capacity_wh: float, temp_pct: float) -> float:
    """Temperature derating (fraction from percentage)."""
    return capacity_wh * (1.0 - temp_pct / 100.0)


def effective_capacity_after_anomaly_wh(
    capacity_wh: float, anomaly_reserve_wh: float
) -> float:
    """Subtract anomaly/SAFE mode energy reserve."""
    return max(0.0, capacity_wh - anomaly_reserve_wh)


def sizing_summary(
    base_capacity_wh: float,
    v_nom: float,
    pack_loss_pct: float = 2.0,
    divergence_pct: float = 3.0,
    redundancy_n: float = 1.0,
    ageing_pct: float = 10.0,
    temp_pct: float = 5.0,
    anomaly_wh: float = 20.0,
) -> dict:
    """
    Single sizing summary: apply each term in order for traceability.
    Returns dict with each step and final effective_capacity_Wh / effective_capacity_Ah.
    """
    after_pack = capacity_after_pack_loss_wh(base_capacity_wh, pack_loss_pct)
    after_div = capacity_after_divergence_wh(after_pack, divergence_pct)
    after_red = capacity_after_redundancy_wh(after_div, redundancy_n)
    after_age = capacity_after_ageing_wh(after_red, ageing_pct)
    after_temp = capacity_after_temp_wh(after_age, temp_pct)
    effective_wh = effective_capacity_after_anomaly_wh(after_temp, anomaly_wh)
    effective_ah = effective_wh / v_nom if v_nom > 0 else 0.0

    return {
        "base_capacity_Wh": round(base_capacity_wh, 2),
        "after_pack_loss_Wh": round(after_pack, 2),
        "after_divergence_Wh": round(after_div, 2),
        "after_redundancy_Wh": round(after_red, 2),
        "after_ageing_Wh": round(after_age, 2),
        "after_temp_Wh": round(after_temp, 2),
        "anomaly_reserve_Wh": round(anomaly_wh, 2),
        "effective_capacity_Wh": round(effective_wh, 2),
        "effective_capacity_Ah": round(effective_ah, 2),
    }

def cell_level_outputs(
    effective_capacity_ah: float,
    cell_ah: float,
    series: int,
    parallel: int,
    eol_factor: float = 0.8,
) -> dict:
    """
    Cell count, string configuration, pack capacity at EOL, and implied
    max charge/discharge from C-rate (call charge_discharge_limits for actual limits).
    """
    series = max(1, int(series))
    parallel = max(1, int(parallel))
    total_cells = series * parallel
    string_config = f"{series}s × {parallel}p"
    pack_capacity_ah = cell_ah * parallel * eol_factor

    return {
        "cell_capacity_Ah": round(cell_ah, 2),
        "series": series,
        "parallel": parallel,
        "total_cells": total_cells,
        "string_config": string_config,
        "pack_capacity_Ah": round(pack_capacity_ah, 2),
        "eol_factor": round(eol_factor, 2),
    }

def charge_discharge_limits(
    pack_capacity_ah: float,
    series: int,
    eocv_per_cell_v: float = 4.2,
    eodv_per_cell_v: float = 3.0,
    c_rate_charge: float = 0.5,
    c_rate_discharge: float = 2.0,
) -> dict:
    """
    Max charge/discharge current, EOCV/EODV at pack level, C-rate limits.
    """
    max_charge_a = pack_capacity_ah * c_rate_charge
    max_discharge_a = pack_capacity_ah * c_rate_discharge
    eocv_pack = eocv_per_cell_v * series
    eodv_pack = eodv_per_cell_v * series

    return {
        "max_charge_current_A": round(max_charge_a, 2),
        "max_discharge_current_A": round(max_discharge_a, 2),
        "eocv_pack_V": round(eocv_pack, 2),
        "eodv_pack_V": round(eodv_pack, 2),
        "c_rate_charge": round(c_rate_charge, 2),
        "c_rate_discharge": round(c_rate_discharge, 2),
        "taper_note": "Taper/step charge per mission profile (e.g. constant current then constant voltage to EOCV).",
    }


def named_requirements(limits: dict) -> List[str]:
    """Emit named requirements REQ-BMS-001, REQ-BMS-002, ... for the snippet."""
    return [
        f"REQ-BMS-001: Max charge current (A): {limits['max_charge_current_A']}",
        f"REQ-BMS-002: Max discharge current (A): {limits['max_discharge_current_A']}",
        f"REQ-BMS-003: End-of-charge voltage, pack (V): {limits['eocv_pack_V']}",
        f"REQ-BMS-004: End-of-discharge voltage, pack (V): {limits['eodv_pack_V']}",
        f"REQ-BMS-005: Max charge C-rate: {limits['c_rate_charge']}C",
        f"REQ-BMS-006: Max discharge C-rate: {limits['c_rate_discharge']}C",
        f"REQ-BMS-007: {limits['taper_note']}",
    ]

def compute_advanced(
    base_capacity_wh: float,
    v_nom: float,
    # Sizing terms
    pack_loss_pct: float = 2.0,
    divergence_pct: float = 3.0,
    redundancy_n: float = 1.0,
    ageing_pct: float = 10.0,
    temp_pct: float = 5.0,
    anomaly_wh: float = 20.0,
    # Cell level
    cell_ah: float = 5.0,
    series: int = 8,
    parallel: int = 1,
    eol_factor: float = 0.8,
    # Charge/discharge
    eocv_per_cell_v: float = 4.2,
    eodv_per_cell_v: float = 3.0,
    c_rate_charge: float = 0.5,
    c_rate_discharge: float = 2.0,
) -> dict:
    """
    Run all advanced steps and return one structure: sizing_summary, cell_level,
    charge_discharge_limits, named_requirements (list of strings).
    """
    sizing = sizing_summary(
        base_capacity_wh,
        v_nom,
        pack_loss_pct=pack_loss_pct,
        divergence_pct=divergence_pct,
        redundancy_n=redundancy_n,
        ageing_pct=ageing_pct,
        temp_pct=temp_pct,
        anomaly_wh=anomaly_wh,
    )
    cell = cell_level_outputs(
        sizing["effective_capacity_Ah"],
        cell_ah,
        series,
        parallel,
        eol_factor,
    )
    limits = charge_discharge_limits(
        cell["pack_capacity_Ah"],
        cell["series"],
        eocv_per_cell_v=eocv_per_cell_v,
        eodv_per_cell_v=eodv_per_cell_v,
        c_rate_charge=c_rate_charge,
        c_rate_discharge=c_rate_discharge,
    )
    reqs = named_requirements(limits)

    return {
        "sizing_summary": sizing,
        "cell_level": cell,
        "charge_discharge_limits": limits,
        "named_requirements": reqs,
    }
