"""Expanding-window errors for scale/calibration fits; never in-sample residuals."""
import numpy as np
import pandas as pd
from sklearn.base import clone


def chronological_residuals(estimator, X, y, dates, *, min_train_dates=365,
                            block_dates=90, embargo_days=2):
    if min_train_dates<2 or block_dates<1 or embargo_days<1:
        raise ValueError("Invalid chronological cross-fit configuration.")
    dates=pd.Series(pd.to_datetime(dates)).dt.normalize().reset_index(drop=True)
    y=np.asarray(y,dtype=float)
    if len(X)!=len(y) or len(y)!=len(dates) or dates.isna().any() or not np.isfinite(y).all():
        raise ValueError("Mismatched or invalid training rows.")
    unique=np.sort(dates.unique())
    predictions=np.full(len(y),np.nan)
    for start in range(min_train_dates,len(unique),block_dates):
        days=unique[start:start+block_dates]
        train=(dates<=pd.Timestamp(days[0])-pd.Timedelta(days=embargo_days)).to_numpy()
        test=dates.isin(days).to_numpy()
        if dates[train].nunique()<min_train_dates:continue
        model=clone(estimator).fit(X.iloc[np.flatnonzero(train)],y[train])
        predictions[test]=model.predict(X.iloc[np.flatnonzero(test)])
    return pd.DataFrame({"prediction":predictions,"residual":y-predictions,"date":dates})
