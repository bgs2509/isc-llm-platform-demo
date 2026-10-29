---
title: "HPC in Underserved Regions: The Longest Last Mile"
url: "https://insightsoftmax.com/blog/hpc-in-underserved-regions-the-longest-last-mile"
author: "Alex Scammon"
date: "2024-02-29"
kind: "case"
---

# HPC in Underserved Regions: The Longest Last Mile

Prior to the last Supercomputing23 conference in Denver, there was a pre-conference workshop called NRG@SC23, put on by Elizabeth Leake ( STEM-Trek ) and Bryan Johnston ( Center for High-Performance Computing, South Africa ) with support from Google, the US National Science Foundation, SC23 General Chair, VAST Data, AWS, and Airlink Airlines. The point of the pre-conference workshop (their fifth) was to bring together a diverse group of researchers from underserved regions to discuss the challenges of running large-scale HPC clusters with limited resources.

#### Challenge #1: Power

The immediate challenge for those attempting to run large-scale HPC clusters in developing countries is the issue of power. What was less obvious until this conference: the impact of trying to run an HPC center in any of these countries. What do you do when your power is routinely turned off for two hours a day during scheduled “load-shedding,” or an unplanned days-long outage when major infrastructure fails? You can run diesel generators or other backup power, but there’s still a distinct danger that you could run out of backup power.

All of this has major implications on how a research organization treats its systems and how it chooses to manage workloads. There are some workarounds, though none are ideal:
- Only drawing a certain amount of power on the days where there is less available
- Making sure that boot-up times are as fast as possible in the event of a power outage (I suppose this is actually a positive thing, if you have the time to invest)
- Performing more routine maintenance because the machines are being powered on and off more often

#### Challenge #2: Bandwidth and throughput

The second challenge we learned about at NRG@SC23 is one of network bandwidth and throughput. When you’re doing large HPC problems and you’re trying to download large data sets from other countries, this becomes a real problem. There was a very good overview given by Vasilka Chergarova (the AmLight program at Florida International University ) about how all of these intercontinental links are managed. Seeing the physical reality of how our Internet world is connected is eye-opening. Similar to the issue of reliable electrical power, we in the developed world are so fortunate to live in a world of robust and reliable networking. For the most part, in the US, we get to work on HPC clusters that are up all the time. In fact, in many major cities, our homes have as much bandwidth as some of these research institutions, sometimes much more.

#### Challenge #3: Training

Beyond the fairly obvious difficulties with power and networking, many HPC operators in developing countries lack the training needed to fully utilize the equipment that they have. There have been many programs over the years that donated aging HPC gear to developing countries. This is great in principle, but having the gear doesn’t mean an operator has the proper training in how to handle it or know what to do with it. Processes that institutions in richer countries have automated long ago are still run manually in developing countries, because that’s what they know. When, for example, they want to add another person to the system, they actually go onto the command line and add them directly, which is what we in the developed world did 20 years ago. Despite its appearance as an out-of-date practice, this actually might be the best option given the difference in circumstances. Many research institutions in the developed world have moved to infrastructure as code, adding users automatically through the systems of scale we’ve built over the years. All of that makes sense if you have thousands of users of your system. But if you don’t — and in many of these developing nations, there’s a very select group of people who are using those systems — this seemingly outdated procedure might very well be the most expedient and correct for their situation.

There are real benefits to working at scale. Without the ability to support larger-scale access to the needed equipment, the scaled-up context will also be missing. There are procedures and training that are only necessary given a larger scale, and certainly opportunities that are unavailable at a smaller scale. The question of scale presents a chicken-and-egg problem: If an institution is not doing it to scale right now, will they be able to scale and provide the service for more people? Maybe not. And then more people won’t be able to work on those systems and drive the kind of scaling-motivated responses that they might need in the future. The problems of scale are needed in order to also aggregate the benefits that come from operating at scale.

#### Challenge #4: Funding

Throughout the talks at NRG@SC23, the most common thread was lack of funding. This is, of course, not a controversial problem to believe that developing nations have. But it goes deeper than simply funding the equipment and infrastructure needed to support larger-scale HPC systems. Sure, the gear has been donated from richer countries, and to some degree, these are cast-offs and secondhand pieces of gear. Beyond that, though, the researchers themselves are generally underpaid compared to their peers in western countries. There’s a huge problem of brain drain: as operators get good at using these systems, they often get hired by countries or companies who will pay them less than what they would be paid in that country, but much more than in their home country.

Developing nations often can’t compete with those salary expectations, and therefore they’re in a real bind. How do they keep those people there, fund them, and fund the gear needed to do the research? If they could get the right gear and pay the people who now know how to work on these systems, maybe they could develop technology that would bring more wealth and prosperity to their country. But they’re constantly falling behind and they need either an infusion of technology or money, or both. There are no easy answers to this, of course. But it’s clear that funding is a driving force behind how difficult it is for these countries to achieve what’s needed in the HPC world.

#### A potential solution

One of the most interesting projects proposed by Elizabeth Leake and Kurt Keville (MIT) is a consortium of companies and researchers working to package HPC gear in a form factor that can be delivered to developing nations relatively cheaply. They call it “Isango,” which is the Zulu word for gateway. The small cluster will help bring HPC to distant corners of the globe, as well as facilitate cloud-bursting. This composable, portable and affordable package can be powered much more easily than in a traditional data center. The hope is that through Isango, they can address some of the concerns around funding and power issues, giving these developing nations and underserved institutions the ability to do meaningful research.

The overarching question infusing the workshop, and one that Elizabeth and Kurt seek to answer, is: How do we provide enough HPC resources for people to learn, and for operators to get the context of large-scale systems? It seems that so much of the HPC hardware community is focused on buying heavy compute footprints for huge installations. If that hardware — and the software run on it — was 1000x more efficient, we could fill the workforce pipeline with talent from places that can’t support large-scale HPC.

All in all, the STEM-Trek 23 pre-conference workshop was an eye-opening experience with a real wealth of diversity in the participants. If you’re interested in the problem of compute in developing nations and want to learn more about STEM-Trek, you can visit their website here and connect with Elizabeth and Kurt on LinkedIn.
