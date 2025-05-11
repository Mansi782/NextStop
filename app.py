from dotenv import load_dotenv
from flask import Flask, render_template, request, session, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import google.generativeai as genai
import requests
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# Configure Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'  # Change for production (PostgreSQL/MySQL)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configure Generative AI API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# OpenWeatherMap API Key
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# ---------------- Database Models ----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)

# ---------------- Routes ----------------
@app.route('/')
def home():
    return render_template('homepage.html')

@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash("Please login to access your dashboard.", "warning")
        return redirect(url_for('login'))

    travel_data = session.get('travel_data', {})
    return render_template('dashboard.html', now=datetime.now(), travel_data=travel_data)

@app.route('/about')
def about():
    return render_template('about.html', now=datetime.now())

@app.route('/contact')
def contact():
    return render_template('contact.html', now=datetime.now())

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            flash(f"Welcome, {user.name}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid email or password!", "danger")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('password2')

        # Check if passwords match
        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('register'))

        # Hash the password
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        # Check if email already exists
        if User.query.filter_by(email=email).first():
            flash("Email already registered!", "danger")
            return redirect(url_for('register'))

        # Save new user to database
        new_user = User(name=name, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out!", "info")
    return redirect(url_for('home'))

@app.route('/generate_itinerary', methods=['POST'])
def generate_itinerary():
    if 'user_id' not in session:
        flash("Please login to generate an itinerary.", "warning")
        return redirect(url_for('login'))

    destination = request.form.get('destination')
    start_date = request.form.get('startDate')
    end_date = request.form.get('endDate')

    # Updated prompt for structured itinerary
    prompt = f"""
    Generate a structured, day-wise travel itinerary for {destination} from {start_date} to {end_date}.
    
    ## Formatting:
    - Each day should start with **Day X: [Date] - [Theme]**
    - Use **bulleted points (-)** for activities.
    - Ensure clear separation between days.

    Example:
    **Day 1: Exploring {destination}**
    - 09:00 AM: Arrive and check-in at the hotel.
    - 10:00 AM: Visit the historic city center.
    - 12:00 PM: Lunch at a famous local restaurant.
    - 02:00 PM: Explore museums and cultural sites.
    - 07:00 PM: Dinner at a waterfront restaurant.
    """

    model = genai.GenerativeModel('gemini-1.5-pro')
    response = model.generate_content(prompt)

    itinerary = response.text  # Keeping raw markdown format

    # Fetch weather data
    weather_data = get_weather_data(destination)

    # Store data in session
    session['travel_data'] = {
        'destination': destination,
        'start_date': start_date,
        'end_date': end_date,
        'itinerary': itinerary,
        'weather': weather_data
    }

    return redirect(url_for('dashboard'))

@app.route('/get_weather', methods=['POST'])
def get_weather():
    """Fetches weather for a given city."""
    data = request.json
    city = data.get("city", "")

    if not city:
        return jsonify({"error": "City not provided"}), 400

    weather_data = get_weather_data(city)
    return jsonify(weather_data)

def get_weather_data(city):
    """Fetches real-time weather from OpenWeatherMap API."""
    if not OPENWEATHER_API_KEY:
        return {"error": "Missing API Key"}
    
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&units=metric&appid={OPENWEATHER_API_KEY}"
        response = requests.get(url)
        weather_data = response.json()

        if response.status_code != 200:
            return {"error": f"API Error: {weather_data.get('message', 'Unknown error')}"}

        return {
            "location": city.capitalize(),
            "description": weather_data["weather"][0]["description"],
            "temperature": weather_data["main"]["temp"],
            "temp_min": weather_data["main"]["temp_min"],
            "temp_max": weather_data["main"]["temp_max"],
            "humidity": weather_data["main"]["humidity"],
            "wind_speed": weather_data["wind"]["speed"],
            "icon": f"http://openweathermap.org/img/w/{weather_data['weather'][0]['icon']}.png"
        }
    except Exception as e:
        return {"error": str(e)}

@app.route('/blog')
def blog():
    return "<h1>Blog Page Coming Soon!</h1>"

@app.route('/trip_planner')
def trip_planner():
    return "<h1>Trip Planner Page Coming Soon!</h1>"

@app.route('/deals')
def deals():
    return "<h1>Deals Page Coming Soon!</h1>"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Creates the database tables if they don't exist
    app.run(debug=True)
