import json
import numpy

class Sigil(object):
    def __init__(self, ops, origin=None, char=None, angle=0):
        '''Given a list of differential ops, and an optional origin, create a
        Sigil instance. If origin is omitted, it is estimated with ops_origin.

        If part of a SigilDict, char is the character this Sigil represents.'''

        self.origin = origin
        if origin is None:
            self.origin = ops_origin(ops)

        self.scale = ops_scale(ops)

        self.ops = ops
        self.char = char

        self.angle = angle

        x1, x2, _, _ = ops_bb(ops)
        self.width = x2 - x1

    @staticmethod
    def from_abs_ops(ops):
        return Sigil(diff_ops(ops))

    def to_dict(self):
        return {
                'origin': self.origin,
                'ops': self.ops,
                }

    def rotated(self, angle=-90):
        '''Return a copy of the sigil rotated clockwise by the given angle.'''

        angle = angle * numpy.pi / 180.0

        matrix = numpy.array([[ numpy.cos(angle), numpy.sin(angle)],
                              [-numpy.sin(angle), numpy.cos(angle)]])

        trans_ops = [(list(matrix.dot(coords)), operator)
                for (coords, operator) in self.ops]
        trans_origin = list(matrix.dot(self.origin))

        return Sigil(ops=trans_ops,
                origin=trans_origin,
                char=self.char,
                angle=self.angle + angle)

    def cmp(self, other):
        if len(self.ops) != len(other.ops):
            print 'different lengths ({}, {}). trying prefix'.format(len(self.ops), len(other.ops))

        ans = []
        for ((x1, y1), c1), ((x2, y2), c2) in zip(self.ops, other.ops):
            s = '{:.2g}'.format(max(abs(x1-x2), abs(y1-y2)))
            if c1 != c2:
                s = s+'*'
            ans.append(s)

        return ', '.join(ans)

    def rescale(self, sf):
        self.origin = [x*sf for x in self.origin]

        for (i, op) in enumerate(self.ops):
            self.ops[i] = [[x*sf for x in op[0]], op[1]]

        self.scale = ops_scale(self.ops)

        x1, x2, _, _ = ops_bb(self.ops)
        self.width = x2 - x1

    def __len__(self):
        return len(self.ops)

    def __str__(self):
        ops_str = '[{}]'.format(', '.join(
            '(({:.2f}, {:.2f}), {})'.format(op[0][0], op[0][1], op[1])
            for op in self.ops))
        return 'Sigil({!r}, {})'.format(self.char, ops_str)


class SigilDict(dict):
    @staticmethod
    def from_json(json_file):
        result = SigilDict()

        for k, v in json.load(json_file).items():
            if isinstance(v, dict):
                v = [v]

            result[k] = [Sigil(char=str(k), **params) for params in v]

        return result

    def to_json(self, json_file):
        json.dump({k: [s.to_dict() for s in v] for (k, v) in self.items()},
                json_file, sort_keys=True, indent=4)

def remove_zero_ops(ops, tol=0.01):
    '''Given a list of absolute ops, remove all ops with a length of less than
    tol (0.01 by default).'''

    assert ops[0][1] == 'm'
    px, py = ops[0][0]

    ans = [ops[0]]
    tol = 0.01

    for (x, y), c in ops[1:]:
        n2 = (x-px) ** 2 + (y-py) ** 2

        if n2 > tol ** 2:
            ans.append( ((x, y), c) )
            px, py = x, y

    return ans

def diff_ops(ops):
    '''Convert a list of absolute ops (eg from a PDF) to differential ops,
    by subtracting the coords of the first 'm' op.'''
    assert ops[0][1] == 'm'
    px, py = ops[0][0]

    ans = []

    for (x, y), c in ops[1:]:
        ans.append( ((x-px, y-py), c) )
        px, py = x, y

    return ans

def ops_bb(ops):
    '''Given a differential ops list, determine the bounding box as
    (min x, max x, min y, max y).'''

    px, py = 0, 0
    xs, ys = [0], [0]

    for (dx, dy), c in ops:
        px += dx
        py += dy
        xs.append(px)
        ys.append(py)

    return (min(xs), max(xs), min(ys), max(ys))

def ops_origin(ops):
    '''Given a differential ops list, estimate the origin, as a vector from
    the initial position. The origin is the (min x)-(min y) corner of the
    bounding box.'''

    min_x, _, min_y, _ = ops_bb(ops)
    return (min_x, min_y)

def ops_height(ops):
    '''Given a differential ops list, determine the height of the bounding
    box.'''

    _, _, min_y, max_y = ops_bb(ops)
    return max_y - min_y

def ops_scale(ops):
    '''Get an arbitrary number indicating the scale of the sigil,
    given some differential operations.

    Uses sum |dx_i| + |dy_i|.'''

    ans = 0

    for (dx, dy), _ in ops:
        ans += abs(dx) + abs(dy)

    return ans
