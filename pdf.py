import PyPDF2

from PyPDF2.pdf import ContentStream
from PyPDF2.generic import *

import numpy

class NovelContentStream(ContentStream):
    def __init__(self, pdf):
        self.pdf = pdf
        self.operations = []

class SchematicReader(PyPDF2.PdfFileReader):
    def get_line_ops(self, page_no):
        '''Return a list of line drawing operations on the given page.'''

        contents = self.get_page_content(page_no)

        ctm = self.get_initial_ctm(page_no)

        line_ops = []

        for op in contents.operations:
            if op[1] in 'ml':
                coords = ctm.dot(map(float, op[0]) + [1])
                line_ops.append(((coords[0], coords[1]), op[1]))

        return line_ops

    def get_page_content(self, page_no):
        '''Load the content stream of a page.'''
        page = self.getPage(page_no)
        return ContentStream(page.getContents(), page.pdf)

    def get_initial_ctm(self, page_no):
        '''Initialise the current transformation matrix (CTM) by looking at
        the Rotate setting in the page dictionary. This doesn't handle CTM
        changes due to `cm` operations in the content stream.'''

        page = self.getPage(page_no)
        rotation = page.get('/Rotate', 0)
        [xl, yl, xh, yh] = page.get('/CropBox', page['/MediaBox'])

        if xl != 0 or yl != 0:
            raise NotImplementedError('Page corner is not at (0, 0)')

        if rotation == 0:
            return numpy.array([[ 1,  0, 0],
                                [ 0,  1, 0],
                                [ 0,  0, 1]])
        elif rotation == 90:
            return numpy.array([[ 0,  1,  0],
                                [-1,  0, xh],
                                [ 0,  0,  1]])
        elif rotation == 180:
            return numpy.array([[-1,  0, xh],
                                [ 0, -1, yh],
                                [ 0,  0,  1]])
        elif rotation == 270:
            return numpy.array([[ 0, -1, yh],
                                [ 1,  0,  0],
                                [ 0,  0,  1]])
        else:
            raise NotImplementedError('unhandled rotation: %r' % rotation)

    def add_text(self, page_no, text_items):
        '''Adds text, given as a {string: coords} to the given page.'''

        page = self.getPage(page_no)

        newContentsArray = ArrayObject()
        newContentsArray.append(ContentStream(page.getContents(), page.pdf))

        addedContents = NovelContentStream(page.pdf)
        addedContents.operations = list(text_to_operations(text_items))
        newContentsArray.append(addedContents)

        newContents = ContentStream(newContentsArray, page.pdf).flateEncode()

        page[NameObject('/Contents')] = newContents

def text_to_operations(*args, **kwargs):
    return objectify_ops(text_to_raw_ops(*args, **kwargs))

def text_to_raw_ops(text_items, font='/TT2'):
    yield ([], 'BT')

    # this font size here seems to have no effect, and you
    # have to change the scale factor in the text matrix
    yield ([font, 1], 'Tf')

    # switch to red text
    yield (['/DeviceRGB'], 'CS')
    yield ([255, 0, 0], 'sc')

    for text, (x, y), scale in text_items:
        # 5 was chosen by trial and error to approximately match
        # size of chars in development doc
        yield ([0, 5*scale, -5*scale, 0, y, x], 'Tm')
        yield ([text], 'Tj')

    yield ([], 'ET')

def objectify_ops(ops):
    def objectify(x):
        if isinstance(x, str):
            return TextStringObject(x)
        elif isinstance(x, int):
            return NumberObject(x)
        elif isinstance(x, float):
            return FloatObject('%.2f' % x)
        else:
            raise NotImplementedError('unrecognised object: %r' % x)

    for operands, operation in ops:
        yield ((objectify(operand) for operand in operands), objectify(operation))

def line_ops_to_lines(ops):
    lines = []

    for next_pos, c in ops:
        if c == 'm':
            pass

        elif c == 'l':
            lines.append(pos + next_pos)

        pos = next_pos

    return lines
