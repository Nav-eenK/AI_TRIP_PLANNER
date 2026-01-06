from flask import Flask, flash, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from groq import Groq
from dotenv import load_dotenv
import requests

# ================= ENV & GROQ =================
load_dotenv()

print("GROQ KEY LOADED:", os.getenv("GROQ_API_KEY"))  # DEBUG

groq_client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

# ================= FLASK APP =================
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trip_planner.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'

db = SQLAlchemy(app)

# ================= MODELS =================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    trips = db.relationship("Trip", backref="user", lazy=True)


class Trip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    source_city = db.Column(db.String(100))
    destination = db.Column(db.String(100))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    total_days = db.Column(db.Integer)
    total_budget = db.Column(db.Float)
    trip_type = db.Column(db.String(50))
    travel_style = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    preferences = db.relationship("Preference", backref="trip", uselist=False)
    budget = db.relationship("Budget", backref="trip", uselist=False)


class Preference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"))
    food_preference = db.Column(db.String(50))
    activity_type = db.Column(db.String(100))
    accommodation_type = db.Column(db.String(50))
    transport_preference = db.Column(db.String(50))
    pace = db.Column(db.String(50))


class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"))
    travel_cost = db.Column(db.Float)
    stay_cost = db.Column(db.Float)
    food_cost = db.Column(db.Float)
    activity_cost = db.Column(db.Float)
    buffer_cost = db.Column(db.Float)
    currency = db.Column(db.String(10), default="INR")


class AILog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"))
    user_prompt = db.Column(db.Text)
    ai_response = db.Column(db.Text)
    model_name = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()

# ================= AI FUNCTION =================
def generate_ai_itinerary(trip, pref):
    prompt = f"""
You are an AI travel planner.

Source: {trip.source_city}
Destination: {trip.destination}
Days: {trip.total_days}
Budget: {trip.total_budget} INR
Trip Type: {trip.trip_type}
Travel Style: {trip.travel_style}

Preferences:
Food: {pref.food_preference}
Activities: {pref.activity_type}
Accommodation: {pref.accommodation_type}
Transport: {pref.transport_preference}
Pace: {pref.pace}

Generate a detailed day-wise itinerary with estimated daily costs.
"""

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",  # safer model
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    return response.choices[0].message.content


def get_place_image(place_name):
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")

    # 1️⃣ Find place
    search_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    params = {
        "input": place_name,
        "inputtype": "textquery",
        "fields": "photos",
        "key": api_key
    }

    response = requests.get(search_url, params=params).json()

    if not response.get("candidates"):
        return None

    photos = response["candidates"][0].get("photos")
    if not photos:
        return None

    photo_ref = photos[0]["photo_reference"]

    # 2️⃣ Build image URL
    image_url = (
        "https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth=800&photo_reference={photo_ref}&key={api_key}"
    )

    return image_url
def clean_ai_text(text):
    text = text.replace("**", "")
    text = text.replace("- ", "• ")
    return text

# ================= ROUTES =================
@app.route('/')
def home():
    return render_template("index.html")


@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user = User(
            username=request.form['username'],
            email=request.form['email'],
            password_hash=generate_password_hash(request.form['password'])
        )
        db.session.add(user)
        db.session.commit()
        flash("Registration successful", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            session['user_id'] = user.id
            return redirect(url_for("dashboard"))
        flash("Invalid credentials", "error")
    return render_template("login.html")


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for("login"))
    user = User.query.get(session['user_id'])
    return render_template("dashboard.html", trips=user.trips)


@app.route("/create_trip", methods=["GET", "POST"])
def create_trip():
    if 'user_id' not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        start = datetime.strptime(request.form['start_date'], "%Y-%m-%d").date()
        end = datetime.strptime(request.form['end_date'], "%Y-%m-%d").date()

        trip = Trip(
            user_id=session['user_id'],
            source_city=request.form['source_city'],
            destination=request.form['destination'],
            start_date=start,
            end_date=end,
            total_days=(end - start).days + 1,
            total_budget=float(request.form['total_budget']),
            trip_type=request.form['trip_type'],
            travel_style=request.form['travel_style']
        )
        db.session.add(trip)
        db.session.commit()

        pref = Preference(
            trip_id=trip.id,
            food_preference=request.form['food_preference'],
            activity_type=request.form['activity_type'],
            accommodation_type=request.form['accommodation_type'],
            transport_preference=request.form['transport_preference'],
            pace=request.form['pace']
        )
        db.session.add(pref)
        db.session.commit()

        db.session.add(Budget(trip_id=trip.id))
        db.session.commit()

        # ===== AI GENERATION =====
        print("➡️ Calling Groq AI...")
        try:
            ai_text = generate_ai_itinerary(trip, pref)
            db.session.add(AILog(
                trip_id=trip.id,
                user_prompt="Auto-generated trip plan",
                ai_response=ai_text,
                model_name="llama3-8b"
            ))
            db.session.commit()
            print("✅ AI LOG SAVED")
        except Exception as e:
            print("❌ AI ERROR:", e)

        flash("Trip created successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("create_trip.html")


@app.route('/trip/<int:trip_id>')
def view_trip(trip_id):
    trip = Trip.query.get_or_404(trip_id)

    ai_log = AILog.query.filter_by(trip_id=trip.id)\
                        .order_by(AILog.created_at.desc())\
                        .first()

    place_image = get_place_image(trip.destination)

    cleaned_ai_response = (
        clean_ai_text(ai_log.ai_response)
        if ai_log and ai_log.ai_response
        else None
    )

    return render_template(
        "trip_details.html",
        trip=trip,
        ai_response=cleaned_ai_response,
        place_image=place_image
    )


@app.route('/trip/<int:trip_id>/delete', methods=['POST'])
def delete_trip(trip_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    trip = Trip.query.get_or_404(trip_id)

    if trip.user_id != session['user_id']:
        flash("Unauthorized action", "error")
        return redirect(url_for('dashboard'))

    # Delete AI logs first
    AILog.query.filter_by(trip_id=trip.id).delete()

    # Delete related data
    if trip.preferences:
        db.session.delete(trip.preferences)
    if trip.budget:
        db.session.delete(trip.budget)

    db.session.delete(trip)
    db.session.commit()

    flash("Trip deleted successfully", "success")
    return redirect(url_for('dashboard'))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host="0.0.0.0",port=5001, debug=True)
