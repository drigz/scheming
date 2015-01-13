import bisect

class BoxLookup(object):
    '''Allows searching for all points within a bounding box.'''

    def __init__(self, matches):
        self.matches = matches

        if len(matches) == 0:
            return

        self.sorted_x_coords = sorted([m.origin[0] for m in matches])
        self.sorted_y_coords = sorted([m.origin[1] for m in matches])
        self.matches_by_x = sorted(matches, key=lambda m: m.origin[0])
        self.matches_by_y = sorted(matches, key=lambda m: m.origin[1])

        self.x_range = max(m.origin[0] for m in matches) - \
                min(m.origin[0] for m in matches)
        self.y_range = max(m.origin[1] for m in matches) - \
                min(m.origin[1] for m in matches)

    def search(self, min_x, min_y, max_x, max_y):

        if len(self.matches) == 0:
            return

        # pick the narrowest side of the box for the primary lookup
        if (max_x - min_x) / self.x_range < (max_y - min_y) / self.y_range:
            sorted_coords = self.sorted_x_coords
            sorted_matches = self.matches_by_x
            first_min, first_max = min_x, max_x
            second_min, second_max = min_y, max_y
            second_coord = lambda m: m.origin[1]
        else:
            sorted_coords = self.sorted_y_coords
            sorted_matches = self.matches_by_y
            first_min, first_max = min_y, max_y
            second_min, second_max = min_x, max_x
            second_coord = lambda m: m.origin[0]

        # find the range of valid primary coordinates
        start = bisect.bisect_left(sorted_coords, first_min)
        end = bisect.bisect_right(sorted_coords, first_max)

        # check range against secondary coordinates and yield results
        for m in sorted_matches[start:end]:
            if second_min <= second_coord(m) <= second_max:
                yield m
