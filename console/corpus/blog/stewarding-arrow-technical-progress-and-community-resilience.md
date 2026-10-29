---
title: "Stewarding Arrow: Technical progress and community resilience"
url: "https://insightsoftmax.com/blog/stewarding-arrow-technical-progress-and-community-resilience"
author: "Alex Scammon"
date: "2026-06-03"
kind: "sections"
---

# Stewarding Arrow: Technical progress and community resilience

Apache Arrow has become foundational infrastructure for the modern data stack. Many of these workflows (everything from financial systems to machine learning pipelines and GPU-accelerated analytics) move data through Arrow's columnar format without the engineers who depend on it giving much thought to what keeps it healthy. With that much data moving through Arrow so reliably, it was easy to assume the infrastructure would just be there to support the workloads without intervention.

In 2025, that assumption was tested.

When Voltron Data wound down its operations, it took with it a significant share of the people who had been paid full-time to keep Arrow healthy. Their roles included maintaining CI, reviewing PRs, benchmarking performance, cutting releases, triaging issues, and doing the unglamorous work that open source projects depend on to function. The contributor pool fell from 94 active contributors to 59. The Contributor Absence Factor (the number of people whose absence would remove half of all merged PR output) dropped from 11 to five. The benchmarking infrastructure that tracks performance regressions across every commit was left without a home.

No one metric perfectly encapsulates community health, but the number of closed issues per month in the Arrow project did showed a distressing trend:

## Source: https://github.com/arrow-maintenance/arrowdash/tree/main/data/cache

While Voltron continued to employ open-source Arrow maintainers, active contributors remained around 50 per month. Now it hovers around 30.

Arctos Alliance was formed to address this directly. It is a small group of contributors, working largely part-time and on limited funding, who stepped in to hold the line. They’re migrating the infrastructure, working down the issue backlog, onboarding new maintainers, and continuing to ship meaningful technical work for the ecosystem.

As a small team, we can’t replace all of the individual contributors that once worked for Voltron. Nevertheless, our small team is having an outsized impact on the throughput of issues in the Arrow project. One small example where this is clear:

## Source: https://github.com/arrow-maintenance/arrowdash/tree/main/data/cache

This post is an account of what the Arctos Alliance has done. It is also an honest account of where things stand: the community is healthier than it was, but it is fragile, and it depends on a very small number of people. If you build on Arrow (and if you are reading this, there’s a reasonable chance that you do) that is something worth understanding.

### Technical progress

The most concrete measure of a project's health is whether it is keeping pace with the hardware and workloads it serves. To that end, the Arctos Alliance is helping Arrow keep pace with some extremely important technical improvements:

#### Float16 support

Work is underway to add native float16 (half-precision floating point) support to the C++ implementation. Half-precision is the lingua franca of inference at scale. It cuts memory footprint roughly in half compared to float32, which matters enormously when moving tensors through pipelines that touch Arrow at either end. Active work is in progress to enable hardware-accelerated float16 operations and to support half-float tensors in equality comparisons, allowing movement of model weights and activations without leaving the Arrow ecosystem, closing a gap that anyone doing serious ML work will appreciate.

Relevant examples: [1] HalfFloatBuilder accepting Float16 [2] Parquet float16 logical type

#### Vector types

Work is progressing on proper vector type support. It’s still in progress, but the direction is clear. Anyone working with GPU-accelerated analytics or embedding-heavy workloads needs a way to represent high-dimensional vectors natively in Arrow without workarounds. This work will make Arrow users first-class citizens in that world.

Relevant examples: [1] Variable shape tensor umbrella issue [2] VariableShapeTensor implementation [3] Apache Arrow tensor arrays: an approach for storing tensor data (FOSDEM 2025)

#### Parquet encryption

Parquet Modular Encryption — the spec-defined mechanism for encrypting individual columns and footers — had long been missing from the Rust implementation. Arctos Alliance led a sustained effort to build it out end-to-end in arrow-rs, covering write support, plaintext footer handling, multi-threaded writing, and key management. Arctos contributors also drove a series of encryption fixes and improvements in the C++ implementation across multiple Arrow releases.

Relevant examples: [1] Content-Defined Chunking PR [2] FIXED_SIZE_LIST logical type [3] Flatbuf schema PR [4] Encryption improvements in C++ [5] Modular encryption support in Rust [6] Multi-threaded encrypted Parquet writing in Rust [7] State of Parquet 2025: Structure, Optimizations, and Recent Innovations (PyData Paris)

#### Modular C++ compute kernels

Many compute kernels were moved from the integrated compute module into a separate, optional C++ library, improving distribution size for users who don't need the full compute functionality and improving the overall modularity of the C++ library. This matters for anyone embedding Arrow in constrained environments or packaging it for distribution.

Relevant examples: [1] [C++] Move non-core compute kernels into separate shared library

#### PyArrow type annotations

A comprehensive type annotation effort for PyArrow began at EuroPython 2025 sprints and has grown into a substantial body of work covering core data structures, the compute module, filesystems, I/O, IPC, Parquet, and Flight. This lowers the barrier to entry for Python developers and improves IDE support across the board — the kind of quality-of-life improvement that compounds over time as more teams adopt Arrow in Python-heavy stacks.

