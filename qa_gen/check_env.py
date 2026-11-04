# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
for m in ["pypdf", "PyPDF2", "pdfminer", "fitz", "pdfplumber"]:
    try:
        mod = __import__(m)
        print(m, "OK", getattr(mod, "__version__", "?"))
    except Exception as e:
        print(m, "MISSING")
