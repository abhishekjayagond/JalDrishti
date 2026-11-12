from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors


def build_knn_graph(nodes: pd.DataFrame, k: int = 8) -> np.ndarray:
    nodes = nodes.sort_values("station_id").reset_index(drop=True)
    latlon = np.radians(nodes[["latitude", "longitude"]].to_numpy(float))
    n = len(nodes)
    if n < 2:
        raise ValueError("At least two stations are required")
    k = min(k, n - 1)
    nn = NearestNeighbors(n_neighbors=k + 1, metric="haversine").fit(latlon)
    dist, ind = nn.kneighbors(latlon)
    A = np.zeros((n, n), dtype=np.float32)
    sigma = float(np.median(dist[:, 1:])) + 1e-8
    for i in range(n):
        for d, j in zip(dist[i, 1:], ind[i, 1:]):
            w = float(np.exp(-((d / sigma) ** 2)))
            A[i, j] = max(A[i, j], w)
            A[j, i] = max(A[j, i], w)
    np.fill_diagonal(A, 1.0)
    A = A / (A.sum(axis=1, keepdims=True) + 1e-8)
    return A


def save_graph(nodes: pd.DataFrame, A: np.ndarray, npy: Path, order_json: Path) -> None:
    npy.parent.mkdir(parents=True, exist_ok=True)
    np.save(npy, A)
    with order_json.open("w", encoding="utf-8") as f:
        json.dump(nodes.sort_values("station_id")["station_id"].tolist(), f, indent=2)
