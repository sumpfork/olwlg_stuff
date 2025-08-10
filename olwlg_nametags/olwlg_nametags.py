"""
OLWLG Nametag Generator

Generates PDF nametags for board game trade participants from OLWLG trade results.
"""

import argparse
import http.client
import itertools
import json
import os
import random
import re
import sys
from typing import Iterator, List, Tuple, Dict, Any

import requests
from boardgamegeek import BoardGameGeek  # type: ignore
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# Configuration Constants
LABELS_PER_PAGE = 10
LABELS_PER_ROW = 2
TOP_MARGIN = 0.5 * inch
LEFT_MARGIN = 0.18 * inch
LABEL_WIDTH = 4 * inch
LABEL_HEIGHT = 2 * inch
MIDDLE_FUDGE = 0.04 * inch

# Font sizes
TITLE_FONT_SIZE = 45
HEADER_FONT_SIZE = 25
NAME_FONT_SIZE = 25
REAL_NAME_FONT_SIZE = 20
LIST_FONT_SIZE = 12
RANGE_FONT_SIZE = 20
SIDE_FONT_SIZE = 6

# Layout constants
USERNAME_MAX_LENGTH = 16
REAL_NAME_MAX_LENGTH = 25


class TradeResultsProcessor:
    """Handles fetching and parsing trade results from OLWLG."""

    def __init__(self, trade_id: int):
        self.trade_id = trade_id
        self.bgg = BoardGameGeek()
        self.cache_filename = f"bgg_trade_cache_{trade_id}.json"
        self.cache: Dict[str, str] = self._load_cache()

    def _load_cache(self) -> Dict[str, str]:
        """Load existing cache file or return empty dict."""
        try:
            with open(self.cache_filename) as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def _save_cache(self) -> None:
        """Save cache to file."""
        with open(self.cache_filename, "w") as f:
            print(f"Writing cache to {self.cache_filename}, {len(self.cache)} traders")
            json.dump(self.cache, f)

    def fetch_results(self) -> str:
        """Fetch trade results from OLWLG server."""
        url = f"http://bgg.activityclub.org/olwlg/{self.trade_id}-results-official.txt"
        print(f"Trade results URL: {url}")

        response = requests.get(url, verify=False)
        if response.status_code != http.client.OK:
            print(
                f"Could not access official results for {self.trade_id}: {response.status_code}"
            )
            sys.exit(1)

        return response.text

    def parse_results(self, results: str) -> Tuple[List[str], List[str]]:
        """Parse trade results to extract traders and preamble."""
        traders_set = set()
        preamble = []

        for line in results.split("\n"):
            # Match trader exchanges: (trader1) receives (trader2)
            match = re.match(r"\((.*?)\).*receives \((.*?)\).*", line)
            if match:
                traders_set.add(match.group(1))
                traders_set.add(match.group(2))
            else:
                # Match preamble lines: #+ text
                preamble_match = re.match(r"#\+ (.*)", line)
                if preamble_match:
                    preamble.append(preamble_match.group(1))

        return sorted(traders_set), preamble

    def get_trader_info(self, traders: List[str]) -> List[Tuple[str, str]]:
        """Get real names for traders from BGG, using cache when possible."""
        trader_info = []

        for trader in traders:
            if trader not in self.cache:
                user = self.bgg.user(trader)
                if user:
                    print(
                        f"Retrieved info for {trader}: {user.firstname} {user.lastname}"
                    )
                    real_name = f"{user.firstname} {user.lastname}"
                    self.cache[trader] = real_name
                else:
                    print(f"Warning: user {trader} not found on BGG")
                    self.cache[trader] = trader  # Fallback to username

                self._save_cache()

            trader_info.append((trader, self.cache[trader]))

        return trader_info


