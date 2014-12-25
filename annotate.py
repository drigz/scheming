import PyPDF2
import pdf, scheming, sigil
from collections import Counter

import argparse

def annotate(input_filename, output_filename, pages=None):
    rdr = pdf.SchematicReader(open(input_filename, 'rb'))
    sigdict = sigil.SigilDict.from_json(open('scheming.json'))

    font_name = rdr.add_dummy_font()

    if pages is None:
        pages = range(len(rdr.pages))

    for page_no in pages:

        line_ops = rdr.get_line_ops(page_no)

        matches = scheming.match_sigils(sigdict, line_ops)

        rdr.add_text(page_no, font_name,
                [(s, pos, scale) for (s, pos, scale) in matches])

    wtr = PyPDF2.PdfFileWriter()
    for p in rdr.pages:
        wtr.addPage(p)

    wtr.write(open(output_filename, 'wb'))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pages', '-p', nargs='?',
            help="comma-separated list of pages to process [default: all]")
    parser.add_argument('input', nargs='?', default='P1318-005a.pdf',
            help='path to input PDF  [default: P1318-005a.pdf]')
    parser.add_argument('output', nargs='?', default='modified.pdf',
            help='path to output PDF [default: modified.pdf]')
    args = parser.parse_args()

    if args.pages is not None:
        args.pages = map(int, args.pages.split(','))

    annotate(args.input, args.output, pages=args.pages)
