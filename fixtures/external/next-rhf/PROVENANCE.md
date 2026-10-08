# Public example provenance

The form and stylesheet originate from Vercel's MIT-licensed Next.js repository:
https://github.com/vercel/next.js/tree/1fffea65b678744091a6dc13996339dcf8dcfe4e/examples/with-react-hook-form

Pinned repository commit: `1fffea65b678744091a6dc13996339dcf8dcfe4e`.
Original form blob: `8f421e010b0720b4d2ef0ebaa7e34ff38a4d667e`.
The untouched form is `pages/index.upstream.tsx.txt`; the executed form is
`pages/index.tsx`. The accompanying patch records the exact modifications.
The original `register`, validation, fields, and success-view logic are retained.

Instrumentation adds a readiness effect and records the actual callback arguments
at `/api/receipt` before the original `setUser` transition. The API route appends
received payloads to `.receipts.jsonl`, which is generated during testing and is
not part of the release. The capture observer in `run_public.py` records terminal
consumption before the submit handler. It does not replace the original binding.

The dependency lock pins Next.js 15.5.27, React/ReactDOM 18.3.1, and React Hook
Form 7.51.5. These pins are an evaluation environment, not a claim that this
repository commit shipped those exact dependency versions. Production documents
are Next's build-time prerendered HTML; development serves the normal development
application. JavaScript chunks are delayed through browser network routing.

Sixteen production profiles and two available development profiles obtain clean
consumer receipts. Fourteen development profiles request hidden early controls
and are retained as unavailable, with no submission attempted. Only toy input
is used (`toy-user`, `toy-pass`, and a Boolean remember field). A form containing
a password control is not evidence that any real credentials were collected.

`LICENSE.txt` retains the upstream MIT notice. The added instrumentation is
covered by the artifact's MIT license. No upstream defect is attributed to this
clean example, and this is one independently maintained example rather than a
sample of deployed Web applications.
