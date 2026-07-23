# G1 Grading Rubric (human-authored)

This rubric defines how a candidate answer is graded against a case's independently
hand-authored expected findings. It is the contract the deterministic grader
(`benchmarks/g1/grader.py`) encodes and the reference a later model-backed grader is
reviewed against. The rubric is covered by the `rubric_review` human token at Gate G1 exit
(Story 2.4); it is authored here.

## Pass rule (error-diagnosis, G1.2)

G1.2 requires the answer to name **the** failing object and **the** cause — not *an* object
and not a vague gesture at "something is broken". A candidate answer **PASSES** iff BOTH hold:

1. **Object identity match.** The answer names the expected failing object by its immutable
   `Name` (case-insensitive, whole-token). Naming a *different* object in the tree — even a
   real one — is a FAIL (the "names *an* object not *the* object" threat).
2. **Cause match.** The answer contains at least one of the expected cause keywords for the
   case (e.g. "conflicting" / "over-constrained" for an over-constrained sketch; "expression"
   / "binding" for a dangling expression; "missing sketch" / "profile" for a pad orphaned from
   its sketch; "missing tool" / "linked object" for a boolean whose operand was removed).

If either the object or the cause is absent, the answer **FAILS**. This is the
"fluent-plausible-wrong" counter: a confidently-worded answer that names the wrong object or
the wrong cause does not pass on fluency.

## Expected-findings shape

Each error-diagnosis case declares:

```yaml
expected:
  object: <the failing object Name>
  cause: "<human-readable cause>"
  cause_keywords: [<keyword>, <keyword>, ...]
```

The grader matches `object` (identity) + any one of `cause_keywords` (cause). `cause` is the
human-readable reference; the keywords are the matchable surface forms.

## Worked example — a confident-wrong answer that must FAIL

Case `g1-broken-oc-bracket-plate`: the failing object is `BracketPlate` (an over-constrained
sketch with conflicting constraints).

> "The recompute fails because **MountSlot** has conflicting constraints that over-constrain
> the sketch."

**Verdict: FAIL.** The cause keyword ("conflicting" / "over-constrained") is present, but the
answer names the wrong object (`MountSlot`, not `BracketPlate`). Naming *an* object is not
naming *the* object — G1.2 is not satisfied.

A second confident-wrong shape (right object, wrong cause):

> "**SpacerHeight** fails because its material property is set to an unsupported value."

**Verdict: FAIL** for case `g1-broken-be-spacer-height`: the object is right, but the cause is
wrong — the real cause is a dangling **expression binding** to a missing object, and no
expected cause keyword ("expression" / "binding" / "reference" / "not found") appears.

## Worked example — a correct answer that must PASS

Case `g1-broken-be-spacer-height`: the failing object is `SpacerHeight` (a box whose `Height`
expression binds to a non-existent object).

> "**SpacerHeight** fails because its Height **expression binding** references a non-existent
> object. Repoint the expression to an object that exists."

**Verdict: PASS.** The answer names the expected object (`SpacerHeight`) AND a matching cause
keyword ("expression" / "binding"). Both conditions hold.

## Answer-quality (G1.1) — reviewer note

G1.1 tree-explanation / next-tool-guidance answers are fuzzier than the structured
`{object, cause}` of G1.2. The shipped deterministic grader scores the structured
error-diagnosis path; the `GraderClient` seam in `grader.py` is where a model-backed grader
(reviewed against this rubric) plugs in for G1.1 when a backend lands (Stories 2.2/2.3). Until
then, G1.1's expected findings in `eval-questions.yaml` are hand-authored references for that
later grader, and the `--stub` run fails G1.1 honestly (no assistant yet).
