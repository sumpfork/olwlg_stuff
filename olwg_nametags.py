import argparse
import httplib
import sys
import re
import itertools
import json

import requests
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import LETTER

from boardgamegeek import BoardGameGeek

bgg = BoardGameGeek()


def iter_batches(iterable, size):
    sourceiter = iter(iterable)
    while True:
        batchiter = itertools.islice(sourceiter, size)
        yield itertools.chain([batchiter.next()], batchiter)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("tradeid", type=int)
    args = parser.parse_args()
    resp = requests.get(
        "http://bgg.activityclub.org/olwlg/{}-results-official.txt".format(args.tradeid)
    )
    if resp.status_code != httplib.OK:
        print("could not access official results for {}".format(args.tradeid))
        sys.exit(1)
    results = resp.text

    cache_fname = "bgg_trade_cache_{}.json".format(args.tradeid)
    try:
        with open(cache_fname) as f:
            cache = json.load(f)
    except:
        cache = {}
    traders = set()
    for line in results.split("\n"):
        m = re.match(r"\((.*?)\).*receives \((.*?)\).*", line)
        if m:
            traders.add(m.group(1))
            traders.add(m.group(2))
    traders = sorted(traders)
    for t in traders:
        if t not in cache:
            u = bgg.user(t)
            if not u:
                cache[t] = u"NOT FOUND"
            else:
                print(t, u.firstname, u.lastname)
                n = u"{} {}".format(u.firstname, u.lastname)
                cache[t] = n
            with open(cache_fname, 'w') as f:
                json.dump(cache, f)
    traders = [(t, cache[t]) for t in traders]
    print("\n".join([str(t) for t in traders]))
    c = canvas.Canvas("traders_{}.pdf".format(args.tradeid), pagesize=LETTER)
    LABELS_PER_PAGE = 10
    LABELS_PER_ROW = 2
    top_margin = 0.5 * inch  # inch
    left_margin = 0.18 * inch  # 0.28125 / 2 * inch
    label_width = 4 * inch  # 2.625 * inch
    label_height = 2 * inch  # 1 * inch
    for page_labels in iter_batches(traders, LABELS_PER_PAGE):
        c.translate(0, LETTER[1] - top_margin - label_height / 2)
        for labels in iter_batches(page_labels, LABELS_PER_ROW):
            c.saveState()
            c.translate(left_margin, 0)
            for uname, name in labels:
                c.setFont("Helvetica", 25)
                c.drawCentredString((label_width / 2), label_height / 5, uname[:16])
                c.setFont("Helvetica", 20)
                c.drawCentredString((label_width / 2), -label_height / 5, name[:25])
                c.translate(label_width + left_margin, 0)
            c.restoreState()
            c.translate(0, -label_height)
        c.showPage()
    c.save()
