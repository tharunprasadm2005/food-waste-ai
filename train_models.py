# import pandas as pd
# from sklearn.model_selection import train_test_split
# from sklearn.ensemble import RandomForestRegressor
# from catboost import CatBoostRegressor
# import xgboost as xgb
# import lightgbm as lgb
# from sklearn.preprocessing import LabelEncoder
# from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
# import joblib
# import os
# import numpy as np

# # ---------------- LOAD DATA ----------------
# df = pd.read_csv("dataset/food_wastage_data.csv")

# # ---------------- ENCODE CATEGORICAL FEATURES ----------------
# encoders = {}
# for col in df.select_dtypes(include='object').columns:
#     le = LabelEncoder()
#     df[col] = le.fit_transform(df[col])
#     encoders[col] = le

# X = df.drop("Wastage Food Amount", axis=1)
# y = df["Wastage Food Amount"]

# X_train, X_test, y_train, y_test = train_test_split(
#     X, y, test_size=0.2, random_state=42
# )

# # ---------------- RANDOM FOREST ----------------
# rf = RandomForestRegressor(n_estimators=200, random_state=42)
# rf.fit(X_train, y_train)
# rf_pred = rf.predict(X_test)
# rf_metrics = {
#     "MAE": mean_absolute_error(y_test, rf_pred),
#     "RMSE": np.sqrt(mean_squared_error(y_test, rf_pred)),
#     "R2": r2_score(y_test, rf_pred)
# }

# # ---------------- CATBOOST ----------------
# cb = CatBoostRegressor(iterations=300, learning_rate=0.1, depth=6, verbose=False)
# cb.fit(X_train, y_train)
# cb_pred = cb.predict(X_test)
# cb_metrics = {
#     "MAE": mean_absolute_error(y_test, cb_pred),
#     "RMSE": np.sqrt(mean_squared_error(y_test, cb_pred)),
#     "R2": r2_score(y_test, cb_pred)
# }

# # ---------------- XGBOOST ----------------
# xg = xgb.XGBRegressor(n_estimators=200, learning_rate=0.1, max_depth=6, random_state=42)
# xg.fit(X_train, y_train)
# xgb_pred = xg.predict(X_test)
# xgb_metrics = {
#     "MAE": mean_absolute_error(y_test, xgb_pred),
#     "RMSE": np.sqrt(mean_squared_error(y_test, xgb_pred)),
#     "R2": r2_score(y_test, xgb_pred)
# }

# # ---------------- LIGHTGBM ----------------
# lgb_model = lgb.LGBMRegressor(n_estimators=200, learning_rate=0.1, max_depth=6, random_state=42)
# lgb_model.fit(X_train, y_train)
# lgb_pred = lgb_model.predict(X_test)
# lgb_metrics = {
#     "MAE": mean_absolute_error(y_test, lgb_pred),
#     "RMSE": np.sqrt(mean_squared_error(y_test, lgb_pred)),
#     "R2": r2_score(y_test, lgb_pred)
# }

# # ---------------- SAVE MODELS & METRICS ----------------
# os.makedirs("model", exist_ok=True)

# # Save models
# joblib.dump(rf, "model/random_forest.pkl")
# cb.save_model("model/catboost_model.cbm")
# joblib.dump(xg, "model/xgboost.pkl")
# joblib.dump(lgb_model, "model/lightgbm.pkl")

# # Save encoders
# joblib.dump(encoders, "model/encoders.pkl")

# # Save metrics
# joblib.dump(rf_metrics, "model/rf_metrics.pkl")
# joblib.dump(cb_metrics, "model/cb_metrics.pkl")
# joblib.dump(xgb_metrics, "model/xg_metrics.pkl")
# joblib.dump(lgb_metrics, "model/lgb_metrics.pkl")

# print("✅ All models, metrics, and encoders saved successfully")


# import pandas as pd
# from sklearn.model_selection import train_test_split
# from sklearn.ensemble import RandomForestRegressor
# from catboost import CatBoostRegressor
# import xgboost as xgb
# import lightgbm as lgb
# from sklearn.preprocessing import LabelEncoder
# from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
# import joblib
# import os
# import numpy as np

# # ---------------- LOAD DATA ----------------
# df = pd.read_csv("dataset/food_wastage_data.csv")

# # ---------------- ENCODE CATEGORICAL FEATURES ----------------
# encoders = {}
# for col in df.select_dtypes(include="object").columns:
#     le = LabelEncoder()
#     df[col] = le.fit_transform(df[col])
#     encoders[col] = le

