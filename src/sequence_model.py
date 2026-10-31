"""
Stage 3b - Optional LSTM sequence model.

The tabular models in ml_models.py treat every sample independently. This module adds a
recurrent model over sliding windows, so the temporal development of a fault (the trend
that the rolling features only partly capture) is used directly.

PyTorch is an optional dependency, exactly like xgboost: if it is not installed,
`train_lstm` returns None and the rest of the pipeline is unaffected.
"""
import numpy as np

try:
    import torch
    from torch import nn
except ImportError:  # optional dependency
    torch = None
    nn = None

WINDOW = 20   # timesteps per sequence
STRIDE = 5    # window step (keeps the tensor size manageable)


def _build_sequences(df, features, scaler, window, stride):
    """Scale the per-run time series, then cut sliding windows -> (X, y).

    Label of a window = failure flag at its last timestep.
    """
    df = df.reset_index(drop=True)
    scaled = scaler.transform(df[features]).astype(np.float32)
    flags = df["fault_flag"].to_numpy()
    xs, ys = [], []
    for idx in df.groupby("run_id").indices.values():
        idx = np.sort(idx)
        for start in range(0, len(idx) - window + 1, stride):
            xs.append(scaled[idx[start:start + window]])
            ys.append(flags[idx[start + window - 1]])
    return np.stack(xs), np.asarray(ys, dtype=np.float32)


if torch is not None:
    class _LSTMNet(nn.Module):
        def __init__(self, n_features, hidden=64):
            super().__init__()
            self.lstm = nn.LSTM(n_features, hidden, batch_first=True)
            self.head = nn.Sequential(nn.Linear(hidden, 32), nn.ReLU(), nn.Linear(32, 1))

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.head(out[:, -1]).squeeze(-1)


def train_lstm(ds, seed=42, window=WINDOW, stride=STRIDE, epochs=8, batch_size=256, lr=1e-3):
    """Train the LSTM on sliding windows and return {model, metrics, window}.

    Returns None when torch is unavailable.
    """
    if torch is None:
        print("torch not installed - skipping LSTM. Run: pip install torch")
        return None

    from .ml_models import _metrics

    torch.manual_seed(seed)
    Xtr, ytr = _build_sequences(ds["train"], ds["features"], ds["scaler"], window, stride)
    Xte, yte = _build_sequences(ds["test"], ds["features"], ds["scaler"], window, stride)

    model = _LSTMNet(len(ds["features"]))
    optim = torch.optim.Adam(model.parameters(), lr=lr)
    # Class imbalance: weight the (rare) pre-fault samples up
    pos_weight = torch.tensor([(ytr == 0).sum() / max(1, (ytr == 1).sum())], dtype=torch.float32)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    Xtr_t, ytr_t = torch.from_numpy(Xtr), torch.from_numpy(ytr)
    n = len(Xtr_t)
    for epoch in range(epochs):
        model.train()
        perm = torch.randperm(n)
        total = 0.0
        for i in range(0, n, batch_size):
            b = perm[i:i + batch_size]
            optim.zero_grad()
            loss = loss_fn(model(Xtr_t[b]), ytr_t[b])
            loss.backward()
            optim.step()
            total += loss.item() * len(b)
        print(f"  LSTM epoch {epoch + 1}/{epochs} - loss {total / n:.4f}")

    model.eval()
    with torch.no_grad():
        logits = model(torch.from_numpy(Xte))
        pred = (torch.sigmoid(logits) >= 0.5).numpy().astype(int)
    return dict(model=model, window=window, metrics=_metrics(yte, pred))
