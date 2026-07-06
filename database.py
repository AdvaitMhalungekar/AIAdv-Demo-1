"""
Database layer for PrimeNest Realty Chatbot.
Handles SQLite initialization, data seeding from JSON, and query helpers.
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "primerealty.db")


def get_connection():
    """Get a new SQLite connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialize_database():
    """Create all tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS company (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            office TEXT,
            phone TEXT,
            email TEXT
        );

        CREATE TABLE IF NOT EXISTS builders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            phone TEXT,
            agent_type TEXT NOT NULL CHECK(agent_type IN ('sales', 'rental'))
        );

        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id TEXT NOT NULL UNIQUE,
            property_name TEXT NOT NULL,
            listing_type TEXT NOT NULL CHECK(listing_type IN ('Sale', 'Rent')),
            status TEXT NOT NULL,
            property_type TEXT NOT NULL,
            configuration TEXT,

            -- Sale-specific fields
            super_builtup_area_sqft INTEGER,
            carpet_area_sqft INTEGER,
            price INTEGER,
            builder TEXT,
            rera_number TEXT,
            loan_available BOOLEAN,
            maintenance_per_month INTEGER,
            available_units INTEGER,
            possession_date TEXT,

            -- Rent-specific fields
            monthly_rent INTEGER,
            security_deposit INTEGER,
            maintenance_rent INTEGER,
            furnishing TEXT,
            pets_allowed BOOLEAN,
            available_from TEXT,

            -- Common
            description TEXT,
            locality TEXT,
            city TEXT,
            state TEXT,
            assigned_agent TEXT,

            FOREIGN KEY (assigned_agent) REFERENCES agents(agent_id)
        );

        CREATE TABLE IF NOT EXISTS property_amenities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id TEXT NOT NULL,
            amenity TEXT NOT NULL,
            FOREIGN KEY (property_id) REFERENCES properties(property_id)
        );

        CREATE TABLE IF NOT EXISTS property_banks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id TEXT NOT NULL,
            bank TEXT NOT NULL,
            FOREIGN KEY (property_id) REFERENCES properties(property_id)
        );

        CREATE TABLE IF NOT EXISTS property_preferred_tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id TEXT NOT NULL,
            tenant_type TEXT NOT NULL,
            FOREIGN KEY (property_id) REFERENCES properties(property_id)
        );

        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS faqs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT 'New Chat',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_properties_listing_type ON properties(listing_type);
        CREATE INDEX IF NOT EXISTS idx_properties_locality ON properties(locality);
        CREATE INDEX IF NOT EXISTS idx_properties_config ON properties(configuration);
        CREATE INDEX IF NOT EXISTS idx_properties_type ON properties(property_type);
        CREATE INDEX IF NOT EXISTS idx_properties_status ON properties(status);
        CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
    """)

    conn.commit()
    conn.close()


def is_database_seeded():
    """Check if data has already been loaded."""
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
    conn.close()
    return count > 0


