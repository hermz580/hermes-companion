"""Ghost monitors are dropped; real screens beside the primary are kept."""
from hermes_companion.renderer.overlay import (
    connected_to, horizontal_neighbour, shared_band, walk_span)

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

# --- walking off the edge of a panel -------------------------------------------
#
# The bug this guards (found on a 1600x900 primary with three 1920x1080 panels
# reported ABOVE it): the roam target was chosen by x-range alone, so a pet that
# walked right past x=1600 had its centre inside the panel above, adopted it, and
# re-homed to y=-364. The window stayed alive and on top while being invisible on
# every real screen. A side-by-side panel shares a vertical band; a panel above or
# below shares only a full-length edge.

# The exact geometry reported by the machine where the pet vanished.
HOST_PRIMARY = (0, 0, 1600, 900)
ABOVE_LAYOUT = [
    (0, 0, 1600, 900),
    (-2102, -1086, -182, -6),
    (-182, -1080, 1738, 0),
    (1738, -1087, 3658, -7),
]
REAL_RIGHT = (1600, 0, 3200, 900)


def test_panels_beside_one_another_share_a_band():
    assert shared_band(PRIMARY, REAL_RIGHT)
    assert shared_band(PRIMARY, (-1600, 100, 0, 1000))


def test_a_panel_above_or_below_shares_no_band():
    assert not shared_band(PRIMARY, (0, -1080, 1600, 0))
    assert not shared_band(PRIMARY, (0, 1080, 1600, 2160))


def test_walking_off_the_right_edge_onto_a_phantom_row_is_refused():
    """The exact x that used to steal the pet (centre 1600..1738)."""
    for cx in (1600, 1650, 1737):
        assert horizontal_neighbour(HOST_PRIMARY, cx, ABOVE_LAYOUT) is None, cx


def test_walking_off_the_right_edge_onto_a_real_panel_is_still_allowed():
    layout = [HOST_PRIMARY, REAL_RIGHT]
    assert horizontal_neighbour(HOST_PRIMARY, 1600, layout) == REAL_RIGHT
    assert horizontal_neighbour(HOST_PRIMARY, 3199, layout) == REAL_RIGHT


def test_walking_back_off_a_real_panel_returns_to_the_primary():
    layout = [PRIMARY, REAL_RIGHT]
    assert horizontal_neighbour(REAL_RIGHT, 1599, layout) == PRIMARY


def test_the_walkable_span_never_includes_the_phantom_row():
    """room() must not promise floor the pet cannot stand on."""
    assert walk_span(HOST_PRIMARY, ABOVE_LAYOUT) == (0, 1600)
    assert walk_span(HOST_PRIMARY, [HOST_PRIMARY, REAL_RIGHT]) == (0, 3200)
