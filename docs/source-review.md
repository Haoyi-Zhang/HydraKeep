# Source and closest-work review

The implementation and paper were checked against primary framework sources,
official Web specifications, maintained documentation, and the closest research
tools.  The complete key-by-key ledger is `../../paper/reference-audit.csv`.

## Framework behavior

React 19.1.1's pinned `ReactDOMInput.js` hydration path avoids the ordinary
initial value assignment, and the textarea path separately handles initial text
content.  React documentation distinguishes controlled/default bindings,
preservation/reset of component state, server rendering, and hydration.
HydraKeep therefore does not treat every post-hydration replacement as a defect;
its contract states the intended ownership and transition.

Vue 3.5.13's pinned `vModel.ts` treats model state as authoritative for form
bindings.  The evaluated historical pair is anchored in the reported early
input-preservation issue and merged fix, with later remaining-control coverage
tracked separately.  Static `value` bindings in the authored fixtures are
reported explicitly rather than equated with React `defaultValue`.

HTML, DOM, Fetch, XMLHttpRequest/FormData, Input Events, and WebDriver sources
anchor the distinction among initial attributes, current properties, trusted
input, successful controls, request bodies, and receiver observations.

## Closest testing and analysis work

InitRacer establishes browser initialization races and input-overwrite detection.
HydraKeep runs the original observation analyzer on four local semantic controls
to show the property boundary: overwrite detection does not by itself establish
which consumer received an accepted edit or whether a reset was permitted.
AjaxRacer, EventRaceCommander, record/replay systems, Web test generation,
parametric monitoring, contracts, and partial-order reduction are cited as prior
techniques rather than relabeled contributions.

FormNexus and FormWhisperer address Web-form constraint inference and solving.
They motivate richer form semantics but do not provide the hydration-to-consumer
preservation obligation evaluated here.  The maintained Next.js React Hook Form
example is used as an external clean integration, not as evidence that the
method applies to all production forms.

## Citation scope

Publisher metadata, DOI/title correspondence, or pinned official source anchors
were checked for all 73 bibliography entries.  Relevant source sections and
paper scope were reviewed for the claims made in the manuscript.  Citation
verification is not described as experimental replication of every cited tool.
