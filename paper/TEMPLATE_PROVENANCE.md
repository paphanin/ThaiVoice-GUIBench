# IEEE template provenance

The paper uses IEEEtran in conference mode on US Letter with the class defaults.
Official template page: https://www.ieee.org/conferences/publishing/templates.html
IEEE Author Center: https://conferences.ieeeauthorcenter.ieee.org/write-your-paper/authoring-tools-and-templates/

The official IEEE template ZIP returned a non-ZIP response in this environment. The unmodified IEEEtran class and bibliography style were obtained from the CTAN IEEEtran distribution linked by IEEE template instructions.

- Distribution: https://mirrors.ctan.org/macros/latex/contrib/IEEEtran.zip
- Resolved mirror: https://mirror.kku.ac.th/CTAN/macros/latex/contrib/IEEEtran.zip
- Archive SHA-256: e0cd4f5afbd42c8076092280e72b3e0a5111efe501d35de9f715cfb8da313cb4
- Class: IEEEtran.cls v1.8b (2015/08/26), license notice preserved in file.
- Bibliography: IEEEtran.bst, license notice preserved in file.
- Retrieved: 2026-10-19.

Build from paper/: pdflatex -interaction=nonstopmode -halt-on-error main.tex; bibtex main; pdflatex -interaction=nonstopmode -halt-on-error main.tex (twice).
No class margin, body-font, bibliography-font, or global float-spacing overrides are used.

The unmodified `cite.sty` support package is included from https://mirrors.ctan.org/macros/latex/contrib/cite.zip because it was absent locally. SHA-256: 56979b7c69ae65bdb52de5bcd540625cae6dd70119e767db438a4826991910ea. Its license notice is preserved.

Unmodified Times/Courier NFSS font definitions, TFM metrics and virtual fonts from the nested `lw35nfss.zip` in https://mirrors.ctan.org/macros/latex/required/psnfss.zip are included beside the source. These supply missing standard IEEEtran font dependencies; they do not change the template font choice. PSNFSS notices are in `PSNFSS_README.txt`; Type 1 URW font programs and normal TeX font maps are supplied by the TeX distribution.