class NametagGenerator:
    """Generates PDF nametags for traders."""

    def __init__(self, trade_id: int):
        self.trade_id = trade_id
        self.filename = f"traders_{trade_id}.pdf"
        self.canvas = canvas.Canvas(self.filename, pagesize=LETTER)
        self.letter_range_font = self._register_letter_range_font()

    def _register_letter_range_font(self) -> str:
        """Register Menlo-Regular font for letter ranges, fallback to Helvetica."""
        # Common paths for Menlo-Regular.ttf on macOS
        font_paths = [
            "/System/Library/Fonts/Menlo.ttc",  # macOS system font (TTC format)
            "/Library/Fonts/Menlo-Regular.ttf",  # Alternative location
            "Menlo-Regular.ttf",  # Current directory
            "/System/Library/Fonts/Supplemental/Menlo-Regular.ttf",  # Another macOS location
        ]

        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    # Register the font with ReportLab
                    if font_path.endswith(".ttc"):
                        # Handle TTC (TrueType Collection) files
                        pdfmetrics.registerFont(
                            TTFont("Menlo-Regular", font_path, subfontIndex=0)
                        )
                    else:
                        pdfmetrics.registerFont(TTFont("Menlo-Regular", font_path))
                    print(
                        f"Successfully registered Menlo-Regular font from: {font_path}"
                    )
                    return "Menlo-Regular"
                except Exception as e:
                    print(f"Failed to register font from {font_path}: {e}")
                    continue

        print("Menlo-Regular font not found, falling back to Helvetica")
        return "Helvetica"

    def _calculate_cutoffs(
        self, traders: List[Tuple[str, str]], num_groups: int = 3
    ) -> List[int]:
        """Calculate cutoff points for dividing traders into specified number of groups."""
        total = len(traders)
        cutoffs = []

        # Calculate initial cutoff points
        for i in range(1, num_groups + 1):
            cutoffs.append(total * i // num_groups)

        # Set the last cutoff to total to ensure we include all traders
        cutoffs[-1] = total

        # Adjust cutoffs to align with first letter changes (except the last one)
        for i in range(num_groups - 1):  # Don't adjust the last cutoff
            while (
                cutoffs[i] < total
                and cutoffs[i] > 0
                and traders[cutoffs[i]][0][0] == traders[cutoffs[i] - 1][0][0]
            ):
                cutoffs[i] += 1

        return cutoffs

    def generate_name_lists(
        self, traders: List[Tuple[str, str]], cutoffs: List[int]
    ) -> None:
        """Generate checklist pages for each group of traders."""
        start_index = 0

        for cutoff in cutoffs:
            self.canvas.saveState()
            self.canvas.translate(LETTER[0] / 2, LETTER[1] - 50)

            # Group header
            self.canvas.setFont(self.letter_range_font, HEADER_FONT_SIZE)
            first_letter = traders[start_index][0][0]
            last_letter = traders[cutoff - 1][0][0]
            self.canvas.drawCentredString(0, 0, f"{first_letter}-{last_letter}")

            # Individual trader entries
            self.canvas.translate(0, -40)
            for i in range(start_index, cutoff):
                self.canvas.translate(0, -18)
                self.canvas.rect(-130, 0, 10, 10, fill=0)  # Checkbox
                self.canvas.setFont("Helvetica", LIST_FONT_SIZE)
                trader_name = " ".join(traders[i])
                self.canvas.drawString(-100, 0, trader_name)

            self.canvas.restoreState()
            self.canvas.showPage()
            start_index = cutoff

    def _draw_section_cover(
        self,
        traders: List[Tuple[str, str]],
        start_idx: int,
        end_idx: int,
        preamble: List[str],
    ) -> None:
        """Draw a cover page for a section of traders."""
        self.canvas.saveState()
        self.canvas.translate(LETTER[0] / 2, LETTER[1] / 2)

        # Draw preamble
        self.canvas.setFont("Helvetica", LIST_FONT_SIZE)
        y_position = 200
        for line_num, line in enumerate(preamble):
            self.canvas.drawCentredString(0, y_position - line_num * 20, line)

        # Section description
        final_y = y_position - (len(preamble) + 2) * 20
        self.canvas.drawCentredString(
            0, final_y, "Traders with usernames starting with letters:"
        )

        # Large letter range
        self.canvas.setFont(self.letter_range_font, TITLE_FONT_SIZE)
        first_letter = traders[start_idx][0][0]
        last_letter = traders[end_idx - 1][0][0]
        self.canvas.drawCentredString(0, 0, f"{first_letter}-{last_letter}")

        self.canvas.restoreState()
        self.canvas.showPage()

    def _draw_nametag(
        self, username: str, real_name: str, position_in_row: int
    ) -> None:
        """Draw a single nametag."""
        # Main name (username)
        self.canvas.setFont("Helvetica", NAME_FONT_SIZE)
        truncated_username = username[:USERNAME_MAX_LENGTH]
        self.canvas.drawCentredString(
            LABEL_WIDTH / 2, LABEL_HEIGHT / 5, truncated_username
        )

        # Real name
        self.canvas.setFont("Helvetica", REAL_NAME_FONT_SIZE)
        truncated_real_name = real_name[:REAL_NAME_MAX_LENGTH]
        self.canvas.drawCentredString(
            LABEL_WIDTH / 2, -LABEL_HEIGHT / 5, truncated_real_name
        )

        # Side text (rotated username)
        self.canvas.setFont("Helvetica", SIDE_FONT_SIZE)
        self.canvas.saveState()

        is_left_label = position_in_row % LABELS_PER_ROW == 0
        rotation = 90 if is_left_label else -90
        x_offset = -LABEL_WIDTH - 4 + MIDDLE_FUDGE if is_left_label else -7 - MIDDLE_FUDGE

        self.canvas.rotate(rotation)
        self.canvas.drawCentredString(0, x_offset, username)
        self.canvas.restoreState()

    def generate_section_covers(
        self, traders: List[Tuple[str, str]], preamble: List[str], num_groups: int = 3
    ) -> None:
        """Generate section cover pages for all groups."""
        cutoffs = self._calculate_cutoffs(traders, num_groups)
        print(f"Generating {num_groups} section cover pages")
        print(f"Cutoffs for {num_groups} groups: {cutoffs}")

        start_index = 0

        for cutoff in cutoffs:
            # Draw section cover page
            self._draw_section_cover(traders, start_index, cutoff, preamble)
            start_index = cutoff

    def generate_nametags(
        self, traders: List[Tuple[str, str]], num_groups: int = 3
    ) -> None:
        """Generate nametag pages for all traders."""
        cutoffs = self._calculate_cutoffs(traders, num_groups)
        print(f"Generating nametag pages for {num_groups} groups")
        print(f"Adjusted cutoffs at first letter changes: {cutoffs}")

        start_index = 0

        for cutoff in cutoffs:
            # Generate nametag pages for this section
            section_traders = traders[start_index:cutoff]

            for page_traders in iter_batches(section_traders, LABELS_PER_PAGE):
                page_traders = list(page_traders)

                middle = LETTER[0] / 2 - MIDDLE_FUDGE

                # Draw page divider line and range indicators
                self.canvas.line(
                    middle, LETTER[1] - TOP_MARGIN, middle, TOP_MARGIN
                )

                self.canvas.setFont(self.letter_range_font, RANGE_FONT_SIZE)
                first_letter = page_traders[0][0][0]
                last_letter = page_traders[-1][0][0]
                range_text = f"{first_letter}-{last_letter}"

                # Top and bottom range indicators
                self.canvas.drawCentredString(middle, 15, range_text)
                self.canvas.drawCentredString(middle, LETTER[1] - 25, range_text)

                # Position for first row of labels
                self.canvas.translate(0, LETTER[1] - TOP_MARGIN - LABEL_HEIGHT / 2)

                # Draw labels in rows
                for row_traders in iter_batches(page_traders, LABELS_PER_ROW):
                    self.canvas.saveState()
                    self.canvas.translate(LEFT_MARGIN, 0)

                    for position, (username, real_name) in enumerate(row_traders):
                        self._draw_nametag(username, real_name, position)
                        self.canvas.translate(LABEL_WIDTH + LEFT_MARGIN, 0)

                    self.canvas.restoreState()
                    self.canvas.translate(0, -LABEL_HEIGHT)

                self.canvas.showPage()

            start_index = cutoff

    def save(self) -> None:
        """Save the PDF file."""
        self.canvas.save()
        print(f"Saved nametags to {self.filename}")


def iter_batches(iterable: List[Any], size: int) -> Iterator[Any]:
    """Yield successive batches of specified size from iterable."""
    source_iter = iter(iterable)
    try:
        while True:
            batch_iter = itertools.islice(source_iter, size)
            yield itertools.chain([next(batch_iter)], batch_iter)
    except StopIteration:
        return


def main() -> None:
    """Main entry point for the nametag generator."""
    parser = argparse.ArgumentParser(
        description="Generate PDF nametags for OLWLG trade participants"
    )
    parser.add_argument("tradeid", type=int, help="Trade ID number")
    parser.add_argument(
        "--no-labels",
        action="store_true",
        help="Only process data, don't generate labels",
    )
    parser.add_argument(
        "--random-traders",
        type=int,
        default=0,
        help="Show N random traders for testing",
    )
    parser.add_argument(
        "--print-namelists",
        action="store_true",
        help="Include checklist pages in output",
    )
    parser.add_argument(
        "--groups",
        type=int,
        default=3,
        help="Number of groups to divide traders into (default: 3)",
    )

    args = parser.parse_args()

    # Validate groups argument
    if args.groups < 1:
        print("Error: Number of groups must be at least 1")
        sys.exit(1)

    # Initialize processors
    results_processor = TradeResultsProcessor(args.tradeid)

    # Fetch and parse trade results
    results_text = results_processor.fetch_results()
    traders_list, preamble = results_processor.parse_results(results_text)

    # Handle random traders option
    if args.random_traders > 0:
        random_selection = random.sample(traders_list, args.random_traders)
        print(f"Randomly selected traders: {random_selection}")

    # Exit early if only processing data
    if args.no_labels:
        sys.exit(0)

    # Get trader information (with caching)
    trader_info = results_processor.get_trader_info(traders_list)
    print(f"{len(trader_info)} traders found")

    # Generate PDF
    generator = NametagGenerator(args.tradeid)

    # Generate name lists if requested
    if args.print_namelists:
        cutoffs = generator._calculate_cutoffs(trader_info, args.groups)
        generator.generate_name_lists(trader_info, cutoffs)

    # Generate section covers first, then nametags
    generator.generate_section_covers(trader_info, preamble, args.groups)
    generator.generate_nametags(trader_info, args.groups)
    generator.save()


if __name__ == "__main__":
    main()
