import pygame
from pygame.locals import *

import time, math

import json

import random

import zoomview, pdf, sigil

def gencol():
    return tuple(random.randint(0, 255) for _ in range(3))

def extract_ops(ops, ul, lr):
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

def match_sigils(sigdict, abs_ops, tol=0.95):
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
        ((x1, y1), c1) = step1
        ((x2, y2), c2) = step2
        n1 = math.sqrt(x1*x1+y1*y1)
        n2 = math.sqrt(x2*x2+y2*y2)

        if c1 != c2:
            return False
        if n1 < 0.01 or n2 < 0.01:
            return n1 < 0.01 and n2 < 0.01

        return (x1*x2+y1*y2)/n1/n2 > tol
        return abs(x1-x2) < 0.1 and abs(y1-y2) < 0.1

    for (i, op) in enumerate(ops):
        # evaluate current options
        options = [(sig, pos+1) for (sig, pos) in options
                if match_op(op, sig.ops[pos])]

        # try starting a new option
        for sig in sigdict.values():
            if match_op(op, sig.ops[0]):
                options.append((sig, 1))

        # detect finished sigs and remove from options
        new_options = []
        for sig, pos in options:
            if pos == len(sig):
                # get absolute position of sig origin
                start_op = abs_ops[i+1-pos]
                origin = [a+b for a,b in zip(start_op[0], sig.origin)]

                matches.append((sig, origin, i+1-pos, i+1))

            else:
                new_options.append((sig, pos))
        options = new_options

    # filter overlapping matches
    def end_then_start(match):
        _, _, start, end = match
        return (end, -start)

    deleted = []
    matches = list(sorted(matches, key=end_then_start))
    earliest_start = matches[-1][-1]
    es_char = ''
    for (i, (s, _, start, _)) in reversed(list(enumerate(matches))):
        if start >= earliest_start:
            deleted.append((s.char, es_char))
            del matches[i]

        #earliest_start = min(start, earliest_start)
        if start < earliest_start:
            earliest_start = start
            es_char = s.char
    from collections import Counter
    for (k,v) in sorted(Counter(deleted).items()):
        print k, v

    # only return sigil and origin
    return list(match[0:2] for match in matches)

class OriginView(zoomview.ZoomView):
    def __init__(self, abs_ops):
        self.og_lines = pdf.line_ops_to_lines(abs_ops)
        zoomview.ZoomView.__init__(self, self.og_lines)

        self.sigdict = sigil.SigilDict.from_json(open('scheming.json', 'r'))
        self.matches = match_sigils(self.sigdict, abs_ops)

        self.add_matches()

    def add_matches(self):
        lines = self.og_lines + \
                [(ox-1, oy-1, ox+1, oy+1) for (sig, (ox, oy)) in self.matches] + \
                [(ox+1, oy-1, ox-1, oy+1) for (sig, (ox, oy)) in self.matches]
        self.set_lines(lines)

    def handle_select(self, ul, lr):
        (ulx, uly) = ul
        (lrx, lry) = lr

        sel_matches = []
        true_origin_y = 99999999999
        for (sig, (ox, oy)) in self.matches:
            if ulx <= ox <= lrx and uly <= oy <= lry:
                sel_matches.append( (sig, (ox, oy)) )
                true_origin_y = min(true_origin_y, oy)

        applied = set()
        for (sig, (_, false_origin_y)) in sel_matches:
            if sig.char in applied:
                continue
            applied.add(sig.char)

            for m in self.matches:
                if m[0] is sig:
                    m[1][1] += true_origin_y - false_origin_y

            self.sigdict[sig.char].origin[1] += true_origin_y - false_origin_y

        # reposition match markers
        self.add_matches()

        print ''.join(m[0].char for m in sel_matches)
        print ', '.join('{:.2f}'.format(m[1][0]) for m in sel_matches)
        print ', '.join('{:.2f}'.format(m[1][1]) for m in sel_matches)

class CaptureView(OriginView):
    def __init__(self, abs_ops):
        OriginView.__init__(self, abs_ops)

        self.abs_ops = abs_ops

    def handle_select(self, ul, lr):
        selected_ops = list(extract_ops(self.abs_ops, ul, lr))
        if 'gap' in selected_ops:
            print 'gap in selected ops'
            return

        sig = sigil.Sigil.from_abs_ops(selected_ops)
        sigdict = sigil.SigilDict.from_json(open('scheming.json', 'r'))
        c = raw_input('enter char: ')
        if c in sigdict:
            print sig.cmp(sigdict[c])
        else:
            sigdict[c] = sig
            sigdict.to_json(open('scheming.json', 'w'))
