import sqlite3
from fastapi import HTTPException

def get_connection():
    return sqlite3.connect("gtd_database.db")

def init_database():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT NOT NULL
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS next_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT NOT NULL,
        project_id INTEGER REFERENCES projects(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items_pending_review (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT NOT NULL
    )
    """)
    conn.commit()
    cursor.close()
    conn.close()
    
def get_next_action_list():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.description, p.description AS project_description
        FROM (
            SELECT na.*,
                ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY id ASC) AS rn
            FROM next_actions na
            WHERE project_id IS NOT NULL
        ) a
        JOIN projects p ON a.project_id = p.id
        WHERE rn = 1;
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(id=r[0], description=r[1], project=r[2]) for r in rows]

def check_action(action_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM next_actions WHERE id = ?", [action_id])
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Action not found")
    return {"status": "success", "deleted_id": action_id}