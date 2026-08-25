"""Procurement 6.7 E-Auction Management URL patterns."""
from .Auctions import urlpatterns as _eauc_auctions
from .Bids import urlpatterns as _eauc_bids

urlpatterns = [
    *_eauc_auctions,  # 6.7 register/setup/lifecycle/invites + floor/rules/console/board
    *_eauc_bids,      # 6.7 live bidding screen + post-auction results/award
]
