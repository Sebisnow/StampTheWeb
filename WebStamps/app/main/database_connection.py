import pymysql


def connect_to_database(host='localhost',
                        user='root',
                        password='',
                        port=3306,
                        db='regularstamps',
                        charset='utf8mb4',
                        cursorclass=pymysql.cursors.DictCursor):
    return pymysql.connect(host=host,
                           user=user,
                           password=password,
                           db=db,
                           port=port,
                           charset=charset,
                           cursorclass=cursorclass)


def execute_on_database(query, args):
    connection = connect_to_database()
    try:
        with connection.cursor() as cursor:
            cursor.execute('USE regularstamps')
            cursor.fetchall()
            cursor.execute(query, args)
            result = cursor.fetchall()
        connection.commit()
    finally:
        connection.close()
    return result
