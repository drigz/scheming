import os
from flask import Flask, abort, g, render_template, request, redirect, send_from_directory, url_for
from werkzeug import secure_filename
from dbaccess import State, connect_db

ALLOWED_EXTENSIONS = set(['pdf'])

BASE_PATH = '/usr/local/scheming'

app = Flask('scheming')
app.config.update({
    'UPLOAD_FOLDER': os.path.join(BASE_PATH, 'uploads/'),
    'RESULT_FOLDER': os.path.join(BASE_PATH, 'results/'),
    'DATABASE': os.path.join(BASE_PATH, 'scheming.db'),
    'DEBUG': True,
})

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db(app.config['DATABASE'])
    return g.sqlite_db

@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

def header(title):
    return '''
    <!doctype html>

    <head>
        <title>'''+title+'''</title>

        <script src="https://ajax.googleapis.com/ajax/libs/jquery/1.11.1/jquery.min.js"></script>
        <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.1/css/bootstrap.min.css">
        <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.1/css/bootstrap-theme.min.css">
        <script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.1/js/bootstrap.min.js"></script>
        <script src="'''+url_for('static', filename='bootstrap-filestyle.min.js')+'''"></script>
    </head>
    <body>
        <div class="container">
            <div class="row">
                <div class="col-md-8 col-md-offset-2">
                    <h1>'''+title+'''</h1>
                </div>
            </div>
    '''

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    db = get_db()

    if request.method == 'POST':
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            cur = db.execute('insert into uploaded (original_filename, state) values (?, ?)',
                    [filename, State.New])
            db.commit()

            id = str(cur.lastrowid)

            file.save(os.path.join(app.config['UPLOAD_FOLDER'], id+'.pdf'))
            return redirect(url_for('status', id=id))

    return render_template('index.html',
            title='Searchable Schematics')

@app.route('/status/<id>')
def status(id):
    db = get_db()
    cur = db.execute('select state from uploaded where id = ?', [id])
    states = cur.fetchall()

    if len(states) == 0:
        abort(404)

    return render_template('status.html',
            title='Searchable Schematics',
            id=id, state=states[0][0], State=State)

@app.route('/result/<id>')
def result(id):
    db = get_db()
    cur = db.execute('select state, original_filename from uploaded where id = ?', [id])
    rows = cur.fetchall()

    if len(rows) == 0:
        abort(404)

    state, original_filename = rows[0]
    new_filename = adjust_filename(original_filename)

    if state != State.Succeeded:
        return redirect(url_for('status', id=id))

    return send_from_directory(
            app.config['RESULT_FOLDER'], id + '.pdf',
            as_attachment=True, attachment_filename=new_filename)

def adjust_filename(filename):
    '''Add '_searchable' to the filename to make it clear it's been
    processed.'''
    
    root, ext = os.path.splitext(filename)
    return root + '_searchable' + ext

@app.route('/delete/<id>', methods=['POST'])
def delete(id):

    db = get_db()
    cur = db.execute('select state from uploaded where id = ?', [id])
    rows = cur.fetchall()

    if len(rows) == 0:
        abort(404)

    state = rows[0][0]

    if state == State.Succeeded:
        secure_delete(os.path.join(app.config['UPLOAD_FOLDER'], id + '.pdf'))
        secure_delete(os.path.join(app.config['RESULT_FOLDER'], id + '.pdf'))

        db.execute('update uploaded set state = ? where id = ?', [State.Deleted, id])
        db.commit()

    return redirect(url_for('status', id=id))

def secure_delete(path):
    '''Overwrite a file with zeros before deleting it.'''

    size = os.stat(path).st_size

    f = open(path, 'w')
    f.write('\0' * size)
    f.flush()
    os.fsync(f.fileno())
    f.close()

    os.remove(path)

if __name__ == '__main__':
    app.run()
