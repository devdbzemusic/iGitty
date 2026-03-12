"""Tests fuer das Maskieren sensibler Werte."""

from core.masking import mask_secret


def test_mask_secret_masks_middle_section() -> None:
    """
    Prueft die typische Maskierung eines langen Geheimnisses.

    Eingabeparameter:
    - Keine.

    Rueckgabewerte:
    - Keine.

    Moegliche Fehlerfaelle:
    - AssertionError bei falscher Maskierung.

    Wichtige interne Logik:
    - Der Test stellt sicher, dass Anfang und Ende sichtbar bleiben, der Mittelteil aber verborgen ist.
    """

    assert mask_secret("1234567890") == "1234****90"
