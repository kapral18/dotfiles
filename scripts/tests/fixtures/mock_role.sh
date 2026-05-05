#!/usr/bin/env bash
# Mock role harness for orchestrator tests.
# Reads stdin (the orchestrator-built context) but ignores most of it.
# Behavior driven by env vars set by the test harness:
#   RALPH_TEST_ROLE             - role name (planner|executor|reviewer|re_reviewer)
#   RALPH_TEST_GOAL             - goal text echoed back into spec.json
#   RALPH_TEST_ARTIFACT         - target file path the executor will create
#   RALPH_TEST_CONTENT          - content to write
#   RALPH_TEST_MAX_ITERS        - cap echoed in spec
#   RALPH_TEST_COUNTER_DIR      - dir holding per-role iteration counters
#   RALPH_TEST_FAIL_EXECUTOR_ITER - if set and matches counter, executor "fails"
#                                   (writes nothing, reviewer should say needs_iteration)
#   RALPH_TEST_FAIL_REVIEWER    - if "true", reviewer says fail on iter 1; re_reviewer
#                                  downgrades to needs_iteration so iter 2 retries
#   RALPH_TEST_REVIEWER_VERDICT  - if set ("pass"|"fail"|"needs_iteration"), the
#                                  reviewer emits exactly this verdict regardless
#                                  of artifact state; used to script the diversity
#                                  gate's reviewer side under disagreement
#   RALPH_TEST_RE_REVIEWER_VERDICT - if set ("pass"|"fail"|"needs_iteration"), the
#                                    re_reviewer emits exactly this final_verdict
#                                    regardless of artifact state; used to script
#                                    the diversity gate's adjudication under
#                                    disagreement (final_verdict wins per the
#                                    orchestrator's resolution at scripts/ralph.py)
#   RALPH_TEST_OMIT_ANCHOR      - if "true", role omits the mandatory ANCHOR header
#                                  (used to prove role validation gates on ANCHOR)
#   RALPH_TEST_PLANNER_ASK_FIRST - if "true", planner's first invocation emits
#                                  RALPH_QUESTIONS instead of a spec; subsequent
#                                  invocations emit a normal spec (after answers)
#   RALPH_TEST_EXECUTOR_ASK_ITER - if set and equals counter, executor emits
#                                  RALPH_QUESTIONS instead of writing the artifact
#   RALPH_TEST_WORKFLOW         - workflow id the planner declares in its spec
#                                  (one of: feature|bugfix|review|research)

set -eu

# Drain stdin so the harness sees a clean exit; we don't actually need it.
cat > /dev/null

role="${RALPH_TEST_ROLE:?RALPH_TEST_ROLE not set}"
counter_dir="${RALPH_TEST_COUNTER_DIR:-/tmp/ralph-test-counters}"
mkdir -p "$counter_dir"
counter_file="$counter_dir/$role"
n=$(($(cat "$counter_file" 2> /dev/null || echo 0) + 1))
printf '%s\n' "$n" > "$counter_file"

# Anchor scaffolding: every role re-anchors to the goal verbatim. Tests can
# flip RALPH_TEST_OMIT_ANCHOR=true to prove the validation gate fires.
emit_anchor() {
  if [ "${RALPH_TEST_OMIT_ANCHOR:-false}" != "true" ]; then
    printf 'ANCHOR: %s\n\n' "${RALPH_TEST_GOAL:-test goal}"
  fi
}

case "$role" in
  planner)
    emit_anchor
    if [ "${RALPH_TEST_PLANNER_ASK_FIRST:-false}" = "true" ] && [ "$n" = "1" ]; then
      cat << 'JSON'
```json
{
  "questions": [
    {"id": "q1", "text": "Which file should hold the artifact?"},
    {"id": "q2", "text": "Should we preserve any legacy export?"}
  ]
}
```
RALPH_QUESTIONS
JSON
    else
      cat << JSON
