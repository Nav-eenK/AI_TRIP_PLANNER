from flask import Flask, app, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trip_planner.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'

db = SQLAlchemy(app)


# 1️⃣ Users Table
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    trips = db.relationship("Trip", backref="user", lazy=True)


# 2️⃣ Trips Table (Main Entity)
class Trip(db.Model):
    __tablename__ = "trips"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    source_city = db.Column(db.String(100), nullable=False)
    destination = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    total_days = db.Column(db.Integer, nullable=False)
    total_budget = db.Column(db.Float, nullable=False)

    trip_type = db.Column(db.String(50))      # solo / couple / family
    travel_style = db.Column(db.String(50))   # budget / mid / luxury
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    preferences = db.relationship("Preference", backref="trip", uselist=False)
    budget = db.relationship("Budget", backref="trip", uselist=False)
    itineraries = db.relationship("Itinerary", backref="trip", lazy=True)


# 3️⃣ Preferences Table
class Preference(db.Model):
    __tablename__ = "preferences"

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id"), nullable=False)

    food_preference = db.Column(db.String(50))       # veg / non-veg
    activity_type = db.Column(db.String(100))        # adventure / relax
    accommodation_type = db.Column(db.String(50))    # hostel / hotel
    transport_preference = db.Column(db.String(50))  # bus / train
    pace = db.Column(db.String(50))                  # slow / fast


# 4️⃣ Budget Breakdown Table
class Budget(db.Model):
    __tablename__ = "budgets"

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id"), nullable=False)

    travel_cost = db.Column(db.Float)
    stay_cost = db.Column(db.Float)
    food_cost = db.Column(db.Float)
    activity_cost = db.Column(db.Float)
    buffer_cost = db.Column(db.Float)
    currency = db.Column(db.String(10), default="INR")


# 5️⃣ Itinerary Table (Day-wise)
class Itinerary(db.Model):
    __tablename__ = "itineraries"

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id"), nullable=False)

    day_number = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date)
    city_area = db.Column(db.String(100))
    summary = db.Column(db.Text)
    estimated_day_cost = db.Column(db.Float)

    activities = db.relationship("Activity", backref="itinerary", lazy=True)


# 6️⃣ Activities Table
class Activity(db.Model):
    __tablename__ = "activities"

    id = db.Column(db.Integer, primary_key=True)
    itinerary_id = db.Column(db.Integer, db.ForeignKey("itineraries.id"), nullable=False)

    name = db.Column(db.String(150), nullable=False)
    activity_type = db.Column(db.String(50))  # sightseeing / food / travel
    start_time = db.Column(db.String(20))
    end_time = db.Column(db.String(20))
    estimated_cost = db.Column(db.Float)
    notes = db.Column(db.Text)


# 7️⃣ AI Logs Table (Optional but Useful)
class AILog(db.Model):
    __tablename__ = "ai_logs"

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id"))

    user_prompt = db.Column(db.Text)
    ai_response = db.Column(db.Text)
    model_name = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('dashboard'))  # go to dashboard
        else:
            return "Invalid credentials"  # show message or render login.html again
    # GET request
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        password_hash = generate_password_hash(password)
        if username == '' or email == '' or password == '':
            return "Please fill all fields"
        if User.query.filter_by(username=username).first():
            return "Username already exists"
        if User.query.filter_by(email=email).first():
            return "Email already registered"
        user= User(username=username, email=email, password_hash=password_hash)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    
    return render_template('register.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    trips = user.trips  # fetch all trips for this user

    return render_template('dashboard.html', username=user.username, trips=trips)

@app.route("/create_trip")
def create_trip():
    return render_template('create_trip.html')
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__=='__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
