"""Ghost monitors are dropped; real screens beside the primary are kept."""
from hermes_companion.renderer.overlay import connected_to

PRIMARY = (0, 0, 1920, 1080)


def test_a_second_screen_beside_the_primary_is_kept():
    right = (1920, 0, 3840, 1080)
    left = (-1600, 100, 0, 1000)
    above = (200, -900, 1800, 0)
    assert connected_to(PRIMARY, [PRIMARY, right, left, above]) == [PRIMARY, right, left, above]


def test_a_chain_of_screens_is_kept():
    second, third = (1920, 0, 3840, 1080), (3840, 0, 5760, 1080)
    assert connected_to(PRIMARY, [third, PRIMARY, second]) == [third, PRIMARY, second]


def test_detached_ghosts_are_dropped():
    ghosts = [(-5000, -3000, -3080, -1920), (-9000, 0, -7080, 1080)]
    assert connected_to(PRIMARY, [PRIMARY] + ghosts) == [PRIMARY]


def test_touching_only_at_a_corner_is_not_joined():
    corner = (1920, 1080, 3840, 2160)
    assert connected_to(PRIMARY, [PRIMARY, corner]) == [PRIMARY]
