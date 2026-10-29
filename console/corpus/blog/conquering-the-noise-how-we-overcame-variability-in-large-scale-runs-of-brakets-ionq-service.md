---
title: "Conquering the Noise: How We Overcame Variability in Large-Scale Runs of Braket’s IonQ Service"
url: "https://insightsoftmax.com/blog/conquering-the-noise-how-we-overcame-variability-in-large-scale-runs-of-brakets-ionq-service"
author: "Hollis Nolan & Tommy Aldo Sonin"
date: "2022-11-03"
kind: "sections"
---

# Conquering the Noise: How We Overcame Variability in Large-Scale Runs of Braket’s IonQ Service

We’re making great strides in quantum computing, but it’s important to remember the end goal: turning our theoretical research into real-world solutions for business applications. As problem-solvers, that’s our focus at Insight Softmax – addressing real business needs, such as more efficient usage of our energy grid, improved supply-chain efficiency or, as is the case here, trying to extract meaningful results from one of today’s quantum machines.

#### The challenge

Quantum computing is noisy, and notoriously unstable because of it. Interference from any outside source, from WiFi signals to cosmic rays, can cause a fatal error in as little as a thousandth of a second. And if it’s coming from a disturbance in the Earth’s magnetic field, well, that’s not something you can turn off for a minute.

Noise is unpredictable and can vary widely over time, making it a huge challenge to solve. But if we’re working toward an ultimate goal – moving from idea to execution – the first step is being able to anticipate and control it.

In an ideal world, we’d have diagnostic information at your fingertips immediately after every execution, or a model for how to think about the noise, or an estimation on when the batches are actually going to execute. Failing those things, however, we need a way to deal with the noise and variability that we’ll encounter.

#### The question

How do we achieve the best possible performance when operating a system that’s designed to simulate highly complex quantum circuits through even more complex networks? The answer is knowledge: accurate, all-inclusive and extensive.

Through our work with the IonQ machine, we’ve found that a lack of control over when and how our circuits were being executed makes it difficult to figure out what the results are telling us. When we run a large number of circuits (more than 40-50), for example, they get placed into different batch runs and executed over the course of the day. As it stands, we have no way of knowing or influencing the order in which this happens.

If the results from batch to batch were relatively consistent, interpreting the outcomes wouldn’t present such a challenge. And while our results were reasonably grouped within a single batch, they were inconsistent when comparing one batch to another.

As a next step, we devised an experiment to act as a “litmus test” for assessing the consistency (or lack thereof) of noise across a batch of circuits. With success, this test could then help us inform a decision about whether or not we can trust that a “payload” batch of circuits will experience a consistent noise profile.

If the noise profile turns out to be consistent across a batch, the litmus test should tell us a little bit about that noise so that we can account for its influence on the payload circuits.

#### The experiment

We designed a simple quantum circuit on two qubits to determine how noise would propagate through that circuit if the noise profile were consistent. Specifically, we chose a quantum circuit consisting of six CNOT gates, then decomposed it into 24 other circuits. If all 24 circuits were subject to the same (or very similar) noise processes, the data obtained by executing such a batch should look a particular way. If the noise profile was not consistent across the batch, we would be able to detect that inconsistency by identifying outliers in the data.

A CNOT gate (short for “Controlled NOT”) modifies the state of one qubit (the “target”) based on the state of another qubit (the “control”). If the control qubit is in the state |1〉, a bit flip (or “NOT”) operation should be performed on the target qubit. Conversely, if the control qubit is in the state |0〉, nothing should be done to the target qubit. The litmus circuit is then a sequence of six CNOT gates that alternates the choice of control and target qubit.

If there were no noise in the litmus circuit, the input data should exactly match the output data. But it’s important to note that this is not true for any less than six CNOT gates. Even if a particular input (00, for example) should be returned unchanged at the output (as is always true of 00), there are other inputs which would not be returned unchanged. So, we decomposed our litmus circuit into 24 other circuits as follows: for each of the four possible inputs (00, 01, 10, 11) execute each of six possible subcircuits (1 CNOT, 2 CNOTs, 3 CNOTs, 4 CNOTs, 5 CNOTs, 6 CNOTs) for a total of 6x4=24 circuits. This is the batch we want to deliver to the quantum computer.

Once the experiment was finished, we processed the data from this circuit batch to look for two things. First, we estimated the average probability of error per CNOT gate by calculating the average probability of error across all 24 circuits in the batch. Second, we calculated the variance of the errors and checked to see if it exceeded a tolerance value.

If the variance exceeds tolerance, we can determine that the noise profile has failed to demonstrate the consistency we need to execute the payload batch, and we can save our clients money by terminating the quantum computer execution then and there.

#### The findings

We now have data that shows results from about 500 executions of the same circuit that were all scheduled at the same time but executed throughout the day in subsequent batches. An unpredictable number of circuits are executed in what appears to be a sequential fashion; we call these "execution windows."

In the initial analysis, we discovered that the noise profile can shift drastically from one execution window to the next, and it also seems to drift over time. (Although, that drift seems to be at a level we can manage.)

#### What’s next?

The next step in the process is understanding how to incorporate this litmus test into the routine execution of quantum circuit batches. If the batches are experiencing a consistent noise profile, for example, we could then add random circuits from the original batch of 24 to establish trust in the noise profile consistency. At completion, we could then use these litmus tests to compare all of the batches and adjust for the drift between them.

We think that this approach could be useful for others who are considering executing large numbers of circuits on IonQ hardware. These findings, which did allow us to compare batch-to-batch in a more meaningful way, have been well-received by IonQ, and we appreciate their time and input. As we progress, we hope to not only use this information ourselves, but share more about our findings regarding IonQ’s hardware.

Further interest could lead to a more comprehensive protocol in conjunction with experimental data from multiple hardware vendors who are willing to allow for dedicated execution windows.

If you’re struggling with the same kind of issues, drop us a line . We’d love to chat and see if we can work together.
