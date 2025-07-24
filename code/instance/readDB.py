import sqlite3

conn = sqlite3.connect('C:/Users/User/Documents/GitHub/Vertebrate/code/instance/UserManagement.db')
cursor = conn.cursor()
cursor2 = conn.cursor()
cursor.execute("SELECT * FROM users")
cursor2.execute("SELECT * FROM metainfo")
Users = cursor.fetchall()
Metainfo = cursor2.fetchall()

#Read and print the data from the users and metainfo tables
for zeile in Metainfo:
    print(zeile)

for zeile in Users:
    print(zeile)

if Metainfo and len(Metainfo[0]) > 0:
    cluster_id_temp = Metainfo[0][0]
else:
    cluster_id_temp = None

conn.close()




# import sqlite3
# conn = sqlite3.connect('UserManagement.db')
# cursor = conn.cursor()
# cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
# print(cursor.fetchall())
# conn.close()