# X = df.drop("Wastage Food Amount", axis=1)
# y = df["Wastage Food Amount"]

# X_train, X_test, y_train, y_test = train_test_split(
#     X, y, test_size=0.2, random_state=42
# )

# # ---------------- RANDOM FOREST ----------------
# rf = RandomForestRegressor(n_estimators=200, random_state=42)
# rf.fit(X_train, y_train)
# rf_pred = rf.predict(X_test)
# rf_metrics = {
#     "MAE": mean_absolute_error(y_test, rf_pred),
#     "RMSE": np.sqrt(mean_squared_error(y_test, rf_pred)),
#     "R2": r2_score(y_test, rf_pred),
# }

# # ---------------- CATBOOST ----------------
# # ---------------- CATBOOST (FIXED & OPTIMIZED) ----------------
# # Initialize the base model
# cb = CatBoostRegressor(loss_function="MAE", verbose=False)

# # Define the parameter grid in CatBoost format
# param_grid = {
#     "iterations": [500, 1000],
#     "learning_rate": [0.01, 0.05, 0.1],
#     "depth": [4, 6, 8],
#     "l2_leaf_reg": [1, 3, 5],
# }

# # Use CatBoost's native grid search
# grid_search_result = cb.grid_search(
#     param_grid, X=X_train, y=y_train, cv=3, partition_random_seed=42, plot=False
# )
# # The 'cb' object is now automatically updated with the best parameters
# cb_pred = cb.predict(X_test)

# cb_metrics = {
#     "MAE": mean_absolute_error(y_test, cb_pred),
#     "RMSE": np.sqrt(mean_squared_error(y_test, cb_pred)),
#     "R2": r2_score(y_test, cb_pred),
# }

# print(f"✅ CatBoost Optimized! Best Params: {grid_search_result['params']}")

# # ---------------- XGBOOST ----------------
# xg = xgb.XGBRegressor(n_estimators=200, learning_rate=0.1, max_depth=6, random_state=42)
# xg.fit(X_train, y_train)
# xgb_pred = xg.predict(X_test)
# xgb_metrics = {
#     "MAE": mean_absolute_error(y_test, xgb_pred),
#     "RMSE": np.sqrt(mean_squared_error(y_test, xgb_pred)),
#     "R2": r2_score(y_test, xgb_pred),
# }

# # ---------------- LIGHTGBM ----------------
# lgb_model = lgb.LGBMRegressor(
#     n_estimators=200, learning_rate=0.1, max_depth=6, random_state=42
# )
# lgb_model.fit(X_train, y_train)
# lgb_pred = lgb_model.predict(X_test)
# lgb_metrics = {
#     "MAE": mean_absolute_error(y_test, lgb_pred),
#     "RMSE": np.sqrt(mean_squared_error(y_test, lgb_pred)),
#     "R2": r2_score(y_test, lgb_pred),
# }

# # ---------------- SAVE MODELS & METRICS ----------------
# os.makedirs("model", exist_ok=True)

# # Save models
# joblib.dump(rf, "model/random_forest.pkl")
# cb.save_model("model/catboost_model.cbm")
# joblib.dump(xg, "model/xgboost.pkl")
# joblib.dump(lgb_model, "model/lightgbm.pkl")

# # Save encoders
# joblib.dump(encoders, "model/encoders.pkl")

# # Save metrics
# joblib.dump(rf_metrics, "model/rf_metrics.pkl")
# joblib.dump(cb_metrics, "model/cb_metrics.pkl")
# joblib.dump(xgb_metrics, "model/xg_metrics.pkl")
# joblib.dump(lgb_metrics, "model/lgb_metrics.pkl")

# print("✅ All models, metrics, and encoders saved successfully")

import pandas as pd
import numpy as np
import joblib
import os

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.ensemble import RandomForestRegressor

import xgboost as xgb
import lightgbm as lgb
from catboost import CatBoostRegressor


# ---------------- LOAD DATA ----------------
df = pd.read_csv("dataset/food_wastage_data.csv")

print("Dataset Loaded Successfully")


# ---------------- IDENTIFY CATEGORICAL FEATURES ----------------

# Column names (for encoding)
cat_cols = df.select_dtypes(include=["object"]).columns.tolist()

print("Categorical Column Names:", cat_cols)

