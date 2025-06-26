import sqlite3

conn = sqlite3.connect('C:/Users/User/Documents/GitHub/Vertebrate/code/instance/UserManagement.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM users")
daten = cursor.fetchall()

for zeile in daten:
    print(zeile)

conn.close()

# import sqlite3
# conn = sqlite3.connect('UserManagement.db')
# cursor = conn.cursor()
# cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
# print(cursor.fetchall())
# conn.close()