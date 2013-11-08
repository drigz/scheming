import pygame
from pygame.locals import *

import random

import numpy

fullscreen = object()

class ZoomView(object):
    def __init__(self, lines, ws=(800, 600)):
        '''Initialises a ZoomView, given a default window sizes and an array of
        lines. Each entry in the array of lines should be a 4-element iterable
        containing the (x,y)-coords of the start and end of the line.'''

        self.lines = numpy.asarray(lines)
        self.ws = ws

    def show(self):
        window = pygame.display.set_mode(self.ws)

        pygame.key.set_repeat(300, 50)

        try:
            self.loop(window)

        finally:
            pygame.display.quit()

    def loop(self, window):
        self.init_view()
        # initialise the view

        moving = False
        selecting = False

        redraw = True

        while True:
            if redraw:
                self.redraw(window)

                if selecting:
                    x, y = og_pos
                    mx, my = pygame.mouse.get_pos()
                    pygame.draw.rect(window, (255, 255, 255),
                            (x, y, mx-x, my-y), 1)

                pygame.display.flip()
                redraw = False

            ev = pygame.event.wait()
            if ev.type == MOUSEBUTTONDOWN:
                if ev.button == 4 or ev.button == 5:
                    zf = 0.8
                    if ev.button == 5:
                        zf = 1/zf

                    ((xl, yl), (xh, yh)) = self.view

                    # map pos to doc
                    (xd, yd) = self.to_doc(ev.pos)

                    # recentre view on pos, and adjust
                    xl, yl, xh, yh = xl-xd, yl-yd, xh-xd, yh-yd
                    xl, yl, xh, yh = zf*xl, zf*yl, zf*xh, zf*yh

                    # set new view
                    self.view = ((xl+xd, yl+yd), (xh+xd, yh+yd))
                    redraw = True

                elif ev.button == 1:
                    og_view = self.view
                    og_pos = ev.pos
                    moving = True
                elif ev.button == 3:
                    og_pos = ev.pos
                    selecting = True

            elif ev.type == MOUSEMOTION:
                if moving:
                    dx, dy = ev.pos[0] - og_pos[0], ev.pos[1] - og_pos[1]

                    ((xl, yl), (xh, yh)) = og_view
                    dvx, dvy = dx / float(self.ws[0]) * (xh-xl), dy / float(self.ws[1]) * (yh-yl)

                    self.view = ((xl-dvx, yl-dvy), (xh-dvx, yh-dvy))

                redraw = moving or selecting

            elif ev.type == MOUSEBUTTONUP:
                if ev.button == 1:
                    moving = False
                elif ev.button == 3:
                    pta = self.to_doc(og_pos)
                    ptb = self.to_doc(ev.pos)

                    ul = (min(pta[0], ptb[0]), min(pta[1], ptb[1]))
                    lr = (max(pta[0], ptb[0]), max(pta[1], ptb[1]))

                    self.handle_select(ul, lr)

                    selecting = False
                    redraw = True

            elif ev.type == KEYDOWN:
                if ev.key == K_RETURN:
                    return


    def init_view(self):
        xs = self.lines[:, [0, 2]]
        ys = self.lines[:, [1, 3]]

        self.last_view = (0, 0, 0, 0)
        self.view = ((numpy.min(xs), numpy.min(ys)), (numpy.max(xs), numpy.max(ys)))

    def to_doc(self, pix_pos):
        ((xl, yl), (xh, yh)) = self.view

        # map pos to doc
        x, y = pix_pos
        xd = xl + x / float(self.ws[0]) * (xh - xl)
        yd = yl + y / float(self.ws[1]) * (yh - yl)

        return (xd, yd)

    def from_doc(self, doc_pos):
        x, y = doc_pos
        ((xl, yl), (xh, yh)) = self, view

        return (self.ws[0] * (x - xl) / float(xh - xl),
                self.ws[1] * (y - yl) / float(yh - yl))

    def redraw(self, window):
        random.seed(0)
        window.fill((0, 0, 0))

        dl = pygame.draw.line
        col = (255, 255, 255)
        for x in self.line_screen_coords():
            dl(window, col, x[:2], x[2:])

    def line_screen_coords(self):
        '''Using self.view and self.ws, transforms self.lines to in-window
        coords.'''

        ((xl, yl), (xh, yh)) = self.view

        xsf = self.ws[0] / float(xh - xl)
        ysf = self.ws[1] / float(yh - yl)

        return (self.lines - [xl, yl, xl, yl]) * [xsf, ysf, xsf, ysf]

    def handle_select(self, ul, lr):
        print ul, lr
