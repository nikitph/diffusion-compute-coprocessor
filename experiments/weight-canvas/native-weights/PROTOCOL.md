# Signed-weight diagnostic v0.3

Exploratory one-task check specified during v0.2, before its own run. Reuse the
velocity-reversed task with all five arms. Same models, inference schedule,
80-token limit, feedback timing, practice and held-out observations as v0.2.
The only intended task-interface change is direct signed W1 values rather than
E values offset by two. The prompt is rewritten to explain the same game and
network without the encoding. The evaluator accepts literal or indexed W1 writes
with integer values -2 through 2 (integer-valued floats also accepted), then maps
them to the shared controller evaluator internally. Actual signed weights appear
in model feedback. Reject all other executable forms.

This is one already-seen task, not independent confirmation or a clean single-factor
ablation: wording and representation both change. Its purpose is to identify an
interface bottleneck, not to establish superiority. Report separately.
