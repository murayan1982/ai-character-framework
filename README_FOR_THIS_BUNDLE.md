# FW v5.1.0 Commit 1 bundle

Proposed commit:

```text
docs: add v5.1.0 host app integration roadmap
```

Copy these files into the FW repository:

```text
docs/roadmap_feature_v5.1.0.md
docs/drc_v300_framework_feedback_summary.md
docs/v510_host_app_sdk_readiness_notes.md
```

This is a docs-only roadmap/feedback lock. It should not change runtime behavior,
DRC behavior, provider execution, or release artifacts.

Suggested verification after copying:

```powershell
python -m compileall -q .
python scripts/check_release_package.py
```

If README or release-package policy tracks roadmap docs, add the v5.1.0 roadmap
there in a later commit rather than mixing that with this feedback-lock commit.
