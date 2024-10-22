from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
import africastalking

app = Flask(__name__)

# Africa's Talking credentials
username = "your_username"
api_key = "your_api_key"
africastalking.initialize(username, api_key)
sms = africastalking.SMS

# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///maternal_care.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)
    baby_age = db.Column(db.String(10))  # Store baby's age for vaccine recommendations

class VaccineSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_type = db.Column(db.String(10), nullable=False)  # 'mother' or 'baby'
    schedule = db.Column(db.String(255), nullable=False)
    week_age = db.Column(db.String(50), nullable=False)  # Age for baby

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    appointment_type = db.Column(db.String(20), nullable=False)  # Doctor or Midwife
    hospital = db.Column(db.String(100), nullable=False)

# Initialize the database
db.create_all()

# Seed data for vaccine schedules and hospitals
def seed_data():
    if not VaccineSchedule.query.first():
        # Adding vaccine schedules for baby
        baby_vaccines = [
            VaccineSchedule(recipient_type='baby', schedule='BCG, Hepatitis B', week_age='At Birth'),
            VaccineSchedule(recipient_type='baby', schedule='Polio, DPT, Hib', week_age='6 weeks'),
            VaccineSchedule(recipient_type='baby', schedule='MMR, Varicella', week_age='12 months')
        ]
        db.session.add_all(baby_vaccines)
        db.session.commit()

seed_data()

