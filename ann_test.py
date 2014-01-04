import PyPDF2
import pdf, scheming, sigil

if __name__ == '__main__':
    rdr = pdf.SchematicReader(open('P1318-005a.pdf', 'rb'))
    sigdict = sigil.SigilDict.from_json(open('scheming.json'))

    for page_no in [1]:
        line_ops = rdr.get_line_ops(page_no)

        matches = scheming.match_sigils(sigdict, line_ops)

        rdr.add_text(page_no, [(s.char, pos, scale) for (s, pos, scale) in matches])

    wtr = PyPDF2.PdfFileWriter()
    for p in rdr.pages:
        wtr.addPage(p)

    wtr.write(open('modified.pdf', 'wb'))
