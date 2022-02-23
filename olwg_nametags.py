import argparse
import http.client
import sys
import re
import itertools
import json
import random

import requests
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import LETTER

from boardgamegeek import BoardGameGeek

bgg = BoardGameGeek()


def iter_batches(iterable, size):
    sourceiter = iter(iterable)
    try:
        while True:
            batchiter = itertools.islice(sourceiter, size)
            yield itertools.chain([next(batchiter)], batchiter)
    except StopIteration:
        return


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("tradeid", type=int)
    parser.add_argument("--no-labels", action="store_true")
    parser.add_argument("--random-traders", type=int, default=0)
    args = parser.parse_args()
    url = f"http://bgg.activityclub.org/olwlg/{args.tradeid}-results-official.txt"
    print(f"trade results url: {url}")
    resp = requests.get(
        url,
        verify=False,
    )
    if resp.status_code != http.client.OK:
        print(f"could not access official results for {args.tradeid}: {resp.status_code}")
        sys.exit(1)
    results = resp.text

    cache_fname = "bgg_trade_cache_{}.json".format(args.tradeid)
    try:
        with open(cache_fname) as f:
            cache = json.load(f)
    except FileNotFoundError:
        cache = {}
    traders = set()
    for line in results.split("\n"):
        m = re.match(r"\((.*?)\).*receives \((.*?)\).*", line)
        if m:
            traders.add(m.group(1))
            traders.add(m.group(2))
    if args.random_traders > 0:
        print(f"randomly selected traders: {random.sample(traders, args.random_traders)}")
    if args.no_labels:
        sys.exit(0)
    traders = sorted(traders)
    for t in traders:
        if t not in cache:
            u = bgg.user(t)
            if not u:
                cache[t] = "NOT FOUND"
            else:
                print((t, u.firstname, u.lastname))
                n = "{} {}".format(u.firstname, u.lastname)
                cache[t] = n
            with open(cache_fname, "w") as f:
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
