import argparse
import time
import traceback
import os

from dbaccess import connect_db, State
import annotate

BASE_PATH = '/usr/local/scheming'

DATABASE = os.path.join(BASE_PATH, 'scheming.db')
UPLOADS = os.path.join(BASE_PATH, 'uploads/')
RESULTS = os.path.join(BASE_PATH, 'results/')
CHECK_INTERVAL = 1 # number of seconds to wait between checking for work

def main():
    parser = argparse.ArgumentParser(
            description='Processes work items that are added to the database by the web interface.')
    args = parser.parse_args()

    w = Worker()
    w.connect()
    w.work_loop()

class Worker(object):
    def connect(self):
        self.db = connect_db(DATABASE)

    def work_loop(self):
        '''Repeatedly try to do work items.'''

        while True:
            if not self.try_to_work():
                time.sleep(CHECK_INTERVAL)

    def try_to_work(self):
        '''Try to load and execute a work item from the database. Update the
        database while we're working on it, and finally with the
        success/failure of the work operation.

        Returns True iff it has processed a work item.'''

        # choose an item of work from the database
        cur = self.db.execute('select id from uploaded where state = ? limit 1', [State.New])
        self.db.commit()
        row = cur.fetchone()

        if row is None:
            # nothing to do
            return False

        id = row[0]

        # take the work for ourself
        cur = self.db.execute('update uploaded set state=? where state = ? and id = ?',
                [State.Working, State.New, id])
        self.db.commit()

        if cur.rowcount != 1:
            # someone got it before us
            return False

        # do the work and catch any exceptions
        try:
            print 'Starting work on', id

            start_time = time.time()
            self.do_work(id)

        except:
            new_state = State.Failed
            error_msg = traceback.format_exc()

            print 'Failed to process', id
            print error_msg,

        else:
            new_state = State.Succeeded
            error_msg = ''

            print 'Successfully processed', id

        time_taken = time.time() - start_time

        # record the results
        self.db.execute('update uploaded set state=?, error_msg=?, time_taken=? where id=?',
                [new_state, error_msg, time_taken, id])
        self.db.commit()

        return True

    def do_work(self, id):
        pdf_filename = '{}.pdf'.format(id)

        input_filename = os.path.join(UPLOADS, pdf_filename)
        output_filename = os.path.join(RESULTS, pdf_filename)

        annotate.annotate(input_filename, output_filename)


if __name__ == '__main__':
    main()