\`\`\`json
{
  "goal": "${RALPH_TEST_GOAL:-test goal}",
  "workflow": "${RALPH_TEST_WORKFLOW:-feature}",
  "target_artifact": "${RALPH_TEST_ARTIFACT:?RALPH_TEST_ARTIFACT not set}",
  "success_criteria": [
    "artifact file exists at ${RALPH_TEST_ARTIFACT}",
    "artifact contains expected content"
  ],
  "complexity": "simple",
  "executor_count": 1,
  "max_iterations": ${RALPH_TEST_MAX_ITERS:-3},
  "max_minutes": 1,
  "iteration_task_seed": "create the artifact at ${RALPH_TEST_ARTIFACT}",
  "rationale": "test scenario"
}
\`\`\`
LEARNING: mock planner produced spec for ${RALPH_TEST_GOAL:-test goal}
RALPH_DONE
JSON
    fi
    ;;

  executor)
    emit_anchor
    fail_iter="${RALPH_TEST_FAIL_EXECUTOR_ITER:-}"
    ask_iter="${RALPH_TEST_EXECUTOR_ASK_ITER:-}"
    if [ -n "$ask_iter" ] && [ "$n" = "$ask_iter" ]; then
      cat << 'JSON'
The plan is materially ambiguous; cannot proceed without input.
```json
{
  "questions": [
    {"id": "ex1", "text": "Should I overwrite or append?"}
  ]
}
```
RALPH_QUESTIONS
JSON
    elif [ -n "$fail_iter" ] && [ "$n" = "$fail_iter" ]; then
      echo "Mock executor failure on iteration $n (RALPH_TEST_FAIL_EXECUTOR_ITER)"
      echo "Did not create the file; will let reviewer fail us."
      echo "SELF_CHECK:"
      echo "- artifact at $RALPH_TEST_ARTIFACT"
      echo "LEARNING: mock executor encountered scripted failure on iter $n"
      echo "RALPH_DONE"
    else
      mkdir -p "$(dirname "$RALPH_TEST_ARTIFACT")"
      printf '%s' "${RALPH_TEST_CONTENT:-mock content}" > "$RALPH_TEST_ARTIFACT"
      echo "Wrote $RALPH_TEST_ARTIFACT (iter=$n)"
      echo "SELF_CHECK:"
      echo "- artifact exists at $RALPH_TEST_ARTIFACT"
      echo "- artifact contents equal '${RALPH_TEST_CONTENT:-mock content}'"
      echo "LEARNING: mock executor created ${RALPH_TEST_ARTIFACT} successfully on iter $n"
      echo "RALPH_DONE"
    fi
    ;;

  reviewer)
    emit_anchor
    fail_reviewer="${RALPH_TEST_FAIL_REVIEWER:-false}"
    forced_verdict="${RALPH_TEST_REVIEWER_VERDICT:-}"
    artifact_exists=false
    if [ -f "$RALPH_TEST_ARTIFACT" ]; then
      actual="$(cat "$RALPH_TEST_ARTIFACT")"
      if [ "$actual" = "${RALPH_TEST_CONTENT:-mock content}" ]; then
        artifact_exists=true
      fi
    fi
    if [ -n "$forced_verdict" ]; then
      case "$forced_verdict" in
        pass)
          cat << JSON
\`\`\`json
{"verdict": "pass", "criteria_met": ["forced pass"], "criteria_unmet": [], "next_task": "", "blocking_reason": "", "notes": "RALPH_TEST_REVIEWER_VERDICT=pass on iter $n"}
\`\`\`
RALPH_DONE
JSON
          ;;
        fail)
          cat << JSON
\`\`\`json
{"verdict": "fail", "criteria_met": [], "criteria_unmet": ["forced fail"], "next_task": "", "blocking_reason": "RALPH_TEST_REVIEWER_VERDICT=fail", "notes": "forced fail on iter $n"}
\`\`\`
RALPH_DONE
JSON
          ;;
        needs_iteration)
          cat << JSON
\`\`\`json
{"verdict": "needs_iteration", "criteria_met": [], "criteria_unmet": ["forced needs_iteration"], "next_task": "retry", "blocking_reason": "", "notes": "forced needs_iteration on iter $n"}
\`\`\`
RALPH_DONE
JSON
          ;;
        *)
          echo "unknown RALPH_TEST_REVIEWER_VERDICT: $forced_verdict" >&2
          exit 1
          ;;
      esac
    elif [ "$fail_reviewer" = "true" ] && [ "$n" = "1" ]; then
      cat << JSON
\`\`\`json
{"verdict": "fail", "criteria_met": [], "criteria_unmet": ["scripted reviewer failure"], "next_task": "", "blocking_reason": "", "notes": "scripted fail to trigger re_reviewer"}
\`\`\`
RALPH_DONE
JSON
    elif [ "$artifact_exists" = "true" ]; then
      cat << JSON
\`\`\`json
{"verdict": "pass", "criteria_met": ["artifact exists", "content matches"], "criteria_unmet": [], "next_task": "", "blocking_reason": "", "notes": "passes on iter $n"}
\`\`\`
LEARNING: mock reviewer accepted artifact on iter $n
RALPH_DONE
JSON
    else
      cat << JSON
\`\`\`json
{"verdict": "needs_iteration", "criteria_met": [], "criteria_unmet": ["artifact missing"], "next_task": "create the artifact", "blocking_reason": "", "notes": "no artifact at $RALPH_TEST_ARTIFACT on iter $n"}
\`\`\`
RALPH_DONE
JSON
    fi
    ;;

  re_reviewer)
    emit_anchor
    forced_verdict="${RALPH_TEST_RE_REVIEWER_VERDICT:-}"
    primary_verdict="${RALPH_TEST_REVIEWER_VERDICT:-}"
    artifact_exists=false
    if [ -f "$RALPH_TEST_ARTIFACT" ]; then
      actual="$(cat "$RALPH_TEST_ARTIFACT")"
      if [ "$actual" = "${RALPH_TEST_CONTENT:-mock content}" ]; then
        artifact_exists=true
      fi
    fi
    if [ -n "$forced_verdict" ]; then
      # `agree_with_primary` is informational only — the orchestrator's verdict
      # resolver consumes `final_verdict`. We compute a sensible value so
      # downstream display/logs stay coherent: agree iff the forced re_reviewer
      # verdict matches the (also possibly forced) reviewer verdict, defaulting
      # to "agree on pass" when the reviewer side wasn't scripted.
      if [ -n "$primary_verdict" ]; then
        if [ "$forced_verdict" = "$primary_verdict" ]; then
          agree=true
        else
          agree=false
        fi
      elif [ "$forced_verdict" = "pass" ]; then
        agree=true
      else
        agree=false
      fi
      next_task=""
      if [ "$forced_verdict" = "needs_iteration" ]; then
        next_task="retry per scripted re_reviewer override"
      fi
      cat << JSON
\`\`\`json
{"agree_with_primary": $agree, "final_verdict": "$forced_verdict", "next_task": "$next_task", "blocking_reason": "", "notes": "RALPH_TEST_RE_REVIEWER_VERDICT=$forced_verdict on iter $n"}
\`\`\`
RALPH_DONE
JSON
    elif [ "$artifact_exists" = "true" ]; then
      cat << JSON
\`\`\`json
{"agree_with_primary": true, "final_verdict": "pass", "next_task": "", "blocking_reason": "", "notes": "re_reviewer confirms artifact on iter $n"}
\`\`\`
RALPH_DONE
JSON
    else
      cat << JSON
\`\`\`json
{"agree_with_primary": false, "final_verdict": "needs_iteration", "next_task": "retry creating the artifact", "blocking_reason": "", "notes": "re_reviewer says recoverable on iter $n"}
\`\`\`
RALPH_DONE
JSON
    fi
    ;;

  reflector)
    emit_anchor
    cat << JSON
\`\`\`json
{
  "capsules": [
    {
      "title": "mock reflector capsule",
      "body": "Reusable observation produced by the reflector mock for ${RALPH_TEST_GOAL:-test goal}.",
      "kind": "fact",
      "scope": "project",
      "domain_tags": ["ralph", "test"],
      "confidence": 0.7,
      "refs": []
    }
  ]
}
\`\`\`
RALPH_DONE
JSON
    ;;

  *)
    echo "unknown role: $role" >&2
    exit 1
    ;;
esac
