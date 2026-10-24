"""Layout-check build: LibreOffice here lacks the Math module, so OMML is replaced by mathtext images."""
import hashlib, os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
plt.rcParams.update({"mathtext.fontset": "stix"})
import build_paper as B
os.makedirs("prevmath", exist_ok=True)

def clean(l):
    import re
    l = re.sub(r"\\le(?![a-z])", r"\\leq", l)
    return l.replace(r"\Big(", "(").replace(r"\Big)", ")").replace(r"\big(", "(").replace(r"\big)", ")").replace(r"\qquad", r"\quad\quad")

def fn(latex, size):
    key = hashlib.md5((latex + str(size)).encode()).hexdigest()[:12]
    path = f"prevmath/{key}.png"
    fig = plt.figure(); fig.text(0, 0, "$" + clean(latex) + "$", fontsize=size)
    fig.savefig(path, dpi=600, bbox_inches="tight", pad_inches=0.005, transparent=True); plt.close(fig)
    return path, Image.open(path).size[1] / 600 * 72

B.PREVIEW["fn"] = fn
B.build("prev/preview.docx")
