# Third-party components and scientific inputs

`vendor/react-19.1.1.production.js` contains the React 19.1.1, React DOM 19.1.1,
and scheduler production library sections extracted from the installed
Playwright trace-viewer bundle.  Upstream copyright/license comments are retained
and three global exports are appended for the local adapter.  The extraction is
recorded in `scripts/recover_vendors.py`.  React's MIT license is in
`licenses/React-MIT.txt`.  This is not represented as the official npm build or
a server renderer.

`vendor/vue-3.5.13.production.js` is the unmodified Vue 3.5.13 production global
build found in the installed `trame_client` package.  Its version and license
header are retained; `licenses/Vue-MIT.txt` contains the upstream MIT terms.  It
is the real client hydration runtime, not Vue's server renderer.

`vendor/acorn.mjs` is Acorn 8.15.0 for offline parsing of the bounded handler
subset.  Its MIT license is in `licenses/Acorn-MIT.txt`.  Acorn is prior
infrastructure, not a HydraKeep analysis contribution.

The locally installed Playwright package supplies automation at runtime and is
not copied into the artifact.  Chromium, Python, Node.js, TeX, operating-system
files, fonts, virtual environments, and `node_modules` are not redistributed.
Browser-version changes are replications rather than identical-version
reproductions.

## Authored fixtures and data

The single-field, vector, transaction, heterogeneous-control, semantic-control,
and unknown-effect fixtures use benign toy strings, selections, and Booleans.
They contain no production traffic, personal data, credentials, autofill values,
human subjects, or proprietary datasets.  R15 is an explicitly seeded keyed
remount regression.  Other authored outcomes concern chosen integrations and
contracts and are not represented as previously unknown upstream defects.  The
loopback receivers store only authored form values.

## Native integrations and public example

Native clients use pinned React 19.1.1/React DOM 19.1.1 and Vue 3.5.13, 3.5.40,
3.5.41, and 3.5.43 with corresponding server renderers.  `vendor/native/` records
built-file manifests and upstream MIT notices; bundled code retains embedded
license comments.  Server/client component factories and the browser drivers
are original artifact code.

`fixtures/external/next-rhf/` adapts Vercel's MIT-licensed React Hook Form example
at commit `1fffea65b678744091a6dc13996339dcf8dcfe4e`.  The source snapshot, MIT
notice, instrumentation patch, package lock, provenance, and hashes are included.
The callback is instrumented to record its actual values before the original
success transition.  The password field receives only `toy-pass`.  Dependencies
are installed during reproduction; no installed tree, build output, or browser
executable is redistributed.

The InitRacer control driver retrieves the original analyzer at commit
`b5f1c0bffd118008c64b30ec3723b2443b6d95cf` into a separate checkout.  Upstream
analyzer source and generated runtime bundles are not included.  The comparison
uses the original observation analyzer with a local HTTP/browser driver and four
plain-JavaScript semantic controls.

## Manuscript inputs

The paper cites external publications and official documentation but does not
redistribute their PDFs or screenshots.  The ACM class and bibliography style in
`paper/template-license/` retain the publisher's supplied license and are not
claimed as original project code.
