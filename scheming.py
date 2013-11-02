import PyPDF2

import pygame
from pygame.locals import *

import time

import json

import random

def parse_pdf (pdf_doc):
    """Open the pdf document, and apply the function, returning the results"""
    reader = PyPDF2.PdfFileReader(open(pdf_doc, 'rb'))

    return parse_pages(reader)

class Path(object):
    pass

def parse_pages(doc):
    """With an open PDFDocument object, get the pages and parse each one
    [this is a higher-order function to be passed to parse_pdf()]"""

    page = doc.getPage(1)
    contents = PyPDF2.pdf.ContentStream(page.getContents(), page.pdf)

    return list(get_paths(contents.operations))

def get_paths(ops):
    for op in ops:
        if op[1] in 'mlh':
            yield (map(float, (op[0][1], op[0][0])), op[1])
        elif op[1] == 'c':
            yield (map(float, (op[0][5], op[0][4])), op[1])

def gencol():
    return tuple(random.randint(0, 255) for _ in range(3))

def show_paths(window, paths, map_pt):
    for step in paths:
        c = step[-1]
        if c == 'm':
            pos = (step[0][0], step[0][1])
            start = pos
            col = gencol()

        elif c in 'lc':
            pos2 = (step[0][0], step[0][1])

            pygame.draw.line(window, col,
                    map_pt(pos), map_pt(pos2))
            pos = pos2

        elif c == 'h':
            print 'hhhh'
            pygame.draw.line(window, (255, 255, 255),
                    map_pt(pos), map_pt(start))
            pos = start

def with_window(fn, *args):
    window = pygame.display.set_mode((800, 600))#, pygame.FULLSCREEN)
    pygame.key.set_repeat(300, 50)

    try:
        fn(window, *args)

    finally:
        pygame.display.quit()

def to_doc(pix_pos, ws, view):
    ((xl, yl), (xh, yh)) = view

    # map pos to doc
    x, y = pix_pos
    xd = xl + x / float(ws[0]) * (xh - xl)
    yd = yl + y / float(ws[1]) * (yh - yl)

    return (xd, yd)

def from_doc(doc_pos, ws, view):
    x, y = doc_pos
    ((xl, yl), (xh, yh)) = view

    return (ws[0] * (x - xl) / float(xh - xl),
            ws[1] * (y - yl) / float(yh - yl))

def extract_path(paths, ul, lr):
    (ulx, uly) = ul
    (lrx, lry) = lr
    started = stopped = False
    for (x, y), c in paths:
        if ulx <= x <= lrx and uly <= y <= lry:
            if stopped:
                yield 'gap'
                stopped = False

            started = True

            yield ((x, y), c)
        elif started:
            stopped = True

def diff_path(path):
    assert path[0][1] == 'm'
    px, py = path[0][0]

    for (x, y), c in path[1:]:
        yield (x-px, y-py), c
        px, py = x, y

def save_path(path):
    pathdict = json.load(open('scheming.json', 'r'))
    c = raw_input('enter char: ')
    if c in pathdict:
        print cmp_path(list(path), pathdict[c])
    else:
        path = list(path)
        pathdict[c] = {
                'origin': path_origin(path),
                'path': path,
                }
        json.dump(pathdict, open('scheming.json', 'w'))

def cmp_path(path1, path2):
    if len(path1) != len(path2):
        print 'different lengths ({}, {}). trying prefix'.format(len(path1), len(path2))

    ans = []
    from math import sqrt
    for ((x1, y1), c1), ((x2, y2), c2) in zip(path1, path2):
        s = '{:.2g}'.format(max(abs(x1-x2), abs(y1-y2)))
        if c1 != c2:
            s = s+'*'
        ans.append(s)

    return ', '.join(ans)

def path_origin(path):
    px, py = 0, 0
    ox, oy = 0, 0

    for (dx, dy), c in path:
        px += dx
        py += dy

        ox = min(px, ox)
        oy = min(py, oy)

    return (ox, oy)

def zoomview(window, paths):

    ws = window.get_size()

    ys = [s[0][1] for s in paths if s[-1] in 'ml']
    xs = [s[0][0] for s in paths if s[-1] in 'ml']

    last_view = (0, 0, 0, 0)
    view = ((min(xs), min(ys)), (max(xs), max(ys)))

    def view_pt(pt):
        return from_doc(pt, ws, view)

    moving = False
    selecting = False
    last_selecting = False

    while True:
        if view != last_view or selecting or last_selecting:
            random.seed(0)
            window.fill((0, 0, 0))
            show_paths(window, paths, view_pt)

            if selecting:
                x, y = og_pos
                mx, my = pygame.mouse.get_pos()
                pygame.draw.rect(window, (255, 255, 255),
                        (x, y, mx-x, my-y), 1)

            pygame.display.flip()

        last_view = view
        last_selecting = selecting

        ev = pygame.event.wait()
        if ev.type == MOUSEBUTTONDOWN:
            if ev.button == 4 or ev.button == 5:
                zf = 0.8
                if ev.button == 5:
                    zf = 1/zf

                ((xl, yl), (xh, yh)) = view

                # map pos to doc
                (xd, yd) = to_doc(ev.pos, ws, view)

                # recentre view on pos, and adjust
                xl, yl, xh, yh = xl-xd, yl-yd, xh-xd, yh-yd
                xl, yl, xh, yh = zf*xl, zf*yl, zf*xh, zf*yh

                # set new view
                view = ((xl+xd, yl+yd), (xh+xd, yh+yd))

            elif ev.button == 1:
                og_view = view
                og_pos = ev.pos
                moving = True
            elif ev.button == 3:
                og_pos = ev.pos
                selecting = True
        elif ev.type == MOUSEMOTION:
            if moving:
                dx, dy = ev.pos[0] - og_pos[0], ev.pos[1] - og_pos[1]

                ((xl, yl), (xh, yh)) = og_view
                dvx, dvy = dx / float(ws[0]) * (xh-xl), dy / float(ws[1]) * (yh-yl)

                view = ((xl-dvx, yl-dvy), (xh-dvx, yh-dvy))

        elif ev.type == MOUSEBUTTONUP:
            if ev.button == 1:
                moving = False
            elif ev.button == 3:
                ((xl, yl), (xh, yh)) = view

                pta = to_doc(og_pos, ws, view)
                ptb = to_doc(ev.pos, ws, view)

                ul = (min(pta[0], ptb[0]), min(pta[1], ptb[1]))
                lr = (max(pta[0], ptb[0]), max(pta[1], ptb[1]))

                path = list(extract_path(paths, ul, lr))
                if 'gap' in path:
                    print 'gap in path'
                    continue

                save_path(diff_path(path))

                selecting = False
        elif ev.type == KEYDOWN:
            if ev.key == K_RETURN:
                print view
                return

def match_paths(pathdict, paths, tol=0.1):
    paths = diff_path(paths)

    options = []

    def match_step(step1, step2):
        ((x1, y1), c1) = step1
        ((x2, y2), c2) = step2

        return c1 == c2 and abs(x1-x2) < tol and abs(y1-y2) < tol

    for (i, step) in enumerate(paths):
        # evaluate current options
        options = [(char, pos+1) for (char, pos) in options
                if match_step(step, pathdict[char]['path'][pos])]

        # try starting a new option
        for char, path in pathdict.iteritems():
            if match_step(step, path['path'][0]):
                options.append((char, 1))

        new_options = []
        for char, pos in options:
            if pos == len(pathdict[char]['path']):
                print 'match {} at {} ({})'.format(char, i-pos, pos)
            else:
                new_options.append((char, pos))
        options = new_options
