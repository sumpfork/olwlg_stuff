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
    parser.add_argument("--print-namelists", action="store_true")

    args = parser.parse_args()
    url = f"http://bgg.activityclub.org/olwlg/{args.tradeid}-results-official.txt"
    print(f"trade results url: {url}")
    resp = requests.get(
        url,
        verify=False,
    )
    if resp.status_code != http.client.OK:
        print(
            f"could not access official results for {args.tradeid}: {resp.status_code}"
        )
        sys.exit(1)
    results = resp.text

    cache_fname = "bgg_trade_cache_{}.json".format(args.tradeid)
    try:
        with open(cache_fname) as f:
            cache = json.load(f)
    except FileNotFoundError:
        cache = {}
    traders = set()
    preamble = []
    for line in results.split("\n"):
        m = re.match(r"\((.*?)\).*receives \((.*?)\).*", line)
        if m:
            traders.add(m.group(1))
            traders.add(m.group(2))
        else:
            m = re.match(r"#\+ (.*)", line)
            if m:
                preamble.append(m.group(1))
    if args.random_traders > 0:
        print(
            f"randomly selected traders: {random.sample(traders, args.random_traders)}"
        )
    if args.no_labels:
        sys.exit(0)
    traders = sorted(traders)
    for t in traders:
        if t not in cache:
            u = bgg.user(t)
            if u:
                print((t, u.firstname, u.lastname))
                n = "{} {}".format(u.firstname, u.lastname)
                cache[t] = n
            else:
                print(f"Warning: user {t} not found on BGG")
            with open(cache_fname, "w") as f:
                json.dump(cache, f)
    traders = [(t, cache[t]) for t in traders]
    print(f"{len(traders)} Traders found")

    cutoffs = (len(traders) // 3, len(traders) * 2 // 3, len(traders))
    print(f"cuttoffs: {cutoffs}")
    for i in (0, 1):
        while traders[cutoffs[i]][0][0] == traders[cutoffs[i] - 1][0][0]:
            print(f"{traders[cutoffs[i]]}, {traders[cutoffs[i] - 1]}")
            cutoffs = (
                cutoffs[0] + (1 if i == 0 else 0),
                cutoffs[1] + (1 if i == 1 else 0),
                cutoffs[2],
            )
    print(f"adjusted cuttoffs: {cutoffs}")

    # print("\n".join([str(t) for t in traders]))
    c = canvas.Canvas("traders_{}.pdf".format(args.tradeid), pagesize=LETTER)

    if args.print_namelists:
        # first print some name lists
        i = 0
        for ci, cutoff in enumerate(cutoffs):
            c.saveState()
            c.translate(LETTER[0] / 2, LETTER[1] - 50)
            c.setFont("Helvetica", 25)
            c.drawCentredString(0, 0, f"{traders[i][0][0]}-{traders[cutoff - 1][0][0]}")
            c.translate(0, -40)
            while i < cutoff:
                c.translate(0, -18)
                c.rect(-130, 0, 10, 10, fill=0)
                c.setFont("Helvetica", 12)
                c.drawString(
                    -100,
                    0,
                    " ".join(traders[i]),
                )
                i += 1
            c.showPage()

    LABELS_PER_PAGE = 10
    LABELS_PER_ROW = 2
    top_margin = 0.5 * inch  # inch
    left_margin = 0.18 * inch  # 0.28125 / 2 * inch
    label_width = 4 * inch  # 2.625 * inch
    label_height = 2 * inch  # 1 * inch
    i = 0
    for cutoff in cutoffs:
        c.saveState()
        c.translate(LETTER[0] / 2, LETTER[1] / 2)
        c.setFont("Helvetica", 12)
        y = 200
        for n, line in enumerate(preamble):
            c.drawCentredString(0, y - n * 20, line)
        c.drawCentredString(
            0, y - (n + 3) * 20, "Traders with usernames starting with letters:"
        )
        c.drawCentredString(0, y - n * 20, line)
        c.setFont("Helvetica", 45)
        c.drawCentredString(0, 0, f"{traders[i][0][0]}-{traders[cutoff - 1][0][0]}")
        c.restoreState()
        c.showPage()

        for page_labels in iter_batches(traders[i:cutoff], LABELS_PER_PAGE):
            c.line(LETTER[0] / 2, LETTER[1] - top_margin, LETTER[0] / 2, top_margin)
            page_labels = list(page_labels)
            c.setFont("Helvetica", 20)
            c.drawCentredString(
                LETTER[0] / 2 - 50,
                10,
                f"{page_labels[0][0][0]}-{page_labels[-1][0][0]}",
            )
            c.drawCentredString(
                LETTER[0] / 2 - 50,
                LETTER[1] - 25,
                f"{page_labels[0][0][0]}-{page_labels[-1][0][0]}",
            )
            c.translate(0, LETTER[1] - top_margin - label_height / 2)
            for labels in iter_batches(page_labels, LABELS_PER_ROW):
                c.saveState()
                c.translate(left_margin, 0)
                for ri, (uname, name) in enumerate(labels):
                    c.setFont("Helvetica", 25)
                    c.drawCentredString((label_width / 2), label_height / 5, uname[:16])
                    c.setFont("Helvetica", 20)
                    c.drawCentredString((label_width / 2), -label_height / 5, name[:25])

                    c.setFont("Helvetica", 6)
                    c.saveState()
                    on_left = ri % LABELS_PER_ROW == 0
                    c.rotate(90 if on_left else -90)

                    c.drawCentredString(
                        0,  # 25 if on_left else -25,
                        -label_width -4 if on_left else -7,
                        uname,
                    )
                    c.restoreState()
                    c.translate(label_width + left_margin, 0)
                    i += 1
                c.restoreState()
                c.translate(0, -label_height)
            c.showPage()
    c.save()
