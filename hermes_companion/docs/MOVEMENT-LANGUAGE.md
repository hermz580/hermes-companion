# Read the companion

The character is a visual explanation of reported AI activity. It does not
expose private chain of thought, infer successful recovery from failure, or
claim task completion from a successful tool call.

| Movement | Meaning | What you do |
| --- | --- | --- |
| Wake and stretch | Starting a task | Let it begin |
| Travel then steady work | A tool started | Continue your own work |
| Scan ring | Web activity | Watch if relevant |
| File cards | File activity | Watch if relevant |
| Branch accent | Development activity | Watch if relevant |
| Inspecting posture | Tool returned; progress review | This is not task completion |
| Gentle repeated wave, gold label | Approval required | Return to the original approval UI |
| Failure posture, pink label | Tool failed | Recovery has not been confirmed |
| Celebration, then rest | Task completion reported | Review the result in Hermes |
| Quiet resting pose | No active work reported | No action requested |

Labels teach the movement vocabulary and provide a second cue beyond color.
Approval remains visible across background tool and idle events until an
explicit approval response arrives. No auto-approval or task control is added.

## Run

Place this directory under a parent as `hermes_companion`. From that parent:

```sh
python -m hermes_companion live
python -m hermes_companion status --events /path/to/events.jsonl
python -m unittest discover -s hermes_companion/tests -p test_attention_language.py
```

Live display requires Windows, Tk, Pillow and an existing configured pet atlas.
The live renderer reads the installed pet; this package does not install art.

## Current limits

This is a local implementation, not a published release. Automated checks cover
state semantics and frame ordering; live visual quality with the user's atlas
and multi-device animation synchronization still require verification.
Existing nine-row art limits poses; different work categories reuse poses with
different accents. Recipes repeat for identical pose/category/step inputs;
there is no unlimited new anatomy or automatic motion generation.
The attention model currently represents one combined event stream, not
independently tracked simultaneous tasks. Helper counts require paired events.
There is no tool-detail inspector, progress percentage, or stalled-task detector.