# Column indexes (for CatBoost)
cat_features = [df.columns.get_loc(col) for col in cat_cols]

print("Categorical Column Indexes:", cat_features)

# ---------------- CREATE ENCODED COPY FOR OTHER MODELS ----------------
df_encoded = df.copy()

encoders = {}

for col in cat_cols:
    le = LabelEncoder()
    df_encoded[col] = le.fit_transform(df_encoded[col])
    encoders[col] = le

# ---------------- DEFINE FEATURES ----------------
X_encoded = df_encoded.drop("Wastage Food Amount", axis=1)
y = df_encoded["Wastage Food Amount"]

X_cat = df.drop("Wastage Food Amount", axis=1)


# ---------------- TRAIN TEST SPLIT ----------------
X_train_enc, X_test_enc, y_train, y_test = train_test_split(
    X_encoded, y, test_size=0.2, random_state=42
)

X_train_cat, X_test_cat, _, _ = train_test_split(
    X_cat, y, test_size=0.2, random_state=42
)


# ---------------- RANDOM FOREST ----------------
rf = RandomForestRegressor(
    n_estimators=60,
    max_depth=6,
    random_state=42
)

print("Training Random Forest...")
rf.fit(X_train_enc, y_train)

rf_pred = rf.predict(X_test_enc)

rf_metrics = {
    "MAE": mean_absolute_error(y_test, rf_pred),
    "RMSE": np.sqrt(mean_squared_error(y_test, rf_pred)),
    "R2": r2_score(y_test, rf_pred)
}


# ---------------- XGBOOST ----------------
xg = xgb.XGBRegressor(
    n_estimators=60,
    max_depth=3,
    learning_rate=0.2,
    random_state=42
)

print("Training XGBoost...")
xg.fit(X_train_enc, y_train)

xgb_pred = xg.predict(X_test_enc)

xgb_metrics = {
    "MAE": mean_absolute_error(y_test, xgb_pred),
    "RMSE": np.sqrt(mean_squared_error(y_test, xgb_pred)),
    "R2": r2_score(y_test, xgb_pred)
}


# ---------------- LIGHTGBM ----------------
lgb_model = lgb.LGBMRegressor(
    n_estimators=60,
    max_depth=4,
    learning_rate=0.2,
    random_state=42
)

print("Training LightGBM...")
lgb_model.fit(X_train_enc, y_train)

lgb_pred = lgb_model.predict(X_test_enc)

lgb_metrics = {
    "MAE": mean_absolute_error(y_test, lgb_pred),
    "RMSE": np.sqrt(mean_squared_error(y_test, lgb_pred)),
    "R2": r2_score(y_test, lgb_pred)
}


# ---------------- CATBOOST (CATEGORICAL DATA) ----------------
cb = CatBoostRegressor(
    iterations=2000,
    depth=10,
    learning_rate=0.02,
    l2_leaf_reg=2,
    bagging_temperature=0.5,
    random_strength=0.2,
    border_count=254,
    loss_function="RMSE",
    random_seed=42,
    verbose=0
)

print("Training CatBoost...")
cb.fit(
    X_train_cat,
    y_train,
    cat_features=cat_features
)

cb_pred = cb.predict(X_test_cat)

cb_metrics = {
    "MAE": mean_absolute_error(y_test, cb_pred),
    "RMSE": np.sqrt(mean_squared_error(y_test, cb_pred)),
    "R2": r2_score(y_test, cb_pred)
}


# ---------------- PRINT RESULTS ----------------
print("\nModel Performance Comparison\n")

print("Random Forest:", rf_metrics)
print("XGBoost:", xgb_metrics)
print("LightGBM:", lgb_metrics)
print("CatBoost:", cb_metrics)


# ---------------- SAVE MODELS ----------------
os.makedirs("model", exist_ok=True)

joblib.dump(rf, "model/random_forest.pkl")
joblib.dump(xg, "model/xgboost.pkl")
joblib.dump(lgb_model, "model/lightgbm.pkl")
cb.save_model("model/catboost_model.cbm")

joblib.dump(encoders, "model/encoders.pkl")

joblib.dump(rf_metrics, "model/rf_metrics.pkl")
joblib.dump(xgb_metrics, "model/xg_metrics.pkl")
joblib.dump(lgb_metrics, "model/lgb_metrics.pkl")
joblib.dump(cb_metrics, "model/cb_metrics.pkl")

print("\nAll models and metrics saved successfully.")