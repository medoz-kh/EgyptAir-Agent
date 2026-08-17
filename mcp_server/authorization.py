from mcp_server.database import get_connection


def check_employee_exists(employee_id: int) -> dict:
    """
    Check whether an employee exists.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT role
        FROM Employees
        WHERE employee_id = ?
        AND is_active = 1
        """,
        (employee_id,),
    )

    employee = cursor.fetchone()

    connection.close()

    if employee is None:
        return {
            "authorized": False,
            "message": "Employee not found."
        }

    return {
        "authorized": True,
        "role": employee["role"]
    }


def authorize_customer_service(employee_id: int) -> dict:
    """
    Customer Service, Supervisor and Manager
    are allowed to submit compensation requests.
    """

    employee = check_employee_exists(employee_id)

    if not employee["authorized"]:
        return employee

    allowed_roles = [
        "CustomerService",
        "Supervisor",
        "Manager",
    ]

    if employee["role"] not in allowed_roles:
        return {
            "authorized": False,
            "message": "Permission denied."
        }

    return {
        "authorized": True
    }


def authorize_manager(employee_id: int) -> dict:
    """
    Only Managers and Supervisors can approve compensation requests.
    """

    employee = check_employee_exists(employee_id)

    if not employee["authorized"]:
        return employee

    if employee["role"] == "CustomerService":
        return {
            "authorized": False,
            "message": "Manager role required."
        }

    return {
        "authorized": True
    }