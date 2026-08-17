-- ==========================================
-- EgyptAir Flight Disruption Management System
-- Database Schema
-- ==========================================

PRAGMA foreign_keys = ON;

-- ===========================
-- Employees
-- ===========================

CREATE TABLE Employees (
    employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL CHECK (
        role IN ('CustomerService', 'Supervisor', 'Manager')
    ),
    department TEXT NOT NULL,
    password TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

-- ===========================
-- Flights
-- ===========================

CREATE TABLE Flights (
    flight_id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_number TEXT UNIQUE NOT NULL,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    departure_time TEXT NOT NULL,
    arrival_time TEXT NOT NULL,

    status TEXT NOT NULL CHECK (
        status IN (
            'Scheduled',
            'Delayed',
            'Cancelled',
            'Boarding',
            'Departed',
            'Arrived'
        )
    ),

    delay_minutes INTEGER DEFAULT 0
);

-- ===========================
-- Passengers
-- ===========================

CREATE TABLE Passengers (
    passenger_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    passport_number TEXT UNIQUE NOT NULL,
    email TEXT,
    phone TEXT
);

-- ===========================
-- Bookings
-- ===========================

CREATE TABLE Bookings (
    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,

    passenger_id INTEGER NOT NULL,

    flight_id INTEGER NOT NULL,

    seat_number TEXT NOT NULL,

    ticket_class TEXT NOT NULL CHECK (
        ticket_class IN (
            'Economy',
            'Business',
            'First'
        )
    ),

    booking_status TEXT NOT NULL CHECK (
        booking_status IN (
            'Confirmed',
            'Cancelled',
            'Rebooked'
        )
    ),

    FOREIGN KEY(passenger_id)
        REFERENCES Passengers(passenger_id),

    FOREIGN KEY(flight_id)
        REFERENCES Flights(flight_id)
);

-- ===========================
-- Compensation Requests
-- ===========================

CREATE TABLE CompensationRequests (

    request_id INTEGER PRIMARY KEY AUTOINCREMENT,

    booking_id INTEGER NOT NULL,

    requested_amount REAL NOT NULL CHECK (
        requested_amount >= 0
    ),

    reason TEXT NOT NULL,

    status TEXT NOT NULL CHECK (
        status IN (
            'Pending',
            'Approved',
            'Rejected'
        )
    ),

    approved_by INTEGER,

    created_at TEXT NOT NULL,

    FOREIGN KEY(booking_id)
        REFERENCES Bookings(booking_id),

    FOREIGN KEY(approved_by)
        REFERENCES Employees(employee_id)
);

-- ===========================
-- Policies
-- ===========================

CREATE TABLE Policies (

    policy_id INTEGER PRIMARY KEY AUTOINCREMENT,

    title TEXT NOT NULL,

    content TEXT NOT NULL
);

-- ===========================
-- Reports
-- ===========================

CREATE TABLE Reports (

    report_id INTEGER PRIMARY KEY AUTOINCREMENT,

    employee_id INTEGER NOT NULL,

    report_type TEXT NOT NULL,

    status TEXT NOT NULL CHECK (
        status IN (
            'Pending',
            'Running',
            'Completed'
        )
    ),

    progress INTEGER NOT NULL DEFAULT 0
        CHECK(progress BETWEEN 0 AND 100),

    generated_at TEXT NOT NULL,

    FOREIGN KEY(employee_id)
        REFERENCES Employees(employee_id)
);
-- ===========================
-- Failure Tickets (Final Project)
-- ===========================

CREATE TABLE FailureTickets (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    thread_id TEXT NOT NULL,          -- Connects the ticket to the specific LangGraph run
    
    node_name TEXT NOT NULL,          -- The exact node where the agent crashed
    
    error_message TEXT NOT NULL,      -- The exception caught
    
    state_dump TEXT,                  -- JSON string of the agent's state when it died
    
    status TEXT NOT NULL CHECK (
        status IN (
            'Open',
            'Investigating',
            'Resolved'
        )
    ),
    
    resolved_by INTEGER,              -- The Admin/Employee who clears the ticket
    
    created_at TEXT NOT NULL,
    
    FOREIGN KEY(resolved_by)
        REFERENCES Employees(employee_id)
);