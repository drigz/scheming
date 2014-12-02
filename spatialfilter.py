class SpatialFilter(object):
    def __init__(self, block_size):
        self.block_size = block_size
        self.valid_blocks = set()

    def get_block(self, pos):
        return (self.round_to_block(pos[0]), self.round_to_block(pos[1]))

    def round_to_block(self, val):
        return self.block_size * round(val / self.block_size)

    def get_neighbours(self, pos):
        for dx in [-self.block_size, 0, self.block_size]:
            for dy in [-self.block_size, 0, self.block_size]:
                yield (pos[0]+dx, pos[1]+dy)

    def mark_valid(self, pos):
        for neighbour in self.get_neighbours(self.get_block(pos)):
            self.valid_blocks.add(neighbour)

    def check(self, pos):
        return self.get_block(pos) in self.valid_blocks
