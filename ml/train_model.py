# python_executor/train_model.py

import pandas as pd
import xgboost as xgb
from sklearn.metrics import root_mean_squared_error
import joblib
import matplotlib.pyplot as plt
import mlflow
import mlflow.xgboost

def train_gas_model():
    """
    Loads data, engineers features, trains an XGBoost model,
    and logs the entire process to MLflow.
    """
    print("Starting model training process with MLflow...")
    mlflow.xgboost.autolog()

    # 1. LOAD DATA (Same as before)
    # ----------------
    data_path = '../data/gas_data.csv'
    df = pd.read_csv(data_path, parse_dates=['hour']).set_index('hour').sort_index()

    # 2. FEATURE ENGINEERING
    # ----------------------
    print("Performing feature engineering...")
    df['target_price_next_hour'] = df['avg_gas_in_gwei'].shift(-1)
    df['hour_of_day'] = df.index.hour
    df['day_of_week'] = df.index.dayofweek
    df['month'] = df.index.month
    df['rolling_avg_24h'] = df['avg_gas_in_gwei'].rolling(window=24).mean()
    df['lag_1h'] = df['avg_gas_in_gwei'].shift(1)

    # --- FIX FOR THE SCHEMA WARNING ---
    # Convert integer columns to float64 to prevent potential schema
    # enforcement errors during inference if data is missing.
    print("Converting integer columns to float64 for schema consistency.")
    int_features = ['hour_of_day', 'day_of_week', 'month']
    df[int_features] = df[int_features].astype('float64')
    # ------------------------------------

    df = df.dropna()
    print("Feature engineering complete.")
    
    # 3. PREPARE DATA FOR MODEL (Same as before)
    # -------------------------
    features = ['avg_gas_in_gwei', 'hour_of_day', 'day_of_week', 'month', 'rolling_avg_24h', 'lag_1h']
    target = 'target_price_next_hour'
    X = df[features]
    y = df[target]

    # 4. TRAIN-TEST SPLIT (Same as before)
    # -------------------
    test_size = int(len(X) * 0.1)
    X_train, X_test = X[:-test_size], X[-test_size:]
    y_train, y_test = y[:-test_size], y[-test_size:]
    
    with mlflow.start_run() as run:
        print(f"MLflow Run ID: {run.info.run_id}")
        
        # 5. MODEL TRAINING (Same as before)
        # -----------------
        print("Training the XGBoost model...")
        model = xgb.XGBRegressor(
            objective='reg:squarederror', 
            n_estimators=1000,
            learning_rate=0.05,
            early_stopping_rounds=50
        )
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False
        )
        print("Model training complete.")

        # 6. EVALUATION (Same as before)
        # -------------
        print("Evaluating model performance...")
        predictions = model.predict(X_test)
        rmse = root_mean_squared_error(y_test, predictions)
        print(f"Model Performance (RMSE on test data): {rmse:.4f} Gwei")
        mlflow.log_metric("final_rmse", rmse)
        
        # 7. VISUALIZE AND LOG ARTIFACT (Same as before)
        # --------------------------------
        print("Creating and logging visualization artifact...")
        fig, ax = plt.subplots(figsize=(15, 6))
        results = pd.DataFrame({'actual': y_test, 'predicted': predictions})
        results.tail(200).plot(ax=ax, title='Actual vs. Predicted Gas Price (Last 200 Hours)')
        ax.set_ylabel("Gas Price (Gwei)")
        ax.grid(True)
        
        plot_path = "predictions_plot.png"
        fig.savefig(plot_path)
        plt.close(fig)
        
        mlflow.log_artifact(plot_path)

        # 8. SAVE THE MODEL (Same as before)
        # -----------------
        print("Model has been automatically logged by MLflow.")

if __name__ == "__main__":
    train_gas_model()