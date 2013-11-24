import PyPDF2

from PyPDF2.pdf import ContentStream
from PyPDF2.generic import *

class NovelContentStream(ContentStream):
    def __init__(self, pdf):
        self.pdf = pdf
        self.operations = []

class SchematicReader(PyPDF2.PdfFileReader):
    def get_line_ops(self, page_no):
        '''Return a list of line drawing operations on the given page.'''

        page = self.getPage(page_no)
        contents = ContentStream(page.getContents(), page.pdf)

        return list(filter_line_ops(contents.operations))

    def add_text(self, page_no, text_items):
        '''Adds text, given as a {string: coords} to the given page.'''

        page = self.getPage(page_no)

        newContentsArray = ArrayObject()
        newContentsArray.append(ContentStream(page.getContents(), page.pdf))

        addedContents = NovelContentStream(page.pdf)
        addedContents.operations = list(text_to_operations(text_items))
        newContentsArray.append(addedContents)

        newContents = ContentStream(newContentsArray, page.pdf)

        page[NameObject('/Contents')] = newContents

def text_to_operations(*args, **kwargs):
    return objectify_ops(text_to_raw_ops(*args, **kwargs))

def text_to_raw_ops(text_items, font='/TT2'):
    yield ([], 'BT')
    yield ([font, 5], 'Tf')

    for text, (x, y) in text_items.items():
        yield ([1, 0, 0, 1, y, x], 'Tm')
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

def filter_line_ops(ops):
    '''Filters out the line drawing instructions used by schematics.

    Currently also converts Decimal -> float and swaps x & y coords.'''
    # TODO: use the ctm matrix, or return the raw coordinates
    for op in ops:
        if op[1] in 'ml':
            yield (map(float, (op[0][1], op[0][0])), op[1])

def line_ops_to_lines(ops):
    lines = []

    for next_pos, c in ops:
        if c == 'm':
            pass

        elif c == 'l':
            lines.append(pos + next_pos)

        pos = next_pos

    return lines
