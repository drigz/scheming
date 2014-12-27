import pygame
from pygame.locals import *

import time, math, sys
import argparse

import json

import random

import numpy

import zoomview, pdf, sigil

from matcher import match_sigils, count_ambiguous

def gencol():
    return tuple(random.randint(0, 255) for _ in range(3))

def extract_ops(ops, ul, lr):
    '''Given a list ops of drawing operations and the coordinates (ul, lr) of a
    bounding box, return only the operations with coordinates inside the
    bounding box. Each run of operations outside the bounding box is replaced
    by the string 'gap'.

    Returns a generator.'''

    (ulx, uly) = ul
    (lrx, lry) = lr
    started = stopped = False
    for (x, y), c in ops:
        if ulx <= x <= lrx and uly <= y <= lry:
            if stopped:
                yield 'gap'
                stopped = False

            started = True

            yield ((x, y), c)
        elif started:
            stopped = True

class OriginView(zoomview.ZoomView):
    '''Used for testing matched sigils and correction their origins.

    When a region is selected in the window, all matched sigils within the
    window are identified. They should all be on one horizontal line of text.

    The script corrects the y value of the origin of each sigil so that all
    origins lie on one line, ie all sigils have their origin y value set to
    that of the sigil with the minimum origin y value.

    The matched characters and new origin values are also printed.'''

    def __init__(self, abs_ops, skip_alignment_check=True):
        self.og_lines = pdf.line_ops_to_lines(abs_ops)
        zoomview.ZoomView.__init__(self, self.og_lines)

        self.sigdict = sigil.SigilDict.from_json(open('scheming.json', 'r'))
        self.matches = match_sigils(self.sigdict, abs_ops, skip_alignment_check=skip_alignment_check)

        self.add_matches()

        self.removing_match = False

    def add_matches(self):
        origins = [m.origin for m in self.matches]
        lines = self.og_lines + \
                [(ox-1, oy-1, ox+1, oy+1) for (ox, oy) in origins] + \
                [(ox+1, oy-1, ox-1, oy+1) for (ox, oy) in origins]
        self.set_lines(lines)

    def handle_select(self, ul, lr):
        (ulx, uly) = ul
        (lrx, lry) = lr

        sel_matches = []
        for i, m in enumerate(self.matches):
            if ulx <= m.origin[0] <= lrx and uly <= m.origin[1] <= lry:
                sel_matches.append( (i, m) )

        print ''.join(m.sig.char for (i, m) in sorted(sel_matches, key=lambda x: x[1].origin[0]))
        print 'x:    ', ', '.join('{:6.2f}'.format(m.origin[0]) for (i, m) in sel_matches)
        print 'y:    ', ', '.join('{:6.2f}'.format(m.origin[1]) for (i, m) in sel_matches)
        print 'scale:', ', '.join('{:6.3f}'.format(m.sf) for (i, m) in sel_matches)

        if len(sel_matches) <= 3:
            # for few matches, we delete one
            print 'which match do you want to delete? options:'
            print ', '.join(repr(m.sig.char) for (i, m) in sel_matches)

            self.sel_matches = sel_matches
            self.removing_match = True
            return

        ambi = count_ambiguous(m for i, m in sel_matches)
        if len(ambi) > 0:
            print 'there are still ambiguous matches:', ambi
            print 'delete them before correcting origins'
            return

        # otherwise perform origin correction
        true_origin_y = numpy.median(numpy.array([m.origin[1] for (i, m) in sel_matches]))

        applied = []
        for i, m in sel_matches:
            false_origin_y = m.origin[1]

            if any(m.sig is s for s in applied):
                continue
            applied.append(m.sig)

            for m2 in self.matches:
                if m2.sig is m.sig:
                    m2.origin[1] += (true_origin_y - false_origin_y) / m.sf * m2.sf

            m.sig.origin[1] += (true_origin_y - false_origin_y) / m.sf

        # reposition match markers
        self.add_matches()

    def handle_event(self, ev):
        if self.removing_match:
            if hasattr(ev, 'unicode') and len(ev.unicode) == 1:
                rem_matches = [(i, m) for (i, m) in self.sel_matches if m.sig.char == ev.unicode.encode('utf-8')]
                if len(rem_matches) != 1:
                    print 'incorrect number of matches:', repr([m.sig.char for (i, m) in rem_matches])
                del self.matches[rem_matches[0][0]]
                self.add_matches()
                self.removing_match = False

        elif ev.type == KEYDOWN and ev.key == K_s:
            print 'Saving scheming.json...'
            self.sigdict.to_json(open('scheming.json', 'w'))

class CaptureView(OriginView):
    '''Used for the identification and classification of undetected letters.

    When a region of the viewed PDF is selected, the operations within that
    region are loaded and the user is asked (on the command line) for the
    character that those operations correspond to.'''

    def __init__(self, abs_ops):
        OriginView.__init__(self, abs_ops, skip_alignment_check=False)

        self.abs_ops = abs_ops

        self.capturing_sigil = False

    def handle_select(self, ul, lr):
        (ulx, uly) = ul
        (lrx, lry) = lr

        selected_ops = list(extract_ops(self.abs_ops, ul, lr))
        if 'gap' in selected_ops:
            print 'gap in selected ops'
            return

        if 0:
            for (x, y), c in sigil.diff_ops(selected_ops):
                print '{:4.2f},{:4.2f} {}'.format(x, y, c)
            return

        self.capturing_sigil = True
        self.new_sigil = sigil.Sigil.from_abs_ops(selected_ops)
        print 'enter char...'

    def handle_event(self, ev):
        if self.capturing_sigil:
            if not hasattr(ev, 'unicode') or len(ev.unicode) != 1:
                # modifier key/click
                return

            c = ev.unicode.encode('utf-8')

            print 'char:', repr(c)
            if c in self.sigdict:
                self.sigdict[c].append(self.new_sigil)
            else:
                self.sigdict[c] = [self.new_sigil]

            self.capturing_sigil = False

        else:
            super(CaptureView, self).handle_event(ev)

if __name__ == '__main__':
    pdf_file = 'P1318-005a.pdf'
    if len(sys.argv) > 2:
        pdf_file = sys.argv[2]

    parser = argparse.ArgumentParser()
    parser.add_argument('--page', '-p', nargs='?', default=0, type=int,
            help="page to process [default: 0]")
    parser.add_argument('mode',
            help='operation mode: capture, origin or bench')
    parser.add_argument('input', nargs='?', default='P1318-005a.pdf',
            help='path to input PDF [default: P1318-005a.pdf]')
    args = parser.parse_args()

    rdr = pdf.SchematicReader(open(args.input, 'rb'))
    line_ops = rdr.get_line_ops(args.page)

    if args.mode == 'capture':
        v = CaptureView(line_ops)
        v.show()

    elif args.mode == 'origin':
        v = OriginView(line_ops)
        v.show()

    elif args.mode == 'bench':
        sigdict = sigil.SigilDict.from_json(open('scheming.json', 'r'))

        t = time.time()
        matches = match_sigils(sigdict, line_ops)
        print 'matched {} symbols in {:.3f} seconds'.format(len(matches), time.time() - t)
