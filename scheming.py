import pygame
from pygame.locals import *

import time, math, sys
import argparse

import json

import random

import zoomview, pdf, sigil

from matcher import match_sigils

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

    def __init__(self, abs_ops):
        self.og_lines = pdf.line_ops_to_lines(abs_ops)
        zoomview.ZoomView.__init__(self, self.og_lines)

        self.sigdict = sigil.SigilDict.from_json(open('scheming.json', 'r'))
        self.matches = match_sigils(self.sigdict, abs_ops)

        self.add_matches()

    def add_matches(self):
        lines = self.og_lines + \
                [(ox-1, oy-1, ox+1, oy+1) for (sig, (ox, oy), _) in self.matches] + \
                [(ox+1, oy-1, ox-1, oy+1) for (sig, (ox, oy), _) in self.matches]
        self.set_lines(lines)

    def handle_select(self, ul, lr):
        (ulx, uly) = ul
        (lrx, lry) = lr

        sel_matches = []
        true_origin_y = 99999999999
        for i, (sig, (ox, oy), scale) in enumerate(self.matches):
            if ulx <= ox <= lrx and uly <= oy <= lry:
                sel_matches.append( (sig, (ox, oy), scale) )
                true_origin_y = min(true_origin_y, oy)

        applied = set()
        for (sig, (_, false_origin_y), scale) in sel_matches:
            if sig.char in applied:
                continue
            applied.add(sig.char)

            for m in self.matches:
                if m[0] is sig:
                    m[1][1] += (true_origin_y - false_origin_y) / scale * m[2]

            self.sigdict[sig.char].origin[1] += (true_origin_y - false_origin_y) / scale

        # reposition match markers
        self.add_matches()

        print ''.join(m[0].char for m in sel_matches)
        print 'x:    ', ', '.join('{:6.2f}'.format(m[1][0]) for m in sel_matches)
        print 'y:    ', ', '.join('{:6.2f}'.format(m[1][1]) for m in sel_matches)

    def handle_event(self, ev):
        if ev.type == KEYDOWN and ev.key == K_s:
            print 'Saving scheming.json...'
            self.sigdict.to_json(open('scheming.json', 'w'))

class CaptureView(OriginView):
    '''Used for the identification and classification of undetected letters.

    When a region of the viewed PDF is selected, the operations within that
    region are loaded and the user is asked (on the command line) for the
    character that those operations correspond to.'''

    def __init__(self, abs_ops):
        OriginView.__init__(self, abs_ops)

        self.abs_ops = abs_ops

    def handle_select(self, ul, lr):
        selected_ops = list(extract_ops(self.abs_ops, ul, lr))
        if 'gap' in selected_ops:
            print 'gap in selected ops'
            return

        sig = sigil.Sigil.from_abs_ops(selected_ops)
        c = raw_input('enter char: ')
        if c in self.sigdict:
            print sig.cmp(self.sigdict[c])
        else:
            self.sigdict[c] = sig

if __name__ == '__main__':
    pdf_file = 'P1318-005a.pdf'
    if len(sys.argv) > 2:
        pdf_file = sys.argv[2]

    parser = argparse.ArgumentParser()
    parser.add_argument('--page', '-p', nargs='?', default=0,
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
