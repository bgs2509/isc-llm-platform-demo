---
title: "Ethics, bias, and fairness in AI"
url: "https://insightsoftmax.com/blog/ethics-bias-and-fairness-in-ai"
author: "Damian Sol"
date: "2024-03-02"
kind: "plain"
---

# Ethics, bias, and fairness in AI

It’s impossible to watch the news or scroll social media lately without hearing about AI, often citing its dangers. Like any powerful tool, it has the potential to do harm. You could end up harming people (and your own business) if you don’t design your AI solution with this in mind. Here I’ll give you a high-level overview of three essential focus areas to help you utilize the power of AI in a safe way.

Principles for Human-centric design for AI (AI ethics):
- Understand people’s pain points and needs in order to better define the problem
- Ask if AI adds value to any potential solution
- Consider the potential harms that the AI system could cause
- When prototyping, start with non-AI solutions and make sure that people from diverse backgrounds are included in the process
- Provide ways for people to challenge the system
- Build in safety measures

Bias in AI (six examples):
- Historical bias (occurs when the state of the world in which the data was generated is flawed)
- Representation bias (occurs when building datasets for training a model, if those datasets poorly represent the people that the model will serve)
- Measurement bias (occurs when the accuracy of the data varies across groups. This can happen when working with proxy variables)
- Aggregation bias (occurs when groups are inappropriately combined)
- Evaluation bias (occurs when evaluating a model, if the benchmark data does not represent the population that the model will serve)
- Deployment bias (occurs when the problem the model is intended to solve is different from the way it is actually used)

AI Fairness (four examples):
- Demographic parity / statistical parity (the composition of people who are selected by the model matches the group membership percentages of the applicants)
- Equal opportunity (the proportion of people in each group who should be selected by the model are actually selected by the model)
- Equal accuracy (the percentage of correct classifications should be the same for each group)
- Group unaware / “Fairness through unawareness” (removes all group membership information from the dataset)

We hope this list gives you a better understanding of how you can design these powerful AI tools with ethics, bias, and fairness in mind. We want to thank Hult International School for Business for inviting our COO Marcus Rabe to teach another installment of his course, Computational Analytics with Python, at their Boston campus over January and February.