# USSD endpoint
@app.route('/ussd', methods=['POST'])
def ussd():
    session_id = request.values.get("sessionId", None)
    service_code = request.values.get("serviceCode", None)
    phone_number = request.values.get("phoneNumber", None)
    text = request.values.get("text", "default")

    # Split the input from the user (for submenu navigation)
    user_response = text.split('*')

    # Ensure user exists in the database
    user = User.query.filter_by(phone_number=phone_number).first()
    if not user:
        user = User(phone_number=phone_number)
        db.session.add(user)
        db.session.commit()

    # Main Menu
    if text == '':
        response = "CON Welcome to Maternal Care\n"
        response += "1. Schedule Appointment\n"
        response += "2. Vaccine Rotation\n"
        response += "3. Emergency Contacts\n"

    # Schedule Appointment (Option 1)
    elif text == '1':
        response = "CON Schedule Appointment\n"
        response += "1. Book Doctor\n"
        response += "2. Book Midwife\n"

    # Sub-option for booking a Doctor (Option 1*1)
    elif text == '1*1':
        response = "CON Please indicate your county (e.g., Nairobi, Kisumu)"
    
    # Sub-option for booking a Midwife (Option 1*2)
    elif text == '1*2':
        response = "CON Available Midwives\n"
        response += "1. Ashley W (10 deliveries)\n"
        response += "2. Mary J (28 deliveries)\n"
        response += "3. John M (15 deliveries)\n"
        response += "4. Veronica S (20 deliveries)\n"

    # Get hospitals based on county (Option 1*1*<county>)
    elif len(user_response) == 2 and user_response[0] == '1' and user_response[1]:  # Check if county is provided
        county = user_response[1]
        hospitals = {
            'Nairobi': ['Nairobi Hospital', 'Aga Khan Hospital', 'Karen Hospital'],
            'Kisumu': ['Kisumu County Hospital', 'Jaramogi Oginga Odinga Teaching and Referral Hospital'],
            # Add more counties and their hospitals as needed
        }
        available_hospitals = hospitals.get(county, [])
        
        if available_hospitals:
            response = "CON Available Hospitals:\n"
            for index, hospital in enumerate(available_hospitals):
                response += f"{index + 1}. {hospital}\n"
        else:
            response = "END No hospitals found for the given county."

    # Book selected doctor appointment (Option 1*1*<county>*<hospital_choice>)
    elif len(user_response) == 3 and user_response[0] == '1' and user_response[1] and user_response[2].isdigit():
        hospital_choice = int(user_response[2]) - 1  # Get the index of the selected hospital
        county = user_response[1]
        hospitals = {
            'Nairobi': ['Nairobi Hospital', 'Aga Khan Hospital', 'Karen Hospital'],
            'Kisumu': ['Kisumu County Hospital', 'Jaramogi Oginga Odinga Teaching and Referral Hospital'],
        }
        available_hospitals = hospitals.get(county, [])
        
        if 0 <= hospital_choice < len(available_hospitals):
            appointment = Appointment(user_id=user.id, appointment_type='Doctor', hospital=available_hospitals[hospital_choice])
            db.session.add(appointment)
            db.session.commit()
            response = "END Your appointment with a doctor at {} has been booked. You will receive confirmation via SMS.".format(available_hospitals[hospital_choice])
            send_sms(phone_number, "Appointment booked with a doctor at {}.".format(available_hospitals[hospital_choice]))
        else:
            response = "END Invalid hospital choice."

    # Book selected midwife appointment (Option 1*2*<midwife_choice>)
    elif len(user_response) == 3 and user_response[0] == '1' and user_response[1] == '2' and user_response[2].isdigit():
        midwife_choice = int(user_response[2]) - 1  # Get the index of the selected midwife
        if midwife_choice in range(4):  # Ensure the choice is within the number of midwives listed
            appointment = Appointment(user_id=user.id, appointment_type='Midwife', hospital='Midwife Service')
            db.session.add(appointment)
            db.session.commit()
            response = "END Your appointment with a midwife has been booked. You will receive confirmation via SMS."
            send_sms(phone_number, "Appointment booked with a midwife.")
        else:
            response = "END Invalid midwife choice."

    # Vaccine Rotation (Option 2)
    elif text == '2':
        response = "CON Vaccine Rotation\n"
        response += "1. Baby's Vaccine Schedule\n"
        response += "2. Set Baby Age\n"
    
    # Baby's Vaccine Schedule (Option 2*1)
    elif text == '2*1':
        vaccines = VaccineSchedule.query.filter_by(recipient_type='baby').all()
        response = "END Baby's Vaccines:\n"
        for item in vaccines:
            response += f"{item.week_age}: {item.schedule}\n"
    
    # Set Baby Age (Option 2*2)
    elif text == '2*2':
        response = "CON Please enter your baby's age in months:"

    # Store baby's age and recommend next vaccine based on age
    elif len(user_response) == 2 and user_response[0] == '2' and user_response[1].isdigit():
        baby_age_months = int(user_response[1])
        user.baby_age = user_response[1]
        db.session.commit()
        
        # Recommend the next vaccine based on age
        if baby_age_months < 1:
            response = "END Next vaccine due: BCG, Hepatitis B at Birth."
        elif 1 <= baby_age_months < 6:
            response = "END Next vaccine due: Polio, DPT, Hib at 6 weeks."
        elif 6 <= baby_age_months < 12:
            response = "END Next vaccine due: MMR, Varicella at 12 months."
        else:
            response = "END No further vaccines due at this time."

        # Set reminder (this can be expanded with a real reminder system)
        send_sms(phone_number, f"Reminder: Next vaccine due for your baby in {max(0, 6 - baby_age_months)} months.")

    # Emergency Contacts (Option 3)
    elif text == '3':
        response = "END Emergency Contacts:\n"
        response += "1. Hospital\n"
        response += "2. Midwife\n"
    elif text == '3*1':
        response = "END Doctor on call is Dr. Vamos (Gynecologist). Contact: +25471234567"
        send_sms(phone_number, "Doctor on call is Dr. Vamos (Gynecologist). Contact: +25471234567")

    # Default response for invalid input
    else:
        response = "END Invalid option. Please try again."

    return response

# Function to send SMS reminders using Africa's Talking
def send_sms(phone_number, message):
    try:
        response = sms.send(message, [phone_number])
        print(f"SMS sent successfully: {response}")
    except Exception as e:
        print(f"Failed to send SMS: {e}")

# Running the Flask server
if __name__ == '__main__':
    app.run(debug=True)
