from flask import Flask, request, jsonify
from flask_cors import CORS

import joblib
import pandas as pd

app = Flask(__name__)

model = joblib.load('../model/food_waste_model.pkl')
encoders = joblib.load('../model/encoders.pkl')


@app.route('/predict', methods=['POST'])
def predict():
    data = request.json
    df = pd.DataFrame([data])

    for col, le in encoders.items():
        df[col] = le.transform(df[col])

    prediction = model.predict(df)[0]

    risk = "High" if prediction > 30 else "Medium" if prediction > 15 else "Low"

    return jsonify({
        "predicted_waste": round(prediction, 2),
        "risk_level": risk
    })

if __name__ == '__main__':
    app.run(debug=True)
