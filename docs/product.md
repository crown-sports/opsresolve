# Product fit and evidence

The intended user owns an HTTP application and must decide what to investigate,
whether a declared repair recovered it, or whether two trace samples reveal a
regression. These are use-case hypotheses drawn from the implemented workflow;
there are no published user interviews or adoption measurements behind them.

## What is implemented

| Advantage over an ad hoc workflow | Evidence you can inspect | What it does not establish |
| --- | --- | --- |
| Keep simultaneous fault candidates instead of stopping at the first symptom | [Diagnosis tests](../tests/test_diagnosis.py), [three-topology experiments](results.md) | Accuracy on unknown production faults |
| Join exact patches, stale-plan rejection and business recovery checks | [Live recovery tests](../tests/test_live_recovery.py), [interruption tests](../tests/test_interruption.py) | Arbitrary repair support or globally atomic multi-file changes |
| Compare recorded operations with explicit missing/undersampled states | [Trace comparison tests](../tests/test_trace_compare.py), [synthetic exports](../examples/trace-regression/before.json) | Statistical significance or deployment causality |

These are reproducible integration advantages using established algorithms.
The code is MIT licensed and can be copied. There is no evidence here of an
exclusive algorithm, proprietary incident corpus or established commercial moat.

## Next evidence to earn

1. **First-use fit:** observe application owners completing the demo and importing
   their own sanitized trace. Record completion/failure and the decision they
   could make, including unsupported inputs. No completion rate is measured yet.
2. **Coverage:** collect consented, sanitized incident reproductions with known
   outcomes, including ambiguous and failed repairs. Broaden contracts only when
   their preconditions and recovery checks can be tested. A maintained corpus
   could become a cumulative asset; the current development fixtures are not it.
3. **Operational trust:** measure setup effort and false regression alerts under
   real sampling changes before promising deployment gating or time savings.

For a trial, begin with [the README demo](../README.md#try-a-complete-recovery),
then a read-only target described in [usage](usage.md). Keep monitoring for
collection and alerts. Repair requires explicit contracts and operator review.

## Version availability

This document was added after v0.2.0 and is available on main; all demo commands
above already work in v0.2.0. Existing release archives are unchanged.
