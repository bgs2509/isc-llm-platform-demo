---
title: "Measuring the Value of Open Source, Part One: Coming Up With Some Numbers"
url: "https://insightsoftmax.com/blog/measuring-the-value-of-open-source-part-one-coming-up-with-some-numbers"
author: "Alex Scammon"
date: "2024-04-24"
kind: "sections"
---

# Measuring the Value of Open Source, Part One: Coming Up With Some Numbers

A recent paper from HBS has been making waves in the OSS community for once again trying to assess the true financial value of Open Source Software. The tl;dr is that OSS is worth several trillion dollars. Profit!

Whether you believe in the exact methodology posed in this paper (and we’ve had a lot of discussion about this point in the FOSS Funders discussion group), it’s certain that OSS is an incredibly valuable commodity. The question is how to take that fact and apply it practically within our organizations. Many of the companies that we work with (and for) take the value of OSS seriously, but it’s a challenge to convert that into dollars spent on OSS itself.

One of the places where this presents a challenge is getting funds to establish an Open Source Program Office (OSPO). Often, an OSPO is positioned primarily as a vehicle for philanthropy, marketing, or policy work. While companies recognize that supporting the broader open source ecosystem is important, these types of OSPOs are usually seen as cost centers and will be at the mercy of the financial vicissitudes of the business. This framing makes it easy to put Open Source programs on the chopping block when times are tough.

To combat this, we believe the OSPO needs to be positioned differently: as a value generator rather than a cost center. Through this lens, one of the OSPO’s primary functions becomes demonstrating how their work is not only mission-critical, but also revenue-positive and aligned with the financial bottom line of the larger organization.

Once that baseline understanding of value is established throughout the organization, almost paradoxically, much more philanthropic work can get done. How best, then, to demonstrate the actual dollar value of the OSPO to the organization? In this series of blog posts, we’ll discuss how we’ve built a 40-person OSPO. To start, we’ll talk about how we calculate the value of the OSS team. In Part 2, we’ll talk about how we communicate that value, and in Part 3, we’ll outline the non-financial benefits of contributing to OSS.

## The Spectrum of Tangibility

Like the authors of the HBS paper, we admit up front that we don’t know whether this is the right methodology or what the correct methodology is. We do know, however, that we have to have some methodology to make the value of OSS tangible for our company.

Here’s a chart we created to demonstrate the “spectrum of tangibility” we’re laying out in this article:

### More Tangible

One easy way of showing hard numbers is to illustrate how the OSPO can pare down expenses. For example: The company was previously spending a lot of money on a proprietary software license – and, by extension, expensive support contracts – but the OSPO has eliminated all those overhead costs by moving to an equivalent Open Source project. The general concept is:
- A former proprietary software license cost = W dollars/year
- The engineering effort required to migrate to OSS = Y cost to migrate
- W dollars of cost savings over X years – Y cost to migrate = Z dollars in total savings

To give a practical example, we used a proprietary compilation tool that cost us $500k/year. However, they weren’t updating their software – even though we paid this princely sum. Instead, we identified an OSS project that was nearly feature-complete compared to the proprietary software.

To bridge the feature gap, we reached out to the developer of the OSS tool and offered him a contract to fill in the missing features. We paid between $200-300k to bring the OSS tool to feature parity (in addition to the $500k we were still paying for the proprietary tool).

Once we were done with that work, we then incurred some amount of internal engineering time to migrate to the OSS tool. Roughly, over the course of the first year, the full cost of the project looked like:

$500k (final year of proprietary license to cover overlap) + $250k (OSS tool feature parity) + $400k (internal migration path)

$1.15M (total year one cost)

While the cost for this process was a lot more than a year’s worth of the proprietary tool itself, by year two, the cost was essentially zero. And by the end of year three, we were ahead of the game, spending less than the $1.5M we would have spent if we had stuck with the proprietary tool that refused to provide support.

Profit, loss, overhead, and savings are all very tangible numbers. In this case, the main drivers of success were the very real cost savings we were already able to make in year two, along with the improved profits by year three. Whenever we have a win like this, we’re very intentional about making it known, because these are the wins that are the easiest to communicate.

### Less Tangible / Fuzzier

#### Unlocked Capabilities and Improved Features

