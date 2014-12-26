'''The implementation of the sigil recognition algorithm. match_sigils() is the
main interface.'''

import math
import re
from boxlookup import BoxLookup

from collections import defaultdict, Counter

import sigil

class Match(object):
    def __init__(self, sig, start):
        self.sig = sig
        self.start = start
        self.end = start + len(sig.ops)

        # adjacency lists and validity status for alignment check
        self.next_matches = []
        self.prev_matches = []
        self.passes_alignment_check = False


    def get_series(self):
        '''During the alignment check, find all matches which are aligned
        with this one, ie all the characters following this one in the current
        word.'''

        current = self
        result = [self]

        while len(current.next_matches) > 0:
            current = current.next_match()
            result.append(current)

        return result

    def next_match(self):
        '''Return the next aligned match, ie the one with the smallest
        x or y coordinate depending on angle.'''

        if self.sig.angle == 0:
            key = lambda m: m.origin[0]
        elif self.sig.angle == -90:
            key = lambda m: m.origin[1]

        return min(self.next_matches, key=key)

    def __iter__(self):
        '''Hack for compatibility with old tuples.'''

        if hasattr(self, 'origin'):
            return iter( (self.sig, self.origin, self.sf) )
        else:
            return iter( (self.sig, self.start, self.end) )

def match_sigils(sigdict, abs_ops, skip_alignment_check=False):
    if len(abs_ops) < 2:
        return []

    non_zero_abs_ops = sigil.remove_zero_ops(abs_ops)
    ops = sigil.diff_ops(non_zero_abs_ops)

    matches = match_without_scale(sigdict, ops)

    if len(matches) == 0:
        return []

    matches = remove_submatches(matches)
    matches = check_scales(matches, non_zero_abs_ops, ops)

    if not skip_alignment_check:
        matches = check_alignment(sigdict, matches)

        print count_ambiguous(matches)

    return matches

def match_without_scale(sigdict, ops):
    '''Find all possible matches based only on the directions of each line.

    Returns an array matches of the form:
        [Match(sigil, start)]
    where start is the index of the first operation.'''

    matches = []

    # wrap in ms to make it easier for the regex to match the divisions between
    # continuous lines
    all_opcodes = 'm{}m'.format(''.join(opcode for (_,opcode) in ops))

    # combine sigils with rotated copies
    all_sigils = sum(sigdict.values(), [])
    all_sigils = all_sigils + [sig.rotated(-90) for sig in all_sigils]

    for sig in all_sigils:

        # first find all places where the correct sequence of operation types is present
        sig_regex = '(?=m{}m)'.format(''.join(opcode for (_,opcode) in sig.ops))

        possible_starts = [m.start() for m in
                re.finditer(sig_regex, all_opcodes)]

        # now at each position, check the directions of the operations are correct
        for start in possible_starts:
            doc_ops = ops[start : start+len(sig.ops)]

            if all(match_op(doc_op, sig_op) for (doc_op, sig_op) in zip(doc_ops, sig.ops)):
                matches.append( Match(sig, start) )

    return matches

def match_op(step1, step2, tol=0.93):
    '''Compare two operations and return True if they are in the same direction.'''

    ((x1, y1), c1) = step1
    ((x2, y2), c2) = step2
    n1 = math.sqrt(x1*x1+y1*y1)
    n2 = math.sqrt(x2*x2+y2*y2)

    if n1 < 0.01 or n2 < 0.01:
        return n1 < 0.01 and n2 < 0.01

    return (x1*x2+y1*y2)/n1/n2 > tol

def remove_submatches(matches):
    '''Given a list of matches, removing all submatches.

    A submatch is a match whose operations are all part of a larger match, eg
    matching a hyphen on the crossbar of an A.'''

    def end_then_start(match):
        return (match.end, -match.start)

    deleted = []
    matches = sorted(matches, key=end_then_start)

    supermatch = matches[-1]

    for (i, m) in reversed(list(enumerate(matches))):

        if m.start > supermatch.start or \
                (m.start == supermatch.start and m.end < supermatch.end):
            deleted.append((m.sig.char, supermatch.sig.char))
            del matches[i]

        if m.start < supermatch.start:
            supermatch = m

    return matches

