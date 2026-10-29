---
title: "Case Study: Cloud HPC cost optimization tools for a mid-sized quantitative trading firm"
url: "https://insightsoftmax.com/blog/case-study-cloud-hpc-cost-optimization-tools-for-a-mid-sized-quantitative-trading-firm"
author: "Tommy Aldo Sonin"
date: "2025-11-21"
kind: "case"
---

# Case Study: Cloud HPC cost optimization tools for a mid-sized quantitative trading firm

## Challenge

The customer lacked in-house HPC specialists needed to build batch tooling around their systems. They suffered cost overruns on their cloud workloads due to an inability to estimate compute costs before running a job. Because they were migrating from a purely on-premise HPC environment into the AWS cloud, their culture around resource utilization needed to be updated to reflect the widely variable cost structures of HPC in the cloud.

## Solution
- Built Slurm tooling, integrated with AWS ParallelCluster, to enable cost estimation before a job is approved for execution
- Built a self-service tool, integrated with AWS's Cost API, for in-house users to calculate compute estimates in real time
- Built an optional secondary approval feature

## Results
- The customer's in-house researchers are now able to estimate job costs using real time AWS data to accurately work within budgets
- Outsourcing the engineering solutions decreased workload and stress on the internal engineering team

The customer is saving money by not running jobs that will overflow their budget. Having reliable cost controls has allowed them to more fully and confidently achieve cloud adoption.
