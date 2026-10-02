from types import SimpleNamespace

from hermes_companion.renderer.petdex_overlay import PetdexOverlay, motion_recipe


def test_motion_recipe_is_deterministic_for_relay_peers():
    assert motion_recipe("terminal_work", "terminal", 2) == motion_recipe(
        "terminal_work", "terminal", 2
    )


def test_motion_recipe_varies_by_pose_category_and_order():
    baseline = motion_recipe("terminal_work", "terminal", 0)
    assert motion_recipe("terminal_work", "web", 0) != baseline
    assert motion_recipe("web_scan", "terminal", 0) != baseline
    assert motion_recipe("terminal_work", "terminal", 1) != baseline


def test_motion_recipe_adds_category_specific_effects():
    assert motion_recipe("work", "terminal", 0).effect == "terminal"
    assert motion_recipe("work", "web", 0).effect == "scan"
    assert motion_recipe("work", "file", 0).effect == "files"
    assert motion_recipe("work", "development", 0).effect == "git"


def test_play_chain_attaches_recipes_without_losing_truthful_motion_fields():
    holder = SimpleNamespace(home_x=0, home_y=0, x=0, y=0)
    step = {
        "pose": "terminal_work",
        "duration_ms": 250,
        "move": {"dx": 12, "dy": -4, "type": "hop", "easing": "bounce"},
    }

    [beat] = PetdexOverlay._beats_for_step(holder, step, "terminal", 3)

    assert beat.row == "waiting"
    assert beat.duration_ms == 250
    assert beat.move_dx == 12
    assert beat.move_dy == -4
    assert beat.move_type == "hop"
    assert beat.ease == "bounce"
    assert beat.prop == "terminal"
    assert beat.recipe == motion_recipe("terminal_work", "terminal", 3)
