import PyPDF2

from PyPDF2.pdf import ContentStream
from PyPDF2.generic import *

import numpy
import json

class NovelContentStream(ContentStream):
    def __init__(self, pdf):
        self.pdf = pdf
        self.operations = []

class SchematicReader(PyPDF2.PdfFileReader):
    def __init__(self, *args, **kwargs):
        super(SchematicReader, self).__init__(*args, **kwargs)

        # TODO: figure out how to convert between CID indices in the font we copy from
        # font_donor.pdf and real characters.
        #
        # For now, I generated this lookup table, but this is such a tragic copout.
        self.font_map = json.load(open('font_map.json'))

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

    def get_initial_ctm(self, page):
        '''Initialise the current transformation matrix (CTM) by looking at
        the Rotate setting in the page dictionary. This doesn't handle CTM
        changes due to `cm` operations in the content stream.'''

        if isinstance(page, int):
            page = self.getPage(page)

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

    def add_dummy_font(self):
        '''Load a font from a dummy donor document and merge it into every page,
        returning the name of the new font.'''

        # load the donor font
        rdr = PyPDF2.PdfFileReader(open('font_donor.pdf', 'rb'))
        donor_page = rdr.getPage(0)
        donor_resources = donor_page['/Resources'].getObject()
        donor_fonts = donor_resources['/Font'].values()

        assert len(donor_fonts) == 1

        new_font_name = '/FINJ'
        new_font_data = donor_fonts[0]

        # add font dictionaries to every page of the target pdf and
        # collect all existing font names
        existing_font_names = set()
        for page in self.pages:
            resources = page['/Resources'].getObject()
            if '/Font' in resources:
                existing_font_names.update(resources['/Font'].keys())
            else:
                resources[NameObject('/Font')] = DictionaryObject()

        # generate a unique name for the new font
        while new_font_name in existing_font_names:
            new_font_name = new_font_name + 'R'

        # add the new font to every page
        for page in self.pages:
            page['/Resources'].getObject()['/Font'][NameObject(new_font_name)] = new_font_data

        return new_font_name

    def add_text(self, page_no, font, text_items):
        '''Adds text, given as a {string: coords} to the given page.'''

        page = self.getPage(page_no)

        newContentsArray = ArrayObject()
        newContentsArray.append(ContentStream(page.getContents(), page.pdf))

        addedContents = NovelContentStream(page.pdf)
        addedContents.operations = self.text_to_operations(page, font, text_items)
        newContentsArray.append(addedContents)

        newContents = ContentStream(newContentsArray, page.pdf).flateEncode()

        page[NameObject('/Contents')] = newContents

    def text_to_operations(self, *args, **kwargs):

        def to_pypdf2_object(x):
            '''Convert a Python object to a PyPDF2 object.'''
            if isinstance(x, PdfObject):
                return x
            elif isinstance(x, str):
                return TextStringObject(x)
            elif isinstance(x, int):
                return NumberObject(x)
            elif isinstance(x, float):
                return FloatObject('%.2f' % x)
            else:
                raise NotImplementedError('unrecognised object: %r' % x)

        def to_operation(operation):
            return (tuple(map(to_pypdf2_object, operation[0])),
                    to_pypdf2_object(operation[1]))

        return map(to_operation,
                self.text_to_unwrapped_operations(*args, **kwargs))

    def text_to_unwrapped_operations(self, page, font, text_items):
        yield ([], 'BT')

        # this font size here seems to have no effect, and you
        # have to change the scale factor in the text matrix
        yield ([NameObject(font), 1], 'Tf')

        # switch to red text
        yield (['/DeviceRGB'], 'CS')
        yield ([255, 0, 0], 'sc')

        itm = numpy.linalg.inv(self.get_initial_ctm(page))

        for text, (x, y), scale in text_items:
            # 5 was chosen by trial and error to approximately match
            # size of chars in development doc
            raw_vector_homogenous = itm.dot([x, y, 1])
            raw_vector = list(raw_vector_homogenous[:2])


            # TODO (maybe): don't hardcode orientation matrix
            yield ([0, 5*scale, -5*scale, 0] + raw_vector, 'Tm')
            yield ([ByteStringObject(self.font_map[text])], 'Tj')

        yield ([], 'ET')

def line_ops_to_lines(ops):
    lines = []

    for next_pos, c in ops:
        if c == 'm':
            pass

        elif c == 'l':
            lines.append(pos + next_pos)

        pos = next_pos

    return lines
