import PyPDF2
import pdf, scheming, sigil
from collections import Counter

def annotate(input_filename, output_filename):
    rdr = pdf.SchematicReader(open(input_filename, 'rb'))
    sigdict = sigil.SigilDict.from_json(open('scheming.json'))

    font_name = rdr.add_dummy_font()

    for page_no in [0,1]:#range(len(rdr.pages)):

        line_ops = rdr.get_line_ops(page_no)

        matches = scheming.match_sigils(sigdict, line_ops)

        rdr.add_text(page_no, font_name,
                [(s.char, pos, scale) for (s, pos, scale) in matches])

    wtr = PyPDF2.PdfFileWriter()
    for p in rdr.pages:
        wtr.addPage(p)

    wtr.write(open(output_filename, 'wb'))

if __name__ == '__main__':
    annotate('P1318-005a.pdf', 'modified.pdf')
