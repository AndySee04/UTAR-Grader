import sqlite3
from pathlib import Path


def main() -> None:
    db_path = Path(__file__).resolve().parents[1] / "auto_grade.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    before = cur.execute(
        "SELECT COALESCE(question_type, 'NULL'), COUNT(*) "
        "FROM marking_guide GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()

    cur.execute(
        "UPDATE marking_guide "
        "SET question_type = 'structured' "
        "WHERE LOWER(TRIM(question_type)) IN ('short_answer', 'calculation')"
    )
    cur.execute(
        "UPDATE marking_guide "
        "SET question_type = 'open_ended' "
        "WHERE LOWER(TRIM(question_type)) = 'essay'"
    )
    cur.execute(
        "UPDATE marking_guide "
        "SET question_type = 'mcq' "
        "WHERE LOWER(TRIM(question_type)) = 'mcq'"
    )

    conn.commit()

    after = cur.execute(
        "SELECT COALESCE(question_type, 'NULL'), COUNT(*) "
        "FROM marking_guide GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()

    print("DB:", db_path)
    print("Before:", before)
    print("After:", after)

    conn.close()


if __name__ == "__main__":
    main()
