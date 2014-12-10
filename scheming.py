import pygame
from pygame.locals import *

import time, math, sys

import json
import re

import random

import zoomview, pdf, sigil
from spatialfilter import SpatialFilter

from intervaltree import Interval, IntervalTree

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

    # loop result: an array of (sigil, start, end)
    # where origin is the x,y coords of the sigil origin, and
    # start and end are the indexes of the start & end ops (used to detect
    # overlapping sigils)
    matches = []

    def match_op(step1, step2):
        '''Compare two operations and return True if they are in the same direction.'''

        ((x1, y1), c1) = step1
        ((x2, y2), c2) = step2
        n1 = math.sqrt(x1*x1+y1*y1)
        n2 = math.sqrt(x2*x2+y2*y2)

        if n1 < 0.01 or n2 < 0.01:
            return n1 < 0.01 and n2 < 0.01
 
        return (x1*x2+y1*y2)/n1/n2 > tol

    # wrap in ms to make it easier for the regex to match the divisions between
    # continuous lines
    all_opcodes = 'm{}m'.format(''.join(opcode for (_,opcode) in ops))

    for sig in sigdict.values():
        sig_regex = '(?=m{}m)'.format(''.join(opcode for (_,opcode) in sig.ops))

        possible_starts = [m.start() for m in
                re.finditer(sig_regex, all_opcodes)]

        for start in possible_starts:
            doc_ops = ops[start : start+len(sig.ops)]

            if all(match_op(doc_op, sig_op) for (doc_op, sig_op) in zip(doc_ops, sig.ops)):
                matches.append( (sig, start, start+len(sig.ops)) )

    # filter overlapping matches
    ############################

    def end_then_start(match):
        _, start, end = match
        return (end, -start)

    deleted = []
    matches = list(sorted(matches, key=end_then_start))
    overlapper_sig, overlapper_start, overlapper_end = matches[-1]
    for (i, (s, start, end)) in reversed(list(enumerate(matches))):
        if start > overlapper_start or \
                (start == overlapper_start and end < overlapper_end):
            deleted.append((s.char, overlapper_sig.char))
            del matches[i]

        if start < overlapper_start:
            overlapper_start, overlapper_end = start, end
            overlapper_sig = s

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

    matches = processed_matches

    # filter out single-operation matches that aren't aligned with characters
    # just beforehand (ie, no underscores, slashes or hyphens at the start of
    # a word)
    #########################################################################

    # estimate font metrics based on V, the widest character
    v_width = sigdict['V'].width
    gap_width = v_width / 2.58
    space_width = gap_width * 2

    # for each sigil, work out the range of possible starts of the next sigil:
    #   FROM x + width
    #   TO   x + width + gap + space + gap + one more gap for tolerance
    windows = IntervalTree()
    for i, (s, (x, y), sf) in enumerate(matches):
        windows.addi(
                x + sf * s.width,
                x + sf * (s.width + 3 * gap_width + space_width),
                (i, y))

    # work out which matches are not spurious (because they are > 1 op)
    # and which are aligned with a previous match
    legit_indices = set()
    aligned_with = dict()

    max_y_sep = 0.7
    for i, (s, (x, y), sf) in enumerate(matches):

        # only delete single-operation matches as these are most prone to
        # spurious matches
        if len(s.ops) > 1:
            legit_indices.add(i)
            continue

        # check all windows containing x
        for window in windows[x]:
            (window_i, window_y) = window.data
            if abs(y - window_y) < max_y_sep:
                aligned_with[i] = window_i
                break

    # now: extend it. if a match is aligned with a legit match, it's legit.
    deleted = set()

    def check_is_legit(i):
        if i in legit_indices:
            return True
        if i in deleted or i not in aligned_with:
            return False

        result = check_is_legit(aligned_with[i])

        if result:
            legit_indices.add(i)
        else:
            deleted.add(i)

        return result

    print 'deleting', Counter(s.char for i, (s, pos, sf) in
            enumerate(matches) if not check_is_legit(i))

    # finally, exclude invalid matches
    matches = [m for i, m in
            enumerate(matches) if check_is_legit(i)]

    return matches

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
    if len(sys.argv) not in [2,3] or sys.argv[1] not in ['capture', 'origin', 'bench']:
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
