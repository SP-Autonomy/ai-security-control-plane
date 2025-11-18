# control_plane/database.py

import sqlite3
from datetime import datetime

def init_db():
    """Initialize the control plane database with proper schema"""
    conn = sqlite3.connect('control_plane.db')
    cursor = conn.cursor()
    
    # Policies table with enabled flag
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS policies (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            rego_policy TEXT NOT NULL,
            enabled BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Audit log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            agent_id TEXT,
            action TEXT,
            policy_id TEXT,
            decision TEXT,
            details TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def get_policy_status(policy_id: str) -> bool:
    """Get the enabled status of a policy"""
    conn = sqlite3.connect('control_plane.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT enabled FROM policies WHERE id = ?', (policy_id,))
    result = cursor.fetchone()
    conn.close()
    
    return bool(result[0]) if result else False

def toggle_policy(policy_id: str, enabled: bool) -> bool:
    """Toggle a policy's enabled status"""
    conn = sqlite3.connect('control_plane.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE policies 
        SET enabled = ?, updated_at = ? 
        WHERE id = ?
    ''', (int(enabled), datetime.utcnow().isoformat(), policy_id))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return success

def get_all_policies():
    """Get all policies with their current status"""
    conn = sqlite3.connect('control_plane.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, name, description, enabled, updated_at 
        FROM policies 
        ORDER BY name
    ''')
    
    policies = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return policies