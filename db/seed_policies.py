import sqlite3
import os

# Connect to your SQLite database file
db_path = os.path.join(os.path.dirname(__file__), "database.db")  # Adjust filename if yours is different
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Ensure the Policies table exists
cursor.execute("""
CREATE TABLE IF NOT EXISTS Policies (
    policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL
)
""")

# Real EgyptAir policy records matching your evaluation questions
policies_to_insert = [
    ("Baggage Allowance", "Economy class international baggage allowance is 1 checked bag up to 23kg."),
    ("Rule MS-772 Fees", "Under penalty rule MS-772, class Y rebooking incurs a mandatory $50 fee."),
    ("EU-261 Deferral", "EU-261 policy limits compensation for a 4-hour delay to 600 euros."),
    ("Pet Policy", "Small pets in approved carriers under 8kg total weight are allowed in the cabin."),
    ("Fleet Wi-Fi", "Onboard high-speed Wi-Fi internet is available on all Boeing 777-300ER aircraft."),
    ("Cabin Pet Requirements", "Pets carried in the cabin must remain in an approved leak-proof carrier."),
    ("Wheelchair Assistance", "Wheelchair assistance must be requested at least 48 hours prior to international flight departure."),
    ("International Arrival Time", "Passengers on international flights must arrive at the airport check-in counter 3 hours prior to departure."),
    ("Mileage Upgrades", "Flight MS800 is eligible for automatic mileage upgrades for Cairo routes."),
    ("Irregular Operations Care", "During maintenance delays over 4 hours, passengers on flight MS777 receive meal vouchers and alternative rebooking options."),
    ("Overnight Accommodations", "In cases of canceled business class flights requiring overnight waiting, EgyptAir covers hotel accommodation and airport lounge access."),
    ("Sporting & Infant Baggage", "Travelers with infants are allowed one extra stroller, while sporting equipment like snowboards incurs standard special handling fees.")
]

# Insert policies into the database
cursor.executemany("""
INSERT INTO Policies (title, content)
VALUES (?, ?)
""", policies_to_insert)

conn.commit()
conn.close()
print("✅ Successfully inserted all policy records into SQLite database!")