from pdfminer.pdfdevice import PDFDevice
from pdfminer.pdfparser import PDFParser, PDFDocument, PDFNoOutlines
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter

import pygame
from pygame.locals import *

import time

import random

def parse_pdf (pdf_doc):
    """Open the pdf document, and apply the function, returning the results"""
    # open the pdf file
    fp = open(pdf_doc, 'rb')
    # create a parser object associated with the file object
    parser = PDFParser(fp)
    # create a PDFDocument object that stores the document structure
    doc = PDFDocument()
    # connect the parser and document objects
    parser.set_document(doc)
    doc.set_parser(parser)
    # supply the password for initialization
    doc.initialize()

    assert doc.is_extractable

    return parse_pages(doc)

class Path(object):
    pass

class SchemingDevice(PDFDevice):
    def __init__(self, rsrcmgr):
        PDFDevice.__init__(self, rsrcmgr)

        self.paths = []

    def paint_path(self, gs, stroke, fill, evenodd, path):
        p = Path()
        p.typestr = '{:d}{:d}{:d}'.format(stroke, fill, evenodd)
        p.shapestr = ''.join(x[0] for x in path)
        p.path = path
        self.paths.append(p)

def parse_pages(doc):
    """With an open PDFDocument object, get the pages and parse each one
    [this is a higher-order function to be passed to parse_pdf()]"""
    rsrcmgr = PDFResourceManager()
    device = SchemingDevice(rsrcmgr)
    interpreter = PDFPageInterpreter(rsrcmgr, device)

    page = list(doc.get_pages())[1]
    interpreter.process_page(page)

    return device.paths

def gencol():
    return tuple(random.randint(0, 255) for _ in range(3))

def show_path(window, path, map_pt):
    assert path.path[0][0] == 'm'

    if any(s[0] == 'c' for s in path.path):
        return

    for step in path.path[0:]:
        c = step[0]
        if c == 'm':
            pos = (step[1], step[2])
            start = pos
            col = gencol()

        elif c in 'lc':
            if c == 'l':
                pos2 = (step[1], step[2])
            elif c == 'c':
                pos2 = (step[5], step[6])

            pygame.draw.line(window, col,
                    map_pt(pos), map_pt(pos2))
            pos = pos2

        elif c == 'h':
            pygame.draw.line(window, (255, 255, 255),
                    map_pt(pos), map_pt(start))
            pos = start

        else:
            raise 'unhandled ins: {}'.format(c)

def with_window(fn, *args):
    window = pygame.display.set_mode((800, 600))#, pygame.FULLSCREEN)
    pygame.key.set_repeat(300, 50)

    try:
        fn(window, *args)

    finally:
        pygame.display.quit()

def key_path(window, paths, ix=0):

    def map_pt(pt):
        x,y = pt
        return y*(1440/1190.0), x*(900/860.0)

    window.fill((0, 0, 0))
    show_path(window, paths[ix], map_pt)
    pygame.display.flip()

    while True:
        ev = pygame.event.wait()
        if ev.type == KEYDOWN:
            if ev.key == K_LEFT:
                ix = (ix + len(paths) - 1) % len(paths)
            elif ev.key == K_RIGHT:
                ix = (ix + len(paths) + 1) % len(paths)
            elif ev.key == K_a:
                window.fill((0, 0, 0))
                for p in paths:
                    show_path(window, p, map_pt)
                pygame.display.flip()
                continue
            elif ev.key == K_RETURN:
                print ix
                break
            else:
                continue

            window.fill((0, 0, 0))
            show_path(window, paths[ix], map_pt)
            pygame.display.flip()

def zoomview(window, paths):

    ws = window.get_size()

    ys = [s[1] for p in paths for s in p.path if len(s) > 1]
    xs = [s[2] for p in paths for s in p.path if len(s) > 1]

    last_view = (0, 0, 0, 0)
    view = ((min(xs), min(ys)), (max(xs), max(ys)))

    def view_pt(pt):
        y, x = pt

        ((xl, yl), (xh, yh)) = view

        return (ws[0] * (x - xl) / float(xh - xl),
                ws[1] * (y - yl) / float(yh - yl))

    moving = False

    while True:
        if view != last_view:
            random.seed(0)
            window.fill((0, 0, 0))
            for p in paths:
                show_path(window, p, view_pt)
            pygame.display.flip()

        last_view = view

        ev = pygame.event.wait()
        if ev.type == MOUSEBUTTONDOWN:
            if ev.button == 4 or ev.button == 5:
                zf = 1.05 if ev.button == 5 else 0.95

                ((xl, yl), (xh, yh)) = view

                # map pos to doc
                x, y = ev.pos
                xd = xl + x / float(ws[0]) * (xh - xl)
                yd = yl + y / float(ws[1]) * (yh - yl)

                # recentre view on pos, and adjust
                xl, yl, xh, yh = xl-xd, yl-yd, xh-xd, yh-yd
                xl, yl, xh, yh = zf*xl, zf*yl, zf*xh, zf*yh

                # set new view
                view = ((xl+xd, yl+yd), (xh+xd, yh+yd))

            elif ev.button == 1:
                og_view = view
                og_pos = ev.pos
                moving = True
        elif ev.type == MOUSEMOTION:
            if moving:
                dx, dy = ev.pos[0] - og_pos[0], ev.pos[1] - og_pos[1]

                ((xl, yl), (xh, yh)) = og_view
                dvx, dvy = dx / float(ws[0]) * (xh-xl), dy / float(ws[1]) * (yh-yl)

                view = ((xl-dvx, yl-dvy), (xh-dvx, yh-dvy))
        elif ev.type == MOUSEBUTTONUP:
            if ev.button == 1:
                moving = False
        elif ev.type == KEYDOWN:
            if ev.key == K_RETURN:
                print view
                return
