# 🍽️ AI-Enabled Food Waste Prediction & Donation Management System

## 📌 Overview

This project is an intelligent, end-to-end platform designed to **predict food surplus** and **optimize food donation distribution**. It leverages **Machine Learning models** and a **full-stack web application** to connect food donors with volunteers and NGOs efficiently.

The system aims to reduce food waste while ensuring surplus food reaches people in need.

---

## 🚀 Features

* 🔍 **Food Surplus Prediction**

  * Uses ML models (Random Forest, XGBoost, LightGBM, CatBoost)
  * Predicts excess food based on historical and real-time data

* 📊 **Donor Analytics Dashboard**

  * Visual insights on donations, trends, and impact
  * Real-time monitoring system

* 🤝 **Smart Volunteer Assignment**

  * Automatically assigns volunteers based on location and availability

* 🌐 **Full-Stack Web Platform**

  * Donation management system
  * Food request and distribution tracking
  * Secure authentication system

* 📦 **End-to-End Workflow**

  * Donor → Prediction → Allocation → Delivery → Impact Reporting

---

## 🛠️ Tech Stack

### 💻 Frontend

* HTML, CSS, JavaScript
* React.js (if used)

### ⚙️ Backend

* Python (Flask)
* RESTful APIs

### 🗄️ Database

* MySQL

### 🤖 Machine Learning

* Scikit-learn
* XGBoost
* LightGBM
* CatBoost

---

## 🧠 Machine Learning Pipeline

1. Data Collection & Preprocessing
2. Feature Engineering
3. Model Training & Evaluation
4. Ensemble Learning Techniques
5. Prediction & Deployment

---

## 📂 Project Structure

```
├── frontend/
├── backend/
├── models/
├── dataset/
├── static/
├── templates/
├── app.py
├── requirements.txt
└── README.md
```

---

## 🔐 Security Note

Sensitive information such as:

* API keys
* Database credentials
* Secret keys

are stored using environment variables and are **not included in this repository**.

---

## ⚙️ Installation & Setup

1. Clone the repository

```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
```

2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate   # (Linux/Mac)
venv\Scripts\activate      # (Windows)
```

3. Install dependencies

```bash
pip install -r requirements.txt
```

4. Setup environment variables
   Create a `.env` file:

```
DB_HOST=
DB_USER=
DB_PASSWORD=
SECRET_KEY=
```

5. Run the application

```bash
python app.py
```

---

## 📈 Future Enhancements

* 📍 Real-time GPS tracking for delivery
* 📱 Mobile application integration
* 🤖 Advanced AI optimization for logistics
* 🌍 Multi-city scalability

---

## 👨‍💻 Author

**Tharun Prasad M**
Full-Stack Developer | AI & Data Science Enthusiast

---

## ⭐ Support

If you like this project:

* Give it a ⭐ on GitHub
* Share with others
* Contribute to improve the system

---

## 📜 License

This project is licensed under the MIT License.