Now we get into areas which require some slightly fuzzier math.

Let’s take our example from before. Even though we got very direct, tangible numbers from this project, it also gave us some indirect benefits:
- The OSS tool unlocked the ability to use our new (and very expensive) farm of A100 GPUs. Because the proprietary tool was not being updated, it had been blocking our utilization of millions of dollars of our own hardware.
- Even better, we got to continue adding features to the OSS tool that made it even faster and more effective than the original proprietary tool.

Both of these are bonus items in the “fuzzy math” category. While they aren’t as easy to measure, the relative value of these two contributions is potentially in the millions or tens of millions of dollars. How do you value being able to effectively use millions of dollars worth of gear for the first time? We don’t know the exact answer, but we know that it’s significant.

To get at this number, we worked with Finance to measure the relative value of the workloads being run on those A100 GPUs, and took a small percentage of that number and claimed it as a financial benefit. Invariably, even if the percentage is small, this number looks big compared to the amount of investment we made (especially since this cost has already been covered by the more tangible example above!).

#### Developer Productivity

Developer productivity is another intangible, yet important, benefit of OSS programs.

Let’s say we’re able to solve some terrible build problem caused by an out-of-date component in an OSS dependency that’s being used widely throughout the company. By contributing to that OSS project, the OSPO is able to fix that broken component and speed up the builds by an hour across all the engineering teams. Here’s the math, starting with how many builds per week the teams are running:
- The engineers run 500 builds per week between their local and CI environments
- The company-sponsored OSS fix saves 15 minutes per build
- The average developer costs $125/hr with all associated costs
- So the cost savings calculation is: 125 saved hours/week x $125/hour = ~$810K/year in developer productivity

Because it’s hard to be sure of these numbers, we recommend being conservative. Cut the estimation by two-thirds, and the number drops to approximately $270K. That’s how we think about calculating the dollar value of an initiative like that.

The important thing here isn’t to get an exact number, but to have the conversation with the stakeholders and to point out that this is, at the very least, a non-zero contribution, and likely much more than that.

The other important thing to note is that this is just for a single fix – there may be many of these throughout a year’s worth of work. It’s easy to see how even the most conservative estimation of these improvements can add up to serious dollar values in a short amount of time.

### Least Tangible / Fuzziest

#### Reducing Opportunity Costs

For many companies, OSPOs confer even more benefits, like reducing opportunity costs.

Here’s an example: improving time to market is a high-value KPI for many companies. Aside from making money faster due to launching earlier, an early-mover advantage can capture additional revenue as a result of being in a less-crowded market.

Here are two ways that concept is represented as value:
- By spending X resources contributing to Y OSS project, we speed up the needed feature development by Z months
- By launching A initiative B months earlier, the company makes $C that much sooner

#### Marketing

Likewise, companies can earn recognition and broadcast their message by sponsoring projects and contributing to the OSS community at large. It’s difficult to assess the positive impact that doing public OSS work has on a company’s brand, but being able to market through a willing community is clearly a greater-than-zero benefit. This is why so many fledgling startups choose to be Open Core products: the benefit they derive from the community amplifying their message is one of the things that helps get them attention in the early days. Again, to assess the value for your company, this is very much a “fuzzy” conversation between your Marketing department and your Finance department. But it’s an important conversation to have nonetheless.

#### Talent Retention and Recruiting

Finally, on the extremely blurry end of the tangibility spectrum, lie the conversations about talent retention and recruiting. Again, you mainly want to make the point that this is a non-zero number. To do that, you can add up:
- How much money the talent team spends to hire new people
- What the cost of attrition is
- The value of an improved ability to hire based on the work the company has been doing out in the public

From there, you can do some math to come up with some conservative number that represents improved retention. Much like with marketing, this is a discussion to have with HR and Finance.

### Adding It All Up

The important thing, as you’re doing this exercise, is to make sure that all of these aspects have some dollar value attributed to them. Ideally, the total value will be more than the actual cost of the OSS team. In our experience, the value that we bring is many multiples of the cost of our 40-person team.

Crucially, it’s up to you to force the conversations with Engineering, Marketing, HR, and Finance to make them consider the value that OSS is bringing to the company. They won’t do it by themselves. If you’re struggling with these dynamics in your organization, we’d love to help, so drop us a line .
