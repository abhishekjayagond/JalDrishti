from __future__ import annotations

import copy
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except ImportError:
    torch = None
    class _MockNNModule:
        pass
    nn = type("nn", (), {"Module": _MockNNModule})
    DataLoader = None
    TensorDataset = None

from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

from .metrics import regression_metrics

FEATURES = ["latitude", "longitude", "gwl_lag_1", "gwl_lag_2", "gwl_lag_3", "gwl_lag_4", "years_back_1", "years_back_2", "years_back_3", "years_back_4", "gwl_mean_4", "gwl_std_4", "gwl_slope_4"]


class LSTMRegressor(nn.Module):
    def __init__(self, input_size: int = 2, hidden_size: int = 32):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, batch_first=True)
        self.head = nn.Sequential(nn.Linear(hidden_size, 16), nn.ReLU(), nn.Linear(16, 1))

    def forward(self, x):
        y, _ = self.lstm(x)
        return self.head(y[:, -1]).squeeze(-1)


class STGNNRegressor(nn.Module):
    def __init__(self, input_size: int = 2, hidden: int = 32):
        super().__init__()
        self.node = nn.Linear(input_size, hidden)
        self.gru = nn.GRU(hidden, hidden, batch_first=True)
        self.head = nn.Sequential(nn.Linear(hidden, 16), nn.ReLU(), nn.Linear(16, 1))

    def forward(self, x, A):
        # x [B,T,N,F]
        x = torch.einsum("ij,btjf->btif", A, x)
        x = torch.relu(self.node(x))
        b, t, n, h = x.shape
        x = x.permute(0, 2, 1, 3).reshape(b * n, t, h)
        y, _ = self.gru(x)
        y = self.head(y[:, -1]).reshape(b, n)
        return y


def split_target_years(df: pd.DataFrame):
    """
    Defensible 4-way chronological split:
      - Train:       target years <= 2016 (model fitting & preprocessors)
      - Validation:  target years 2017-2019 (hyperparameter tuning & model selection)
      - Calibration: target years 2020-2022 (conformal prediction residual calibration)
      - Test:        target years >= 2023 (unseen holdout evaluation 2023-2025)
    """
    years = sorted(df.target_year.unique())
    if len(years) < 7:
        raise ValueError("Not enough target years for 4-way chronological split")
    train_years = [int(y) for y in years if y <= 2016]
    val_years = [int(y) for y in years if 2017 <= y <= 2019]
    calib_years = [int(y) for y in years if 2020 <= y <= 2022]
    test_years = [int(y) for y in years if y >= 2023]
    return train_years, val_years, calib_years, test_years


