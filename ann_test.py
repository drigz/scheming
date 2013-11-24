import PyPDF2
import pdf

rdr = pdf.SchematicReader(open('P1318-005a.pdf', 'rb'))

rdr.add_text(1, {
'freemon': (500.0, 500.0),
'g': (500.0, 480.0),
'o': (500.6, 480.0),
'r': (501.1, 480.0),
'd': (501.4, 480.0),
'a': (502.0, 480.0),
'n': (502.6, 480.0),
})

wtr = PyPDF2.PdfFileWriter()
for p in rdr.pages:
    wtr.addPage(p)

wtr.write(open('modified.pdf', 'wb'))
