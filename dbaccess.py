from sqlite3 import dbapi2 as sqlite3
import sys

class State(object):
    New = 0
    Working = 1
    Failed = 2
    Succeeded = 3
    Deleted = 4

def connect_db(db_path):
    """Connects to the specific database."""
    rv = sqlite3.connect(db_path)
    rv.row_factory = sqlite3.Row
    return rv

def init_db(db_path, schema_path):
    """Initializes the database."""
    db = connect_db(db_path)
    with open(schema_path) as f:
        db.cursor().executescript(f.read())
    db.commit()

if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'initdb':
        init_db(sys.argv[2], sys.argv[3])
        print('Initialized the database.')
    else:
        print('usage: {} initdb <db_path> <schema_path>')
        sys.exit(1)


