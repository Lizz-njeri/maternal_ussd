from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
import africastalking
import os
from dotenv import load_dotenv

app = Flask(__name__)

load_dotenv()
# Africa's Talking credentials
username = os.getenv("username")
api_key = os.getenv("api_key")
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
    schedule = db.Column(db.String(255), nullable=False)
    week_age = db.Column(db.String(50), nullable=False)  # Age for baby

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    appointment_type = db.Column(db.String(20), nullable=False)  # Doctor or Midwife
    hospital = db.Column(db.String(100), nullable=False)

# Initialize the database
with app.app_context():
    db.create_all()


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
        response = "CON Please select your country \n"
        response+= "1. Nairobi\n"
        response+= "2. Mombasa\n"
        response+= "3. Kisumu\n"
    
    elif text == '1*1*1':
        response = "CON Available Hospitals in Nairobi"
        response+= "1. Karen Hospital \n"
        response+= "2. Komarock hospital \n"
        response+= "3. Kenyatta hospital"
    elif text == '1*1*2':
        response = "CON Available Hospitals in Mombasa"
        response+= "1. Mama Ngina Hospital \n"
        response+= "2. Pumwani hospital \n"
        response+= "3. Kwale hospital"
    elif text == '1*1*3':
        response = "CON Available Hospitals in Kisumu"
        response+= "1. Oginga Odinga Hospital \n"
        response+= "2. General hospital \n"
        response+= "3. Marie stopes hospital"
    
    elif text in ['1*1*1*1','1*1*1*2','1*1*1*3','1*1*2*1','1*1*2*2','1*1*2*3','1*1*3*1','1*1*3*2','1*1*3*3']:
        response="END Your appointment with a doctor has been booked. You will receive details via SMS"
        send_sms(phone_number, "You appointed has been booked at 9am with Dr. Anne Wairimu")

    
    # Sub-option for booking a Midwife (Option 1*2)
    elif text == '1*2':
        response = "CON Available Midwives\n"
        response += "1. Ashley W (10 deliveries)\n"
        response += "2. Mary J (28 deliveries)\n"
        response += "3. John M (15 deliveries)\n"
        response += "4. Veronica S (20 deliveries)\n"

    elif text in ['1*2*1','1*2*2','1*2*3','1*2*4']:
        response = "END Your appointment with a midwife has been booked. You will receive confirmation via SMS."
        send_sms(phone_number, "Appointment booked with a midwife. They will contact you for further details.")
       

    # Vaccine Rotation (Option 2)
    elif text == '2':
        response = "CON Vaccine Rotation\n"
        response += "1. Baby's Vaccine Schedule\n"
        response += "2. Set Baby Age\n"
    
    # Baby's Vaccine Schedule (Option 2*1)
    elif text == '2*1':
        schedules = VaccineSchedule.query.all()
        response = "END Vaccine Schedule:\n"
        for schedule in schedules:
            response += f"{schedule.week_age}: {schedule.schedule}\n"
    
    # Set Baby Age (Option 2*2)
    elif text == '2*2':
        response = "CON Please enter your baby's age in months:"    
        # Recommend the next vaccine based on age
    elif text.startswith('2*2'):
        baby_age_months = int(text.split('*')[2])  # Extracting the age from the text
       
        if baby_age_months < 1:
            response = "END Next vaccine due: BCG, Hepatitis B at Birth."
        elif 1 <= baby_age_months < 6:
            response = "END Next vaccine due: Polio, DPT, Hib at 6 weeks."
        elif 6 <= baby_age_months < 12:
            response = "END Next vaccine due: MMR, Varicella at 12 months."
        else:
            response = "END No further vaccines due at this time."

        # Send reminder 
        send_sms(phone_number, f"Reminder: Next vaccine due for your baby in {max(0, 6 - baby_age_months)} months.")

   
    # Emergency Contacts (Option 3)
    elif text == '3':
        response = "CON Emergency Contacts:\n"
        response += "1. Hospital\n"
        response += "2. Midwife\n"
    elif text == '3*1':
        response = "END Doctor on call is Dr. Vamos (Gynecologist). Contact: +25471234567"
        send_sms(phone_number, "Doctor on call is Dr. Vamos (Gynecologist). Contact: +25471234567")
    elif text == '3*2':
        response ="END Midwife available is Ms.Veronica. Contact info: +25473456789"
        send_sms(phone_number, "Midwife available is Ms.Veronica. Contact info: +25473456789")

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
    app.run(host="0.0.0.0", port=os.environ.get("PORT", 5000))
    
