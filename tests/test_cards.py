import unittest

from deepsix_core.cards import (
    NUM_CARDS,
    RANKS,
    SUITS,
    ShortDeckCardError,
    decode_card,
    encode_card,
    format_card,
    legacy_rank_suit_to_core,
    parse_card,
)


class ShortDeckCardCodecTests(unittest.TestCase):
    def test_exactly_36_unique_cards(self):
        cards = {encode_card(rank, suit) for suit in SUITS for rank in RANKS}
        self.assertEqual(len(cards), 36)
        self.assertEqual(cards, set(range(NUM_CARDS)))

    def test_round_trip_all_cards(self):
        for suit in SUITS:
            for rank in RANKS:
                card = encode_card(rank, suit)
                decoded = decode_card(card)
                self.assertEqual((decoded.rank, decoded.suit), (rank, suit))
                self.assertEqual(parse_card(format_card(card)), card)

    def test_reject_removed_ranks(self):
        for rank in "2345":
            with self.assertRaises(ShortDeckCardError):
                encode_card(rank, "s")

    def test_legacy_openholdem_boundary_rejects_2_to_5(self):
        for rank in range(2, 6):
            with self.assertRaisesRegex(ShortDeckCardError, "INVALID_SHORTDECK_CARD"):
                legacy_rank_suit_to_core(rank, 0)

    def test_legacy_openholdem_boundary_accepts_6_to_ace(self):
        for suit in range(4):
            for rank in range(6, 15):
                card = legacy_rank_suit_to_core(rank, suit)
                decoded = decode_card(card)
                self.assertEqual(decoded.rank, RANKS[rank - 6])
                self.assertEqual(decoded.suit, SUITS[suit])

    def test_invalid_card_ids_are_rejected(self):
        for card in (-1, 36, 100):
            with self.assertRaises(ShortDeckCardError):
                decode_card(card)


if __name__ == "__main__":
    unittest.main()
