from mcp_server.database import get_connection


def validate_booking_exists(booking_id: int) -> dict:
    """
    Check whether a booking exists.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT booking_id
        FROM Bookings
        WHERE booking_id = ?
        """,
        (booking_id,),
    )

    booking = cursor.fetchone()

    connection.close()

    if booking is None:
        return {
            "valid": False,
            "message": "Booking not found."
        }

    return {
        "valid": True
    }


def validate_flight_eligible_for_compensation(booking_id: int) -> dict:
    """
    Check if the booking belongs to a delayed or cancelled flight.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT f.status
        FROM Bookings b
        JOIN Flights f
            ON b.flight_id = f.flight_id
        WHERE b.booking_id = ?
        """,
        (booking_id,),
    )

    result = cursor.fetchone()

    connection.close()

    if result is None:
        return {
            "valid": False,
            "message": "Booking not found."
        }

    if result["status"] not in ("Delayed", "Cancelled"):
        return {
            "valid": False,
            "message": "Compensation is only available for delayed or cancelled flights."
        }

    return {
        "valid": True
    }


def validate_requested_amount(requested_amount: float) -> dict:
    """
    Validate the requested compensation amount.
    """

    if requested_amount <= 0:
        return {
            "valid": False,
            "message": "Requested amount must be greater than zero."
        }

    return {
        "valid": True
    }