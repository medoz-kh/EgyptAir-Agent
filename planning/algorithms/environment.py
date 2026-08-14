import json
import re
import sqlite3
import asyncio
from ..models import EnvironmentFeedback

class Environment:
    """A grounded evaluator that checks the actual EgyptAir database for scheduling conflicts."""

    def __init__(self, db_path: str = "db/database.db"):
        self.db_path = db_path

    async def evaluate(self, state: str) -> EnvironmentFeedback:
        """
        Evaluates the AI's proposed reshuffle plan asynchronously.
        Fails the branch if passengers/flights don't exist, or if the flight is invalid.
        """
        match = re.search(r'\[\s*\{.*?\}\s*\]', state, re.DOTALL)
        
        if not match:
            return EnvironmentFeedback(
                success=False, 
                score=0.1, 
                details=["Critique: Failed to parse plan. You must output the proposed rebookings as a JSON array."]
            )

        try:
            proposed_bookings = json.loads(match.group(0))
        except json.JSONDecodeError:
            return EnvironmentFeedback(
                success=False, 
                score=0.1, 
                details=["Critique: Invalid JSON format in the proposed plan."]
            )

        # We need a fallback if it isn't a list
        if not isinstance(proposed_bookings, list):
            return EnvironmentFeedback(
                success=False, 
                score=0.1, 
                details=["Critique: The parsed JSON is not an array of bookings."]
            )

        def db_check():
            local_success = True
            local_details = []
            
            try:
                with sqlite3.connect(self.db_path) as db:
                    cursor = db.cursor()
                    seen_passengers = set()
                    
                    for booking in proposed_bookings:
                        p_id = booking.get("passenger_id")
                        f_id = booking.get("flight_id")
                        
                        if not p_id or not f_id:
                            local_details.append("Critique: Missing passenger_id or flight_id in booking.")
                            local_success = False
                            continue
                            
                        # 1. Prevent Double Booking in the same proposal
                        if p_id in seen_passengers:
                            local_details.append(f"Critique: Passenger {p_id} was double-booked in this plan!")
                            local_success = False
                        seen_passengers.add(p_id)

                        # 2. Check if Passenger exists
                        cursor.execute("SELECT full_name FROM Passengers WHERE passenger_id = ?", (p_id,))
                        if not cursor.fetchone():
                            local_details.append(f"Critique: Passenger ID {p_id} does not exist in the database.")
                            local_success = False

                        # 3. Check if Flight exists and is valid for rebooking
                        cursor.execute("SELECT status FROM Flights WHERE flight_id = ?", (f_id,))
                        flight_row = cursor.fetchone()
                        
                        if not flight_row:
                            local_details.append(f"Critique: Proposed flight ID {f_id} does not exist.")
                            local_success = False
                        else:
                            status = flight_row[0]
                            if status in ('Cancelled', 'Departed', 'Arrived'):
                                local_details.append(f"Critique: Cannot rebook onto Flight {f_id}. Current status is '{status}'.")
                                local_success = False
                                
            except sqlite3.Error as e:
                local_details.append(f"Database error during verification: {e}")
                local_success = False
                
            return local_success, local_details

        success, details = await asyncio.to_thread(db_check)
        
        score = 1.0 if success else 0.2
        if not success:
            details.append("The grounded environment rejected this plan due to the conflicts above.")
        else:
            details.append("Plan validated successfully against the database. No conflicts found.")

        return EnvironmentFeedback(success=success, score=score, details=details)