def load_data_from_json(json_path: str):
    """Seed the database from the real estate JSON dataset."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    conn = get_connection()
    cursor = conn.cursor()

    # Company
    company = data.get("company", {})
    cursor.execute(
        "INSERT OR IGNORE INTO company (name, office, phone, email) VALUES (?, ?, ?, ?)",
        (company.get("name"), company.get("office"), company.get("phone"), company.get("email"))
    )

    # Builders
    for builder in data.get("builders", []):
        cursor.execute("INSERT OR IGNORE INTO builders (name) VALUES (?)", (builder["name"],))

    # Sales Agents
    for agent in data.get("sales_agents", []):
        cursor.execute(
            "INSERT OR IGNORE INTO agents (agent_id, name, phone, agent_type) VALUES (?, ?, ?, ?)",
            (agent["id"], agent["name"], agent["phone"], "sales")
        )

    # Rental Agents
    for agent in data.get("rental_agents", []):
        cursor.execute(
            "INSERT OR IGNORE INTO agents (agent_id, name, phone, agent_type) VALUES (?, ?, ?, ?)",
            (agent["id"], agent["name"], agent["phone"], "rental")
        )

    # Sale Properties
    for prop in data.get("sale_properties", []):
        addr = prop.get("address", {})
        cursor.execute("""
            INSERT OR IGNORE INTO properties (
                property_id, property_name, listing_type, status, property_type, configuration,
                super_builtup_area_sqft, carpet_area_sqft, price, builder, rera_number,
                loan_available, maintenance_per_month, available_units, possession_date,
                description, locality, city, state, assigned_agent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prop["property_id"], prop["property_name"], prop["listing_type"], prop["status"],
            prop["property_type"], prop["configuration"],
            prop.get("super_builtup_area_sqft"), prop.get("carpet_area_sqft"), prop.get("price"),
            prop.get("builder"), prop.get("rera_number"), prop.get("loan_available"),
            prop.get("maintenance_per_month"), prop.get("available_units"), prop.get("possession_date"),
            prop.get("description"), addr.get("locality"), addr.get("city"), addr.get("state"),
            prop.get("assigned_agent")
        ))

        # Amenities
        for amenity in prop.get("amenities", []):
            cursor.execute(
                "INSERT INTO property_amenities (property_id, amenity) VALUES (?, ?)",
                (prop["property_id"], amenity)
            )

        # Banks
        for bank in prop.get("banks", []):
            cursor.execute(
                "INSERT INTO property_banks (property_id, bank) VALUES (?, ?)",
                (prop["property_id"], bank)
            )

    # Rental Properties
    for prop in data.get("rental_properties", []):
        addr = prop.get("address", {})
        cursor.execute("""
            INSERT OR IGNORE INTO properties (
                property_id, property_name, listing_type, status, property_type, configuration,
                monthly_rent, security_deposit, maintenance_rent, furnishing,
                pets_allowed, available_from,
                description, locality, city, state, assigned_agent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prop["property_id"], prop["property_name"], prop["listing_type"], prop["status"],
            prop["property_type"], prop["configuration"],
            prop.get("monthly_rent"), prop.get("security_deposit"), prop.get("maintenance"),
            prop.get("furnishing"), prop.get("pets_allowed"), prop.get("available_from"),
            prop.get("description", ""), addr.get("locality"), addr.get("city"), addr.get("state"),
            prop.get("assigned_agent")
        ))

        # Amenities
        for amenity in prop.get("amenities", []):
            cursor.execute(
                "INSERT INTO property_amenities (property_id, amenity) VALUES (?, ?)",
                (prop["property_id"], amenity)
            )

        # Preferred tenants
        for tenant in prop.get("preferred_tenants", []):
            cursor.execute(
                "INSERT INTO property_preferred_tenants (property_id, tenant_type) VALUES (?, ?)",
                (prop["property_id"], tenant)
            )

    # Policies
    policies = data.get("policies", {})
    for key, value in policies.items():
        cursor.execute(
            "INSERT OR IGNORE INTO policies (key, value) VALUES (?, ?)",
            (key, str(value))
        )

    # FAQs
    for faq in data.get("faqs", []):
        cursor.execute(
            "INSERT INTO faqs (question, answer) VALUES (?, ?)",
            (faq["question"], faq["answer"])
        )

    conn.commit()
    conn.close()
    print(f"[OK] Database seeded from {json_path}")


# ─── Query Helpers (used by agent tools) ─────────────────────────────────────

def search_sale_properties(locality=None, configuration=None, property_type=None,
                           min_price=None, max_price=None, builder=None,
                           amenities=None, status=None):
    """Search sale properties with optional filters. Returns list of dicts."""
    conn = get_connection()
    query = "SELECT DISTINCT p.* FROM properties p"
    joins = []
    conditions = ["p.listing_type = 'Sale'"]
    params = []

    if amenities:
        if isinstance(amenities, str):
            amenities = [a.strip() for a in amenities.split(",") if a.strip()]
        for i, am in enumerate(amenities):
            alias = f"pa{i}"
            joins.append(f"JOIN property_amenities {alias} ON p.property_id = {alias}.property_id")
            conditions.append(f"LOWER({alias}.amenity) LIKE LOWER(?)")
            params.append(f"%{am}%")

    if locality:
        conditions.append("LOWER(p.locality) LIKE LOWER(?)")
        params.append(f"%{locality}%")
    if configuration:
        conditions.append("LOWER(p.configuration) LIKE LOWER(?)")
        params.append(f"%{configuration}%")
    if property_type:
        conditions.append("LOWER(p.property_type) LIKE LOWER(?)")
        params.append(f"%{property_type}%")
    if min_price is not None:
        conditions.append("p.price >= ?")
        params.append(min_price)
    if max_price is not None:
        conditions.append("p.price <= ?")
        params.append(max_price)
    if builder:
        conditions.append("LOWER(p.builder) LIKE LOWER(?)")
        params.append(f"%{builder}%")
    if status:
        conditions.append("LOWER(p.status) = LOWER(?)")
        params.append(status)

    full_query = query + " " + " ".join(joins) + " WHERE " + " AND ".join(conditions) + " LIMIT 10"
    rows = conn.execute(full_query, params).fetchall()

    results = []
    for row in rows:
        prop = dict(row)
        # Fetch amenities
        amenities_rows = conn.execute(
            "SELECT amenity FROM property_amenities WHERE property_id = ?",
            (prop["property_id"],)
        ).fetchall()
        prop["amenities"] = [a["amenity"] for a in amenities_rows]
        # Fetch banks
        banks = conn.execute(
            "SELECT bank FROM property_banks WHERE property_id = ?",
            (prop["property_id"],)
        ).fetchall()
        prop["banks"] = [b["bank"] for b in banks]
        results.append(prop)

    conn.close()
    return results


def search_rental_properties(locality=None, configuration=None, property_type=None,
                             min_rent=None, max_rent=None, furnishing=None,
                             pets_allowed=None, preferred_tenant=None, amenities=None):
    """Search rental properties with optional filters. Returns list of dicts."""
    conn = get_connection()
    query = "SELECT DISTINCT p.* FROM properties p"
    joins = []
    conditions = ["p.listing_type = 'Rent'"]
    params = []

    if preferred_tenant:
        joins.append("JOIN property_preferred_tenants pt ON p.property_id = pt.property_id")
        conditions.append("LOWER(pt.tenant_type) LIKE LOWER(?)")
        params.append(f"%{preferred_tenant}%")

    if amenities:
        if isinstance(amenities, str):
            amenities = [a.strip() for a in amenities.split(",") if a.strip()]
        for i, am in enumerate(amenities):
            alias = f"pa{i}"
            joins.append(f"JOIN property_amenities {alias} ON p.property_id = {alias}.property_id")
            conditions.append(f"LOWER({alias}.amenity) LIKE LOWER(?)")
            params.append(f"%{am}%")

    if locality:
        conditions.append("LOWER(p.locality) LIKE LOWER(?)")
        params.append(f"%{locality}%")
    if configuration:
        conditions.append("LOWER(p.configuration) LIKE LOWER(?)")
        params.append(f"%{configuration}%")
    if property_type:
        conditions.append("LOWER(p.property_type) LIKE LOWER(?)")
        params.append(f"%{property_type}%")
    if min_rent is not None:
        conditions.append("p.monthly_rent >= ?")
        params.append(min_rent)
    if max_rent is not None:
        conditions.append("p.monthly_rent <= ?")
        params.append(max_rent)
    if furnishing:
        conditions.append("LOWER(p.furnishing) LIKE LOWER(?)")
        params.append(f"%{furnishing}%")
    if pets_allowed is not None:
        conditions.append("p.pets_allowed = ?")
        params.append(1 if pets_allowed else 0)

    full_query = query + " " + " ".join(joins) + " WHERE " + " AND ".join(conditions) + " LIMIT 10"
    rows = conn.execute(full_query, params).fetchall()

    results = []
    for row in rows:
        prop = dict(row)
        amenities_rows = conn.execute(
            "SELECT amenity FROM property_amenities WHERE property_id = ?",
            (prop["property_id"],)
        ).fetchall()
        prop["amenities"] = [a["amenity"] for a in amenities_rows]
        tenants = conn.execute(
            "SELECT tenant_type FROM property_preferred_tenants WHERE property_id = ?",
            (prop["property_id"],)
        ).fetchall()
        prop["preferred_tenants"] = [t["tenant_type"] for t in tenants]
        results.append(prop)

    conn.close()
    return results


def get_property_details(property_id: str):
    """Get full details for a single property by its ID."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM properties WHERE UPPER(property_id) = UPPER(?)", (property_id,)
    ).fetchone()

    if not row:
        conn.close()
        return None

    prop = dict(row)
    amenities = conn.execute(
        "SELECT amenity FROM property_amenities WHERE property_id = ?",
        (prop["property_id"],)
    ).fetchall()
    prop["amenities"] = [a["amenity"] for a in amenities]

    banks = conn.execute(
        "SELECT bank FROM property_banks WHERE property_id = ?",
        (prop["property_id"],)
    ).fetchall()
    prop["banks"] = [b["bank"] for b in banks]

    tenants = conn.execute(
        "SELECT tenant_type FROM property_preferred_tenants WHERE property_id = ?",
        (prop["property_id"],)
    ).fetchall()
    prop["preferred_tenants"] = [t["tenant_type"] for t in tenants]

    conn.close()
    return prop


