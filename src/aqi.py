from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

AQI_BANDS = (
    (50.0, "Good", "#10b981"),
    (100.0, "Satisfactory", "#84cc16"),
    (200.0, "Moderate", "#f59e0b"),
    (300.0, "Poor", "#f97316"),
    (400.0, "Very Poor", "#ef4444"),
    (500.0, "Severe", "#991b1b"),
)

AQI_INDEX_BREAKPOINTS = (0.0, 50.0, 100.0, 200.0, 300.0, 400.0)

# pollutant: (averaging-window hours, minimum valid hourly values,
#             concentration breakpoints)
# Concentrations use ug/m3 except CO, which uses mg/m3.
POLLUTANT_SPECS = {
    "PM2.5": (24, 16, (0.0, 30.0, 60.0, 90.0, 120.0, 250.0)),
    "PM10":  (24, 16, (0.0, 50.0, 100.0, 250.0, 350.0, 430.0)),
    "NO2":   (24, 16, (0.0, 40.0, 80.0, 180.0, 280.0, 400.0)),
    "SO2":   (24, 16, (0.0, 40.0, 80.0, 380.0, 800.0, 1600.0)),
    "CO":    (8, 8, (0.0, 1.0, 2.0, 10.0, 17.0, 34.0)),
    "O3":    (8, 8, (0.0, 50.0, 100.0, 168.0, 208.0, 748.0)),
}

POLLUTANT_ALIASES = {
    "PM25": "PM2.5",
    "PM2.5": "PM2.5",
    "PM10": "PM10",
    "NO2": "NO2",
    "SO2": "SO2",
    "CO": "CO",
    "O3": "O3",
    "OZONE": "O3",
}

UNAVAILABLE_COLOR = "#94a3b8"


def _category_for_index(index: float) -> tuple[str, str]:
    for upper, name, color in AQI_BANDS:
        if index <= upper:
            return name, color
    return "Severe", "#991b1b"


def calculate_pollutant_subindex(
    pollutant: str,
    concentration: float,
) -> tuple[float, str, str] | None:
    """Calculate a pollutant-specific sub-index from its concentration."""
    key = POLLUTANT_ALIASES.get(str(pollutant).strip().upper())
    if key is None:
        return None

    try:
        value = float(concentration)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value):
        return None

    value = max(0.0, value)
    points = POLLUTANT_SPECS[key][2]

    # Concentrations beyond the final supplied breakpoint enter the Severe
    # band. The capped extension is an explicit implementation convention.
    if value > points[-1]:
        if key == "PM2.5":
            index = 400.0 + max(
                1.0, (value - 250.0) * (100.0 / 250.0)
            )
        else:
            final_width = points[-1] - points[-2]
            index = 400.0 + max(
                1.0, (value - points[-1]) * (100.0 / final_width)
            )

        index = round(min(500.0, index), 1)
        return index, "Severe", "#991b1b"

    for i in range(1, len(points)):
        if value <= points[i]:
            low_concentration = points[i - 1]
            high_concentration = points[i]
            low_index = AQI_INDEX_BREAKPOINTS[i - 1]
            high_index = AQI_INDEX_BREAKPOINTS[i]

            index = low_index + (
                (high_index - low_index)
                / (high_concentration - low_concentration)
            ) * (value - low_concentration)

            index = round(index, 1)
            category, color = _category_for_index(index)
            return index, category, color

    return 500.0, "Severe", "#991b1b"


def calculate_composite_aqi(
    hourly_values: Mapping[str, Sequence[float | None]],
) -> dict:
    """
    Estimate a historical city-aggregate AQI from pollutant sub-indices.

    Inputs must be chronological hourly city averages, with missing values
    represented by None. Missing measurements are never imputed.
    """
    pollutant_averages: dict[str, float] = {}
    sub_indices: dict[str, dict] = {}

    for pollutant, (window_hours, minimum_hours, _) in POLLUTANT_SPECS.items():
        raw_values = list(hourly_values.get(pollutant, ()))
        window_values = raw_values[-window_hours:]

        valid_values: list[float] = []
        for raw_value in window_values:
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                continue

            if math.isfinite(value) and value >= 0:
                valid_values.append(value)

        if len(valid_values) < minimum_hours:
            continue

        average = sum(valid_values) / len(valid_values)
        result = calculate_pollutant_subindex(pollutant, average)

        if result is None:
            continue

        index, category, color = result
        pollutant_averages[pollutant] = round(average, 3)
        sub_indices[pollutant] = {
            "aqi": index,
            "category": category,
            "color": color,
            "concentration": round(average, 3),
            "valid_hours": len(valid_values),
            "required_hours": minimum_hours,
            "window_hours": window_hours,
        }

    qualifying = len(sub_indices)
    has_particulate = any(
        pollutant in sub_indices for pollutant in ("PM2.5", "PM10")
    )

    basis = (
        "Historical city-hourly aggregate estimate using pollutant "
        "breakpoint interpolation. PM2.5, PM10, NO2 and SO2 require at least "
        "16 valid hourly values in their 24-hour windows; CO and O3 require "
        "8 valid hourly values in their 8-hour windows. Severe-band extension "
        "is an implementation convention. This is not a live or "
        "station-specific official AQI."
    )

    if qualifying < 3 or not has_particulate:
        return {
            "aqi": None,
            "category": "Insufficient data",
            "color": UNAVAILABLE_COLOR,
            "status": "insufficient_data",
            "dominant_pollutant": None,
            "pollutant_averages": pollutant_averages,
            "sub_indices": sub_indices,
            "basis": basis,
        }

    dominant = max(
        sub_indices,
        key=lambda pollutant: sub_indices[pollutant]["aqi"],
    )
    worst = sub_indices[dominant]

    return {
        "aqi": worst["aqi"],
        "category": worst["category"],
        "color": worst["color"],
        "status": "calculated",
        "dominant_pollutant": dominant,
        "pollutant_averages": pollutant_averages,
        "sub_indices": sub_indices,
        "basis": basis,
    }
