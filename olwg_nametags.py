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


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('tradeid', type=int)
    args = parser.parse_args()
    resp = requests.get('http://bgg.activityclub.org/olwlg/{}-results-official.txt'.format(args.tradeid))
    if resp.status_code != httplib.OK:
        print('could not access official results for {}'.format(args.tradeid))
        sys.exit(1)
    results = resp.text

    try:
        cache = json.load(open('bgg_trade_cache.json'))
    except:
        cache = {}
    traders = set()
    for line in results.split('\n'):
        m = re.match(r'\((.*?)\).*receives \((.*?)\).*', line)
        if m:
            traders.add(m.group(1))
            traders.add(m.group(2))
    traders = sorted(traders)
    for t in traders:
        if t not in cache:
            u = bgg.user(t)
            print(t, u.firstname, u.lastname)
            n = u'{} {}'.format(u.firstname, u.lastname)
            cache[t] = n
            json.dump(cache, open('bgg_trade_cache.json', 'w'))
    traders = [(t, cache[t]) for t in traders]
    print('\n'.join([str(t) for t in traders]))
    c = canvas.Canvas('traders_{}.pdf'.format(args.tradeid),
                      pagesize=LETTER)
    LABELS_PER_PAGE = 30
    LABELS_PER_ROW = 3

    for page_labels in iter_batches(traders, LABELS_PER_PAGE):
        c.translate(0, LETTER[1] - inch)
        for labels in iter_batches(page_labels, LABELS_PER_ROW):
            c.saveState()
            for uname, name in labels:
                c.translate(0.28125 / 2 * inch, 0)
                c.setFont('Helvetica', 18)
                c.drawCentredString((2.625 / 2) * inch, 0.15 * inch, uname)
                c.setFont('Helvetica', 15)
                c.drawCentredString((2.625 / 2) * inch, -0.15 * inch, name[:25])
                c.translate(2.625 * inch, 0)
            c.restoreState()
            c.translate(0, -inch)
        c.showPage()
    c.save()
