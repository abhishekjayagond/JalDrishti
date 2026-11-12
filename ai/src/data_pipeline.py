from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

RAW_COLUMNS = ["state", "district", "block", "village", "latitude", "longitude", "date", "water_level_mbgl"]
SITE_KEY = ["district", "block", "village", "latitude", "longitude"]


def station_id(row: pd.Series) -> str:
    raw = "|".join(str(row[c]).strip() for c in SITE_KEY)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def load_clean(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    missing = set(RAW_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    df = df[RAW_COLUMNS].copy()
    for c in ["latitude", "longitude", "water_level_mbgl"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["year"] = df["date"].dt.year
    df = df.dropna(subset=["district", "block", "village", "latitude", "longitude", "year", "water_level_mbgl"])
    df = df.drop_duplicates().reset_index(drop=True)
    grouped = (
        df.groupby(SITE_KEY + ["year"], as_index=False)
        .agg(water_level_mbgl=("water_level_mbgl", "median"), n_records=("water_level_mbgl", "size"), first_date=("date", "min"))
    )
    grouped["multi_record_flag"] = (grouped["n_records"] > 1).astype(int)
    grouped["station_id"] = grouped.apply(station_id, axis=1)
    return grouped.sort_values(SITE_KEY + ["year"]).reset_index(drop=True)


def candidate_stations(clean: pd.DataFrame, min_years: int = 25) -> pd.DataFrame:
    counts = clean.groupby(SITE_KEY)["year"].nunique().reset_index(name="years")
    first = clean.groupby(SITE_KEY)["year"].min().reset_index(name="first_year")
    last = clean.groupby(SITE_KEY)["year"].max().reset_index(name="last_year")
    out = counts.merge(first, on=SITE_KEY).merge(last, on=SITE_KEY)
    out = out[out.years >= min_years].copy()
    out["station_id"] = out.apply(station_id, axis=1)
    return out.sort_values(["district", "years", "block", "village"], ascending=[True, False, True, True]).reset_index(drop=True)


def build_nodes(clean: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    node_cols = SITE_KEY + ["station_id"]
    return candidates[node_cols].sort_values("station_id").reset_index(drop=True)


def build_wide(clean: pd.DataFrame, nodes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    sub = clean[clean.station_id.isin(nodes.station_id)].copy()
    wide = sub.pivot(index="year", columns="station_id", values="water_level_mbgl").sort_index()
    masks = wide.notna().astype("int8")
    return wide, masks


def consecutive_gaps(clean: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sid, g in clean.groupby("station_id"):
        yrs = sorted(g.year.unique())
        gaps = [b - a for a, b in zip(yrs, yrs[1:])]
        rows.append({
            "station_id": sid,
            "years": len(yrs),
            "first_year": min(yrs),
            "last_year": max(yrs),
            "max_gap": max(gaps, default=0),
            "gap_count": sum(x > 1 for x in gaps),
        })
    return pd.DataFrame(rows)


def build_station_features(clean: pd.DataFrame, nodes: pd.DataFrame, min_history: int = 4) -> pd.DataFrame:
    rows: list[dict] = []
    node_lookup = nodes.set_index("station_id")
    for sid, g in clean[clean.station_id.isin(nodes.station_id)].groupby("station_id"):
        g = g.sort_values("year").copy()
        value = g.set_index("year")["water_level_mbgl"]
        observed_years = sorted(int(y) for y in value.index)
        for target_year in observed_years:
            prior_years = [y for y in observed_years if y < target_year]
            if len(prior_years) < min_history:
                continue
            hist_years = prior_years[-min_history:]
            vals = [float(value[y]) for y in hist_years]
            x = {"station_id": sid, "target_year": target_year, "target": float(value[target_year])}
            for lag, val in enumerate(reversed(vals), start=1):
                x[f"gwl_lag_{lag}"] = val
                x[f"years_back_{lag}"] = float(target_year - hist_years[-lag])
            x["gwl_mean_4"] = float(np.mean(vals))
            x["gwl_std_4"] = float(np.std(vals))
            x["gwl_slope_4"] = float(np.polyfit(np.arange(min_history), np.asarray(vals), 1)[0])
            x["latitude"] = float(node_lookup.loc[sid, "latitude"])
            x["longitude"] = float(node_lookup.loc[sid, "longitude"])
            rows.append(x)
    return pd.DataFrame(rows)