Relevant examples: [1] Type checking support [2] A new home for pyarrow-stubs? [3] Sharing is caring: Efficient Data Exchange with pyarrow (EuroPython 2025)

### Turning the tide on open issues

One of the less glamorous but more consequential things Arctos Alliance has done over the past year is to reverse a trend that was quietly eroding contributor trust: the runaway growth of unresolved issues.

Ten years of uninterrupted growth in open issues Source: https://github.com/arrow-maintenance/arrowdash/tree/main/data/cache

A year ago, the open issue count was climbing, with no obvious ceiling. Left unchecked, that kind of backlog creates a slow-motion crisis: users and contributors submit bugs and hear nothing, maintainers get overwhelmed triaging rather than building, and the project develops a reputation for being unresponsive. Nic Crane ( thisisnic ) led a sustained effort to work through stale issues and surface ones that had been overlooked or forgotten:

The Arctos Alliance inflection point: peak 4,335, now under 2,400. Source: https://github.com/arrow-maintenance/arrowdash/tree/main/data/cache

The Arrow Maintainer Dashboard now shows the open issue count under 2,400 — a reduction of almost 2000 open issues and rolling back the clock to 2022 numbers. That is not just cosmetic. It reflects a genuine change in the project's health and the community's ability to make headway on the actual technical challenges ahead. Despite the obvious improvement, 2,400 issues remain to be assessed and addressed, and only sustained pressure will get through the backlog. This is precisely the kind of work the Arctos Alliance exists to do, and precisely why continued support matters.

### Preserving good engineering through transition

When Voltron Data wound down its operations in 2025, the Arrow community faced a real risk of losing engineering work that had no clear home. Among the assets at risk was a suite of benchmarking infrastructure that the project depends on, for tracking performance across commits and flagging regressions before they ship.

Rok Mihevc ( rok ) led the migration of this infrastructure to an Arrow-managed AWS account. Arctos Alliance now hosts the full benchmarking stack — including arrow-benchmarks-ci , arrowbench , and the benchmarks repository — as well as other essential developer tooling like Crossbow (the task automation system for Arrow's release and CI pipeline), Ursabot , substrait-fiddle , and GPU build infrastructure. Benchmark results, as well as the live Crossbow dashboard, are now published to conbench.arrow-dev.org .

This kind of continuity work rarely gets celebrated despite its importance. The alternative would have set the community back materially, and the tooling is now in stable, community-controlled hands.

### Arctos Alliance's role in the numbers

The sustainability analysis gives a more granular view of where Arctos’s contribution actually sits. Two metrics are worth understanding together.
- The Contributor Absence Factor (CAF) , a standard CHAOSS metric, measures the concentration of PR authorship: specifically, the minimum number of contributors whose absence would remove 50% of all merged PRs in a given quarter. For Apache Arrow, that number is currently 5, down from 11 before Voltron Data's dissolution. Arctos contributors account for 1-3 of those 5 people in any given quarter.
- There is an equally important and less-discussed metric on the merge side. Let’s call it the Merger Absence Factor (MAF) the minimum number of people whose absence would remove 50% of all merge decisions in a quarter. This is the gatekeeping function. You can have a thousand contributors opening PRs, but if the mergers aren't there, nothing ships. Arctos contributors account for 3-5 of the people responsible for half of all merges in any given quarter. That share fluctuates, but it has been consistent.

The data also shows that the CAF fell from 11 to 5 following Voltron Data's closure. This was not because the project got less healthy, but because a significant number of contributors employed full-time to work on Arrow no longer had that mandate. The total contributor pool fell from 94 (Q2 2024) to 59 (Q1 2026). The people who remain are genuinely committed, but they’re stretched thin. Any further attrition in the top tier would have an outsized impact on both review capacity and release velocity.

The analysis concludes plainly: the project would benefit from additional maintainer time, whether through sponsorship or dedicated engineering support from organizations depending on Arrow. That’s the gap Arctos Alliance was formed to address, and represents the bulk of the case we’re making to the organizations whose infrastructure runs on Arrow every day.

### What this adds up to

Arctos Alliance is not a governance body in the bureaucratic sense. It’s a group of people who care about Arrow remaining excellent and have organized to make that happen, by shipping meaningful technical improvements, by maintaining the project's operational health, and by building the kind of community that can weather disruption without losing momentum.

The sustainability data clearly shows the risks, just as the technical record highlights just how much has been accomplished. Both point in the same direction: Arrow is healthy, the stewardship is working, and sustained support — from the organizations that depend on this infrastructure — is what will keep it that way.

If you depend on Apache Arrow — and if you are reading this, there is a reasonable chance that you do — know that Artcos Alliance is the group making sure it maintains that dependability. We would welcome a conversation about how your organization can be part of that: you can reach us at info [at] arctosalliance [dot] org. Alternatively, you can reach us here on OpenCollective.

Arctos Alliance repositories are at github.com/arctosalliance . The Apache Arrow 2025 community highlights are published on the Arrow blog .
