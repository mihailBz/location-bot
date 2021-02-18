import psycopg2
import os

__connection = None
dbname = os.getenv('DBNAME')
user = os.getenv('DBUSER')
password = os.getenv('DBPASSWORD')
host = os.getenv('DBHOST')


def get_connection():
    global __connection

    if __connection is None:
        __connection = psycopg2.connect(dbname=dbname, user=user,
                                        password=password,
                                        host=host)
    return __connection


def init_db(force=False):
    conn = get_connection()
    cursor = conn.cursor()
    if force:
        cursor.execute('DROP TABLE IF EXISTS places')

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS places (
        id          serial,
        chat_id     INTEGER NOT NULL,
        location    POINT,
        address     VARCHAR(100),
        photo       BYTEA
        )
    """)
    conn.commit()


def add_place(chat_id, location, address, photo):
    conn = get_connection()

    cursor = conn.cursor()
    cursor.execute('INSERT INTO places (chat_id, location, address, photo) VALUES (%s, %s, %s, %s)',
                   (chat_id, location, address, photo))
    conn.commit()


def get_location(chat_id):
    conn = get_connection()

    cursor = conn.cursor()
    cursor.execute('SELECT id, location from places WHERE chat_id = %s', (chat_id,))
    locations = cursor.fetchall()
    conn.commit()
    return locations


def get_data_by_location(chat_id, location_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT location, address, photo from places WHERE chat_id = %s and id = ANY(%s)',
                   (chat_id, location_id))
    data = cursor.fetchall()
    conn.commit()
    return data


def get_last_locations(chat_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT location, address, photo from places order by id desc limit 10')
    data = cursor.fetchall()
    conn.commit()
    return data


def drop_users_data(chat_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM places where chat_id = %s', (chat_id,))
    conn.commit()