def check_scales(matches, abs_ops, ops):
    '''Given a list of matches, and the ops that they come from, calculate the
    scale factor of each match.

    Matches with inconsistent scale factors are removed.

    Returns a list of matches with the sf and origin members added.'''

    processed_matches = []

    for m in matches:
        doc_ops = ops[m.start:m.end]

        doc_sf = sigil.ops_scale(doc_ops) / m.sig.scale

        # check scale factor of each operation
        scale_error = False
        for sig_op, doc_op in zip(m.sig.ops, doc_ops):
            assert sig_op[1] == doc_op[1], "match_op() isn't doing its job"

            sig_n = math.sqrt(sig_op[0][0]**2 + sig_op[0][1]**2)
            doc_n = math.sqrt(doc_op[0][0]**2 + doc_op[0][1]**2)

            if sig_n < 0.01 or doc_n < 0.01:
                assert sig_n < 0.01 and doc_n < 0.01, "match_op() isn't doing its job"

            else:
                len_error = abs(doc_n - sig_n * doc_sf)
                if len_error > 0.3:
                    scale_error = True

        # get absolute position of sig origin
        start_op = abs_ops[m.start]
        origin = [a+b*doc_sf for a,b in zip(start_op[0], m.sig.origin)]

        if scale_error is False:
            m.origin = origin
            m.sf = doc_sf
            processed_matches.append(m)

    return processed_matches


def check_alignment(sigdict, matches):
    '''Filter out single-operation matches that aren't aligned with characters
    just beforehand (ie, no underscores, slashes or hyphens at the start of a
    word).

    To be accepted, a single-operation match must be on the same y level as an
    accepted match (ie on the same line), and must be the right x distance away
    to be the next character.

    The main advantage to this step is that it disambiguates between hyphens
    and underscores.'''

    # we need V to measure the font
    if 'V' not in sigdict:
        return matches

    # estimate font metrics based on V, the widest character
    v_width = sigdict['V'][0].width
    gap_width = v_width / 2.58  # gap between adjacent characters
    space_width = gap_width * 2 # the width of a space character
    epsilon = 0.001 # minimum gap between characters

    # hardcoded y alignment tolerance
    max_y_sep = 0.7

    matches_bl = BoxLookup(matches)

    # for each match, work out the range of possible starts of the next character:
    #   FROM x + width,
    #        y - max_y_sep
    #   TO   x + width + gap + space + gap + one more gap for tolerance,
    #        y + max_y_sep
    # or the corresponding rotated coordinates for a rotated character
    #
    # then, check all matches in this box for alignment and record them
    for i, m in enumerate(matches):
        x, y = m.origin
        assert m.sig.angle in [0, -90]

        if m.sig.angle == 0:
            box = [
                x + m.sf * m.sig.width + epsilon,
                y - max_y_sep,
                x + m.sf * (m.sig.width + 3 * gap_width + space_width),
                y + max_y_sep,
                ]
        elif m.sig.angle == -90:
            box = [
                x - max_y_sep,
                y + m.sf * m.sig.width + epsilon,
                x + max_y_sep,
                y + m.sf * (m.sig.width + 3 * gap_width + space_width),
                ]

        for m2 in matches_bl.search(*box):

            # remove matches at different angles or scales
            if m2.sig.angle != m.sig.angle:
                continue
            if m2.sf/m.sf < 0.9 or 1.1 < m2.sf/m.sf:
                continue

            # add edge to graph
            m2.prev_matches.append(m)
            m.next_matches.append(m2)

    # identify whether matches are in valid series
    for m in matches:
        if m.prev_matches != []:
            # not start of series
            continue

        series = m.get_series()

        if series_is_valid(series):
            for m2 in series:
                m2.passes_alignment_check = True

    print '[check_alignment]: deleting', Counter(m.sig.char for m in
            matches if not m.passes_alignment_check)

    # finally, exclude invalid matches
    matches = [m for m in
            matches if m.passes_alignment_check]

    return matches

def series_is_valid(series):
    '''A series of matches is valid if at least one has more than two
    operations, and doesn't suffer case ambiguity (zZ, xX, wW, vV)'''

    def match_is_valid(m):
        return len(m.sig.ops) > 2 and m.sig.char not in 'zZxXwWvV'

    return any(match_is_valid(m) for m in series)

def count_ambiguous(matches):
    '''Return a Counter() of sigils matching the same operations in the
    document.'''

    sigils_by_position = defaultdict(list)
    for m in matches:
        sigils_by_position[(m.start, len(m.sig.ops))].append(m)

    ctr = Counter()
    for ambiguous in sigils_by_position.values():
        if len(ambiguous) > 1:
            chars = tuple(sorted(m.sig.char for m in ambiguous))
            ctr[chars] += 1

    return ctr
