import pypdf
r = pypdf.PdfReader('BixBench.pdf')
if r.is_encrypted:
    r.decrypt('')
with open('BixBench_fulltext.txt', 'w', encoding='utf-8') as f:
    for i, p in enumerate(r.pages):
        f.write(f'\n===== PAGE {i+1} =====\n')
        f.write(p.extract_text() or '')
print('pages:', len(r.pages))
