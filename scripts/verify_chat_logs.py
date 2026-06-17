from dotenv import load_dotenv
load_dotenv()

from database.db import get_connection
from database.tables.chat_logs import create_chat_logs_table


def main():
    conn = get_connection()
    try:
        create_chat_logs_table(conn)

        test_question = "What causes tooth decay?"
        test_answer = "Tooth decay occurs when plaque bacteria produce acids that erode tooth enamel."
        test_time = 1250
        test_sources = 3

        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO chat_logs (question, answer, response_time_ms, sources_count) VALUES (%s, %s, %s, %s)",
                (test_question, test_answer, test_time, test_sources),
            )
            conn.commit()
            inserted_id = cursor.lastrowid

            cursor.execute("SELECT * FROM chat_logs WHERE id = %s", (inserted_id,))
            row = cursor.fetchone()

            cursor.execute("DELETE FROM chat_logs WHERE id = %s", (inserted_id,))
            conn.commit()

        assert row is not None, "No row returned"
        assert row["question"] == test_question
        assert row["answer"] == test_answer
        assert row["response_time_ms"] == test_time
        assert row["sources_count"] == test_sources

        print("✓ chat_logs: insert/select/delete OK")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
