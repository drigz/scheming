import json

class Sigil(object):
    def __init__(self, ops, origin=None, char=None):
        '''Given a list of differential ops, and an optional origin, create a
        Sigil instance. If origin is omitted, it is estimated with ops_origin.

        If part of a SigilDict, char is the character this Sigil represents.'''

        self.origin = origin
        if origin is None:
            self.origin = ops_origin(ops)

        self.ops = ops
        self.char = char

    @staticmethod
    def from_abs_ops(ops):
        return Sigil(diff_ops(ops))

    def to_dict(self):
        return {
                'origin': self.origin,
                'ops': self.ops,
                }

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

    def __len__(self):
        return len(self.ops)


class SigilDict(dict):
    @staticmethod
    def from_json(json_file):
        return SigilDict((k, Sigil(char=str(k), **v)) for (k, v) in json.load(json_file).items())

    def to_json(self, json_file):
        json.dump({k: v.to_dict() for (k, v) in self.items()}, json_file)

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

def ops_origin(ops):
    '''Given a differential ops list, estimate the origin, as a vector from
    the initial position. The origin is the (min x)-(max y) corner of the
    bounding box.'''

    px, py = 0, 0
    ox, oy = 0, 0

    for (dx, dy), c in ops:
        px += dx
        py += dy

        ox = min(px, ox)
        oy = max(py, oy)

    return (ox, oy)

