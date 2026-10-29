---
title: "Case study: How we helped a nuclear fusion startup speed up their simulations by 2.5x and save $MMs in compute costs"
url: "https://insightsoftmax.com/blog/case-study-how-we-helped-a-nuclear-fusion-startup-speed-up-their-simulations-by-2.5x-and-save-$MMs-in-compute-costs"
author: "Tommy Aldo Sonin"
date: "2024-11-14"
kind: "plain"
---

# Case study: How we helped a nuclear fusion startup speed up their simulations by 2.5x and save $MMs in compute costs

A nuclear fusion startup came to us with three business problems.

The first problem was with their software configuration. Their core ideas were solid, but they didn’t have the specialists on their team to configure their complex hardware, software, and orchestration stack to leverage all the advantages high-performance computing (HPC) could offer.

The second problem was time. The simulations were simply taking too long to run, leading to delays in the progress of their core mission.

The third problem was cost. They were spending too much to run their computational fluid dynamics (CFD) simulations. If their spending continued at this rate, they would need to take on more funding sooner than anticipated.

In the end, we were able to significantly speed up their simulation run times while also making them less expensive to run. If you want to learn how we achieved this, keep reading.

To start, we needed to roll up our sleeves and help them compile their software to leverage their hardware’s low-latency, high-bandwidth networking. That alone led to a drastic improvement in the computational performance in the system.

Then it was time to gather data. We asked them for a representative workload of their CFD simulations and ran two series of benchmarks.

We ran the first benchmark on the c5.18xlarge instance type, which they were using already. For the second benchmark, we used instance type hpc6a.48xlarge, as we thought it would fit their use case better.

Over a couple of days of testing, we discovered that our recommended instance type materially improved the run times of their simulations. To make our comparisons as direct as possible, we tested workloads with the same number of nodes and tasks on both instance types. When we scaled up to two nodes, we saw a 50% improvement in the runtime of the simulation. We improved on that further by adding more nodes.

As the number of nodes and tasks scaled, we were no longer able to make exact comparisons due to the relative number of available tasks per node scaling differently between instance types. While we couldn’t make exact comparisons, the numbers certainly pointed to an improvement if we switched instance types. In the end, we changed instance types and chose two nodes at 96 tasks per node, and our customer has reported a ~2.5x speed improvement.

The final piece of the puzzle is cost. The instance types that we recommended were about 5% cheaper than the instance types the customer was running. When we extrapolated the performance improvements and cost savings over time — given the amount of simulation this customer is planning over the next 3-4 years — we estimate a cost savings of several million dollars with just this simple change.

Are your simulations taking too long or costing too much? Do you need help configuring your software, hardware, and orchestration to fully leverage your HPC spend? We’re happy to review your data to identify improvements that will save you time, money, and headache. Just drop us a line and we’ll schedule a time to chat.
