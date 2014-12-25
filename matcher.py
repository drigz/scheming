'''The implementation of the sigil recognition algorithm. match_sigils() is the
main interface.'''

import math
import re
from intervaltree import Interval, IntervalTree

from collections import defaultdict, Counter

import sigil

class Match(object):
    def __init__(self, sig, start):
        self.sig = sig
        self.start = start
        self.end = start + len(sig.ops)

    def __iter__(self):
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

    for sig in sum(sigdict.values(), []):

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
                if len_error > 0.2:
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

    # for each match, work out the range of possible starts of the next character:
    #   FROM x + width
    #   TO   x + width + gap + space + gap + one more gap for tolerance
    windows = IntervalTree()
    for i, m in enumerate(matches):
        x, y = m.origin
        windows.addi(
                x + m.sf * m.sig.width + epsilon,
                x + m.sf * (m.sig.width + 3 * gap_width + space_width),
                (i, y))

    # work out which matches are legit (because they are > 1 op) and which are
    # aligned with a previous match
    legit_indices = set()
    aligned_with = dict()

    max_y_sep = 0.7
    for i, m in enumerate(matches):
        x, y = m.origin

        # only delete single-operation matches as we're mainly worried about
        # hyphens and underscores
        if len(m.sig.ops) > 1:
            legit_indices.add(i)
            continue

        # first use the windows to work out which matches are the right
        # x-distance away to be the preceding character, then check if they're
        # on the same line
        for window in windows[x]:
            (window_i, window_y) = window.data
            if abs(y - window_y) < max_y_sep:
                aligned_with[i] = window_i
                break

    # now, work out which single-operation matches are legit, as they are
    # aligned with a previous character. the recursive search allows several
    # underscores in a row, as long as they're preceded by another character,
    # eg A___B.
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

    print '[check_alignment]: deleting', Counter(m.sig.char for i, m in
            enumerate(matches) if not check_is_legit(i))

    # finally, exclude invalid matches
    matches = [m for i, m in
            enumerate(matches) if check_is_legit(i)]

    return matches

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
