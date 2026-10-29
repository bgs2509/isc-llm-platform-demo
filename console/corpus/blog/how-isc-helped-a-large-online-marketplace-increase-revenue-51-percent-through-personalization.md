---
title: "How ISC Helped a Large Online Marketplace Increase Revenue by 51% Through Personalization"
url: "https://insightsoftmax.com/blog/how-isc-helped-a-large-online-marketplace-increase-revenue-51-percent-through-personalization"
author: "Hollis Nolan"
date: "2023-06-13"
kind: "sections"
---

# How ISC Helped a Large Online Marketplace Increase Revenue by 51% Through Personalization

Personalization — treating each customer as an individual vs. one of the masses — is a trend that’s been catching steam for several years now. A big part of that is developing a recommendation engine that makes relevant, useful suggestions.

The companies who do it well are winning big and setting the standard for everyone else. In fact, good recommendations have become so standard that customers not only expect it, they expect it to be good. Here’s a look at how ISC helped a large online marketplace gain a 65% increase in clicks, a 39% higher purchase rate, and 51% more revenue.

Creative Market sells high-quality fonts, graphic design elements, stock photography, and anything else a creative needs to bring her visions to life. With millions of products in their inventory, a smart recommendation engine was a daunting goal.

The company had set an annual goal to provide customers with better personalization. Their search team reached out to Insight Softmax to help them build a recommendation engine to serve every customer the products most relevant to them.

That might be easy when you sell within a narrow niche. But how do you optimize when you’re dealing with constantly changing factors like user-item sparsity, seasonality, item categorization and tagging, and a wide variety of user behavior? Even a slight parameter change in the wrong direction can send your results flying out of control.

#### The ISC Approach

The first step to a successful data science partnership in this case didn’t begin with numbers – it started with words. An in-depth conversation between ISC and Creative Market leadership uncovered a wealth of important information: the current state of their available data, what they’d like that data to do, and their overall goals for personalization. This early collaboration put us on the right path from day one.

From there, we dug into their data to create a detailed report, focused on what customers viewed while browsing vs. what they eventually ended up buying. This allowed us to suss out trends and patterns in the data. What we uncovered was a true "aha!" moment: Creative Market customers' purchases followed themes (swirly fonts and glitter backgrounds, for example), after which that customer disappeared and didn't interact with the site for several months. When they returned to the site months later, the themes of both their views and purchases were completely different (metal-edge backgrounds and skulls).

A fundamental assumption for recommendation engines is that user preferences don’t change drastically over time. When we looked into these particular customers, they shattered this assumption, adding another layer of complexity to our process. The conclusion: Designers weren’t shopping for themselves. They were shopping for their clients. In other words, their personal preferences had no bearing on what they purchased. That means their multi-year purchase history was not actually useful for recommending relevant products.

#### Collaborative Filtering and Pre-Processing

The recommendation engine we built for Creative Market uses collaborative filtering. At the most basic level, this is like using crowdsourcing to determine if a given user will like a certain product. It constructs a giant table where:
- Each user gets a row
- Each product gets a column
- All the space in the table is filled with zeroes
- Every actual purchase is represented with a 1 in its corresponding user-item spot
- A mathematical algorithm is run to fill in all the empty zeroes
- Every user-product combination then contains a tiny decimal number
- Those numbers are ranked per user
- The highest-scoring unpurchased item is the one the user is most likely to purchase next
- The score is based on an analysis of an aggregated list of items that all users have ever purchased

Pre-processing is a crucial step in every data science project. It can sometimes be even more effective at improving final model accuracy/success than the algorithm tuning step. In this case, the initial report showed us that user preferences change quite a bit over time. In fact, sometimes they change completely!

To work around this reality of the data, we had to transform it in some way. We couldn’t blame the users. We had to adapt to them. The crucial question became, "At what time did user preferences change?" Another way of phasing it would be, "how long did it take an inactive user (in days) before they changed their preferences?"

To explore this, we borrowed from the world of audio signal processing and looked at windowing functions. A simplistic explanation of windowing functions goes something like this:
- A window opens when a user makes their first purchase and closes when they stop for n days
- Once the window closes, all the data gathered inside that window becomes a pseudo-user
- This continues until the user’s complete purchase history is accounted for
- Only the most recent window represents the actual user; the rest are stored as pseudo-users
- That user’s recommendations are only based on the most recent purchase

For quality results, we also added filtering into the pipeline. Scenarios in which a human would have a gut instinct equivalent to "that doesn’t make sense" were captured as code, automated, and excluded. Example excluded products included:
- Free products (that had no cost and were very popular among all users)
- Seasonal products (that were only wanted at one time of year)
- Less-popular categories (that didn’t have enough data to meaningfully contribute)
- 3D meshes of products (that were almost never purchased alongside graphic design items)
- Extremely popular products (the “banana problem”)
- Extremely unpopular products (with so few purchases they made the pipeline slower, without adding any value)

Removing these items from the pre-processing pipeline focused the collaborative filtering on the most relevant data needed to achieve Creative Market’s annual goal: treating their customers as individuals.

The Results

Together we conducted a series of A/B tests to find the optimal results, and landed on a set of hyper-parameters that yielded the following results:
- Click rate: Up 65%
- Purchase rate: Up 39%
- Revenue: Up 51%

Our tests also revealed some valuable data that will help us in our next steps moving forward.

If you’d like to explore how you can unlock the transformative value of your company’s data, drop us a line .
