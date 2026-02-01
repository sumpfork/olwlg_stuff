# Online Want List Generator Stuff

I participate in Math Trades that use the [Online Want List Generator](https://bgg.activityclub.org/olwlg/) and print labels to identify traders when meeting in person.

I also ran a raffle to give away to copies of [Seas of Havoc](https://boardgamegeek.com/boardgame/343525/seas-havoc).

This code helps with both.

To use:
- You'll need to register with the BGG API and get a token
- Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Run `uv run olwlg-nametags <trade_id>` <token> where `trade_id`  is the trade id from the Online Want List Generator and `<token>` is your BGG API token. In particular, this script accesses http://bgg.activityclub.org/olwlg/trade_id-results-official.txt, so you can grab the `trade_id` from there or or any other OLWLG URL for your trade.

This will (obviously) only work once the OLWLG results exist for this trade. It generates traders_<trade_id>.pdf in the same directory.