def fit_tabular_models(features: pd.DataFrame, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    train_years, val_years, calib_years, test_years = split_target_years(features)
    cols = FEATURES
    val_results = {}
    calib_results = {}
    test_results = {}
    val_preds = {}
    calib_preds = {}
    test_preds = {}
    
    tr = features[features.target_year.isin(train_years)]
    va = features[features.target_year.isin(val_years)]
    ca = features[features.target_year.isin(calib_years)]
    te = features[features.target_year.isin(test_years)]

    for name, model in [
        ("linear_regression", LinearRegression()),
        ("random_forest", RandomForestRegressor(n_estimators=350, max_depth=16, min_samples_leaf=2, random_state=42, n_jobs=-1)),
    ]:
        # Fit benchmark evaluation model strictly on training observations (<= 2016)
        model.fit(tr[cols], tr.target)
        p_val = model.predict(va[cols])
        p_calib = model.predict(ca[cols])
        p_test = model.predict(te[cols])
        
        val_results[name] = regression_metrics(va.target, p_val)
        calib_results[name] = regression_metrics(ca.target, p_calib)
        test_results[name] = regression_metrics(te.target, p_test)
        
        val_preds[name] = pd.DataFrame({"station_id": va.station_id.to_numpy(), "target_year": va.target_year.to_numpy(), "y_true": va.target.to_numpy(), "prediction": p_val})
        calib_preds[name] = pd.DataFrame({"station_id": ca.station_id.to_numpy(), "target_year": ca.target_year.to_numpy(), "y_true": ca.target.to_numpy(), "prediction": p_calib})
        test_preds[name] = pd.DataFrame({"station_id": te.station_id.to_numpy(), "target_year": te.target_year.to_numpy(), "y_true": te.target.to_numpy(), "prediction": p_test})
        
        joblib.dump(model, out_dir / f"{name}.joblib")

    # Fit dedicated production model on all eligible historical observations through 2025
    prod_lr = LinearRegression()
    prod_lr.fit(features[cols], features.target.to_numpy(float))
    joblib.dump(prod_lr, out_dir / "production_linear_regression.joblib")
        
    return val_results, calib_results, test_results, val_preds, calib_preds, test_preds, train_years, val_years, calib_years, test_years


def _make_sequences(clean: pd.DataFrame, nodes: pd.DataFrame, window: int = 5, train_cutoff_year: int = 2016):
    ids = nodes.sort_values("station_id").station_id.tolist()
    wide = clean[clean.station_id.isin(ids)].pivot(index="year", columns="station_id", values="water_level_mbgl").sort_index().reindex(columns=ids)
    mask = wide.notna().astype(np.float32)
    
    # Strictly leakage-free: compute missing value median imputations ONLY on training years (<= train_cutoff_year)
    train_wide = wide[wide.index <= train_cutoff_year]
    fill = train_wide.median().fillna(train_wide.stack().median())
    vals = wide.fillna(fill).to_numpy(np.float32)
    m = mask.to_numpy(np.float32)
    years = wide.index.to_numpy()
    
    X, y, target_years, ymask = [], [], [], []
    for idx in range(window, len(years)):
        target = vals[idx]
        tm = m[idx]
        X.append(np.stack([vals[idx-window:idx], m[idx-window:idx]], axis=-1))
        y.append(target)
        ymask.append(tm)
        target_years.append(int(years[idx]))
    return np.asarray(X), np.asarray(y), np.asarray(ymask), np.asarray(target_years), ids, fill.to_numpy(np.float32)


def _train_torch(model, X, y, ymask, train_mask, val_mask, criterion_mask=True, epochs=35, batch_size=16, A=None):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    best = float("inf")
    best_state = None
    train_ds = TensorDataset(torch.tensor(X[train_mask]), torch.tensor(y[train_mask]), torch.tensor(ymask[train_mask]))
    loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    A_t = torch.tensor(A, dtype=torch.float32, device=device) if A is not None else None
    for _ in range(epochs):
        model.train()
        for xb, yb, mb in loader:
            xb, yb, mb = xb.to(device), yb.to(device), mb.to(device)
            opt.zero_grad()
            pred = model(xb, A_t) if A_t is not None else model(xb)
            if criterion_mask:
                loss = ((pred - yb) ** 2 * mb).sum() / (mb.sum() + 1e-6)
            else:
                loss = ((pred - yb) ** 2).mean()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        model.eval()
        with torch.no_grad():
            xv = torch.tensor(X[val_mask], device=device)
            pv = model(xv, A_t) if A_t is not None else model(xv)
            yv = torch.tensor(y[val_mask], device=device)
            mv = torch.tensor(ymask[val_mask], device=device)
            vloss = float((((pv - yv) ** 2 * mv).sum() / (mv.sum() + 1e-6)).cpu())
        if vloss < best:
            best = vloss
            best_state = copy.deepcopy(model.state_dict())
    if best_state is not None:
        model.load_state_dict(best_state)
    return model, device


def fit_lstm(clean: pd.DataFrame, nodes: pd.DataFrame, out_dir: Path):
    Xg, yg, mg, ty, ids, fill = _make_sequences(clean, nodes, window=5, train_cutoff_year=2016)
    # Flatten graph samples to node samples.
    X = Xg.transpose(0, 2, 1, 3).reshape(-1, Xg.shape[1], 2)
    y = yg.reshape(-1)
    masks = mg.reshape(-1)
    station_repeat = np.tile(np.arange(len(ids)), len(ty))
    target_year_repeat = np.repeat(ty, len(ids))
    keep = masks > 0
    X, y, target_year_repeat, station_repeat = X[keep], y[keep], target_year_repeat[keep], station_repeat[keep]
    
    # Strictly fit scaler on training sequence data only (<= 2016)
    tr_mask = target_year_repeat <= 2016
    scaler = StandardScaler()
    scaler.fit(X[tr_mask].reshape(-1, 2))
    Xs = scaler.transform(X.reshape(-1, 2)).reshape(X.shape)
    
    tr = target_year_repeat <= 2016
    va = (target_year_repeat >= 2017) & (target_year_repeat <= 2019)
    ca = (target_year_repeat >= 2020) & (target_year_repeat <= 2022)
    te = target_year_repeat >= 2023
    
    torch.manual_seed(42)
    np.random.seed(42)
    model = LSTMRegressor(2)
    model, device = _train_torch(model, Xs, y, np.ones_like(y), tr, va, criterion_mask=False, epochs=35, batch_size=128)
    model.eval()
    
    with torch.no_grad():
        p_val = model(torch.tensor(Xs[va], device=device)).cpu().numpy()
        p_calib = model(torch.tensor(Xs[ca], device=device)).cpu().numpy()
        p_test = model(torch.tensor(Xs[te], device=device)).cpu().numpy()
        
    val_metrics = regression_metrics(y[va], p_val)
    calib_metrics = regression_metrics(y[ca], p_calib)
    test_metrics = regression_metrics(y[te], p_test)
    
    torch.save({"state_dict": model.state_dict(), "scaler_mean": scaler.mean_, "scaler_scale": scaler.scale_}, out_dir / "lstm.pt")
    
    val_pred = pd.DataFrame({"station_id": [ids[i] for i in station_repeat[va]], "target_year": target_year_repeat[va], "y_true": y[va], "prediction": p_val})
    calib_pred = pd.DataFrame({"station_id": [ids[i] for i in station_repeat[ca]], "target_year": target_year_repeat[ca], "y_true": y[ca], "prediction": p_calib})
    test_pred = pd.DataFrame({"station_id": [ids[i] for i in station_repeat[te]], "target_year": target_year_repeat[te], "y_true": y[te], "prediction": p_test})
    
    return val_metrics, calib_metrics, test_metrics, val_pred, calib_pred, test_pred


def fit_stgnn(clean: pd.DataFrame, nodes: pd.DataFrame, A: np.ndarray, out_dir: Path):
    X, y, m, ty, ids, fill = _make_sequences(clean, nodes, window=5, train_cutoff_year=2016)
    
    # Scale groundwater values using strictly the training portion (<= 2016). Mask feature stays 0/1.
    tr_samples = ty <= 2016
    train_vals = X[tr_samples, :, :, 0]
    mu = float(train_vals.mean())
    sigma = float(train_vals.std() + 1e-6)
    Xs = X.copy()
    Xs[..., 0] = (Xs[..., 0] - mu) / sigma
    ys = (y - mu) / sigma
    
    tr = ty <= 2016
    va = (ty >= 2017) & (ty <= 2019)
    ca = (ty >= 2020) & (ty <= 2022)
    te = ty >= 2023
    
    torch.manual_seed(42)
    np.random.seed(42)
    model = STGNNRegressor(2)
    model, device = _train_torch(model, Xs, ys, m, tr, va, criterion_mask=True, epochs=45, batch_size=8, A=A)
    model.eval()
    A_t = torch.tensor(A, dtype=torch.float32, device=device)
    
    with torch.no_grad():
        p_val_raw = model(torch.tensor(Xs[va], device=device), A_t).cpu().numpy() * sigma + mu
        p_calib_raw = model(torch.tensor(Xs[ca], device=device), A_t).cpu().numpy() * sigma + mu
        p_test_raw = model(torch.tensor(Xs[te], device=device), A_t).cpu().numpy() * sigma + mu
        
    truth_val = y[va]
    m_val = m[va]
    val_metrics = regression_metrics(truth_val[m_val > 0], p_val_raw[m_val > 0])
    
    truth_calib = y[ca]
    m_calib = m[ca]
    calib_metrics = regression_metrics(truth_calib[m_calib > 0], p_calib_raw[m_calib > 0])
    
    truth_test = y[te]
    m_test = m[te]
    test_metrics = regression_metrics(truth_test[m_test > 0], p_test_raw[m_test > 0])
    
    torch.save({"state_dict": model.state_dict(), "mu": mu, "sigma": sigma, "window": 5, "hidden": 32}, out_dir / "stgnn.pt")
    
    def _extract_preds(y_arr, m_arr, p_arr, ty_slice):
        records = []
        for si, yr in enumerate(ty_slice):
            for j, sid in enumerate(ids):
                if m_arr[si, j] > 0:
                    records.append((sid, int(yr), float(y_arr[si, j]), float(p_arr[si, j])))
        return pd.DataFrame(records, columns=["station_id", "target_year", "y_true", "prediction"])

    val_pred_df = _extract_preds(y[va], m[va], p_val_raw, ty[va])
    calib_pred_df = _extract_preds(y[ca], m[ca], p_calib_raw, ty[ca])
    test_pred_df = _extract_preds(y[te], m[te], p_test_raw, ty[te])
    
    return val_metrics, calib_metrics, test_metrics, val_pred_df, calib_pred_df, test_pred_df
