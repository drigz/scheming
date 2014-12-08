import pygame
from pygame.locals import *

import time, math, sys

import json

import random

import zoomview, pdf, sigil
from spatialfilter import SpatialFilter

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

def match_sigils(sigdict, abs_ops, tol=0.93):
    if len(abs_ops) < 2:
        return []

    ops = sigil.diff_ops(abs_ops)

    # loop state: an array of (sigil, pos) where sigil is a sigil that
    # partially matches the most recent ops, and pos is the number of recent
    # ops that are matched.
    options = []

    # loop result: an array of (sigil, origin, start, end)
    # where origin is the x,y coords of the sigil origin, and
    # start and end are the indexes of the start & end ops (used to detect
    # overlapping sigils)
    matches = []

    def match_op(step1, step2):
        '''Compare two operations and return True if:
        - they are the same operation type (ie pen up/pen down)
        - and they are in the same direction'''
        ((x1, y1), c1) = step1
        ((x2, y2), c2) = step2
        n1 = math.sqrt(x1*x1+y1*y1)
        n2 = math.sqrt(x2*x2+y2*y2)

        if c1 != c2:
            return False
        if n1 < 0.01 or n2 < 0.01:
            return n1 < 0.01 and n2 < 0.01
 
        # match operations (2d vectors) on angle between them
        return (x1*x2+y1*y2)/n1/n2 > tol

        # match operations (2d vectors) on absolute difference
        # return abs(x1-x2) < 0.1 and abs(y1-y2) < 0.1

    # these variables are used to avoid matching a sigil
    # when the previous or next operation continues the line
    is_possible_start = is_possible_end = True

    for (i, op) in enumerate(ops):
        operator = op[-1]

        if i+1 < len(ops):
            is_possible_end = ops[i+1][-1] == 'm'
        else:
            is_possible_end = True

        # evaluate current options
        options = [(sig, pos+1) for (sig, pos) in options
                if match_op(op, sig.ops[pos])]

        # try starting a new option
        if is_possible_start:
            for sig in sigdict.values():
                if match_op(op, sig.ops[0]):
                    options.append((sig, 1))

        # detect finished sigs and remove from options
        new_options = []
        for sig, pos in options:
            if pos == len(sig):
                if is_possible_end:
                    matches.append((sig, i+1-pos, i+1))
                # if the sigil couldn't end here, it's spurious, so discard it
            else:
                new_options.append((sig, pos))
        options = new_options

        # for the next iteration
        is_possible_start = operator == 'm'

    # filter overlapping matches
    ############################

    def end_then_start(match):
        _, start, end = match
        return (end, -start)

    deleted = []
    matches = list(sorted(matches, key=end_then_start))
    earliest_start = matches[-1][-1]
    es_char = ''
    for (i, (s, start, _)) in reversed(list(enumerate(matches))):
        if start >= earliest_start:
            deleted.append((s.char, es_char))
            del matches[i]

        if start < earliest_start:
            earliest_start = start
            es_char = s.char

    # print the frequency of sigils which appear as spurious matches within
    # other sigils
    from collections import Counter
    for (k,v) in sorted(Counter(deleted).items()):
        print k, v

    processed_matches = []

    # determine scale factors and filter matches with inconsistent scales
    #####################################################################

    for s, start, end in matches:
        # walking a tightrope of fenceposts...
        doc_ops = ops[start:end]

        doc_sf = sigil.ops_scale(doc_ops) / s.scale

        # check scale factor of each operation
        scale_error = False
        for sig_op, doc_op in zip(s.ops, doc_ops):
            assert sig_op[1] == doc_op[1] # safety net

            sig_n = math.sqrt(sig_op[0][0]**2 + sig_op[0][1]**2)
            doc_n = math.sqrt(doc_op[0][0]**2 + doc_op[0][1]**2)

            if sig_n < 0.01 or doc_n < 0.01:
                if not (sig_n < 0.01 and doc_n < 0.01):
                    scale_error = 'zero'
            else:
                sf_error = doc_n / sig_n / doc_sf
                if sf_error < 0.7 or sf_error > 1.3:
                    scale_error = 'ratio: {:.2f}'.format(sf_error)

        # get absolute position of sig origin
        start_op = abs_ops[start]
        origin = [a+b*doc_sf for a,b in zip(start_op[0], s.origin)]

        if scale_error is False:
            processed_matches.append((s, origin, doc_sf))
        else:
            pass
            #print 'scale error:', s.char, scale_error

    # filter out single-operation matches far from other letters
    ############################################################

    # return early if there are no multi-operation letters
    if not any(len(s.ops) > 1 for (s, _, sf) in processed_matches):
        return []

    # first, set the block size to max letter height
    max_height = max(sf*sigil.ops_height(s.ops)
            for (s, _, sf) in processed_matches if len(s.ops) > 1)
    sfilter = SpatialFilter(max_height)

    # then allow regions around letters
    for s, pos, _ in processed_matches:
        if len(s.ops) > 1:
            sfilter.mark_valid(pos)

    # finally, exclude invalid matches
    processed_matches = [(s, pos, sf) for (s, pos, sf) in processed_matches if sfilter.check(pos)]

    return processed_matches

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
        for (sig, (ox, oy), scale) in self.matches:
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
        print ', '.join('{:.2f}'.format(m[1][0]) for m in sel_matches)
        print ', '.join('{:.2f}'.format(m[1][1]) for m in sel_matches)

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
    if len(sys.argv) != 3 or sys.argv[1] not in ['capture', 'origin']:
        print 'usage: {} capture|origin schematic.pdf'.format(sys.argv[0])

    pdf_file = 'P1318-005a.pdf'
    if len(sys.argv) > 2:
        pdf_file = sys.argv[2]

    rdr = pdf.SchematicReader(open(pdf_file, 'rb'))
    line_ops = rdr.get_line_ops(1)

    if sys.argv[1] == 'capture':
        v = CaptureView(line_ops)
        v.show()

    elif sys.argv[1] == 'origin':
        v = OriginView(line_ops)
        v.show()

    elif sys.argv[1] == 'bench':
        sigdict = sigil.SigilDict.from_json(open('scheming.json', 'r'))

        t = time.time()
        matches = match_sigils(sigdict, line_ops)
        print 'matched {} symbols in {:.3f} seconds'.format(len(matches), time.time() - t)