def get_agent_contact(agent_id: str):
    """Get agent name and phone by agent_id."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM agents WHERE UPPER(agent_id) = UPPER(?)", (agent_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_company_info():
    """Get company details."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM company LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def get_policies():
    """Get all policies as a dict."""
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM policies").fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}


def get_faqs():
    """Get all FAQs."""
    conn = get_connection()
    rows = conn.execute("SELECT question, answer FROM faqs").fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ─── Chat Session Helpers ────────────────────────────────────────────────────

def create_chat_session(title: str = "New Chat"):
    """Create a new chat session and return its ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_sessions (title, created_at) VALUES (?, ?)",
        (title, datetime.now().isoformat())
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id


def get_all_sessions():
    """Get all chat sessions ordered by most recent first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM chat_sessions ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_session_messages(session_id: int, limit: int = 50):
    """Get messages for a session, most recent N messages."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY id ASC LIMIT ?",
        (session_id, limit)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def save_message(session_id: int, role: str, content: str):
    """Save a chat message to the database."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, role, content, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def update_session_title(session_id: int, title: str):
    """Update a session's title."""
    conn = get_connection()
    conn.execute(
        "UPDATE chat_sessions SET title = ? WHERE id = ?",
        (title, session_id)
    )
    conn.commit()
    conn.close()


def delete_session(session_id: int):
    """Delete a session and all its messages."""
    conn = get_connection()
    conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
