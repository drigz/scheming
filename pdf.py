import PyPDF2

def load_line_ops(pdf_path):
    '''Load a schematic pdf with PdfFileReader, and return a list of line
    drawing operations.'''

    doc = PyPDF2.PdfFileReader(open(pdf_path, 'rb'))

    page = doc.getPage(1)
    contents = PyPDF2.pdf.ContentStream(page.getContents(), page.pdf)

    return list(get_line_ops(contents.operations))

def get_line_ops(ops):
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
