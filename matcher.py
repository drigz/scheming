'''The implementation of the sigil recognition algorithm. match_sigils() is the
main interface.'''

import math
import re
from intervaltree import Interval, IntervalTree

from collections import Counter

import sigil

def match_sigils(sigdict, abs_ops):
    if len(abs_ops) < 2:
        return []

    ops = sigil.diff_ops(abs_ops)

    matches = match_without_scale(sigdict, ops)
    matches = remove_submatches(matches)
    matches = check_scales(matches, abs_ops, ops)
    matches = check_alignment(sigdict, matches)

    return matches

def match_without_scale(sigdict, ops):
    '''Find all possible matches based only on the directions of each line.

    Returns an array matches of the form:
        [(sigil, start, end)]
    where start and end are the indices of the start & end ops.'''

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
                matches.append( (sig, start, start+len(sig.ops)) )

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
    '''Given a list of matches [(sigil, start, end)], remove all submatches.

    A submatch is a match whose operations are all part of a larger match, eg
    matching a hyphen on the crossbar of an A.'''

    def end_then_start(match):
        _, start, end = match
        return (end, -start)

    deleted = []
    matches = sorted(matches, key=end_then_start)

    supermatch_sig, supermatch_start, supermatch_end = matches[-1]

    for (i, (s, start, end)) in reversed(list(enumerate(matches))):

        if start > supermatch_start or \
                (start == supermatch_start and end < supermatch_end):
            deleted.append((s.char, supermatch_sig.char))
            del matches[i]

        if start < supermatch_start:
            supermatch_sig, supermatch_start, supermatch_end = s, start, end

    # print the frequency of sigils which appear as spurious matches within
    # other sigils
    for (k,v) in sorted(Counter(deleted).items()):
        print k, v

    return matches

def check_scales(matches, abs_ops, ops):
    '''Given a list of matches [(sigil, start, end)], and the ops that they
    come from, calculate the scale factor of each match.

    Matches with inconsistent scale factors are removed.

    Returns a list [(sigil, origin, scale_factor)].'''

    processed_matches = []

    for s, start, end in matches:
        doc_ops = ops[start:end]

        doc_sf = sigil.ops_scale(doc_ops) / s.scale

        # check scale factor of each operation
        scale_error = False
        for sig_op, doc_op in zip(s.ops, doc_ops):
            assert sig_op[1] == doc_op[1], "match_op() isn't doing its job"

            sig_n = math.sqrt(sig_op[0][0]**2 + sig_op[0][1]**2)
            doc_n = math.sqrt(doc_op[0][0]**2 + doc_op[0][1]**2)

            if sig_n < 0.01 or doc_n < 0.01:
                assert sig_n < 0.01 and doc_n < 0.01, "match_op() isn't doing its job"

            else:
                sf_error = doc_n / sig_n / doc_sf
                if sf_error < 0.7 or sf_error > 1.3:
                    scale_error = True

        # get absolute position of sig origin
        start_op = abs_ops[start]
        origin = [a+b*doc_sf for a,b in zip(start_op[0], s.origin)]

        if scale_error is False:
            processed_matches.append((s, origin, doc_sf))

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

    # estimate font metrics based on V, the widest character
    v_width = sigdict['V'][0].width
    gap_width = v_width / 2.58  # gap between adjacent characters
    space_width = gap_width * 2 # the width of a space character

    # for each match, work out the range of possible starts of the next character:
    #   FROM x + width
    #   TO   x + width + gap + space + gap + one more gap for tolerance
    windows = IntervalTree()
    for i, (s, (x, y), sf) in enumerate(matches):
        windows.addi(
                x + sf * s.width,
                x + sf * (s.width + 3 * gap_width + space_width),
                (i, y))

    # work out which matches are legit (because they are > 1 op) and which are
    # aligned with a previous match
    legit_indices = set()
    aligned_with = dict()

    max_y_sep = 0.7
    for i, (s, (x, y), sf) in enumerate(matches):

        # only delete single-operation matches as we're mainly worried about
        # hyphens and underscores
        if len(s.ops) > 1:
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

    print 'deleting', Counter(s.char for i, (s, pos, sf) in
            enumerate(matches) if not check_is_legit(i))

    # finally, exclude invalid matches
    matches = [m for i, m in
            enumerate(matches) if check_is_legit(i)]

    return matches

