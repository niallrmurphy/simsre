SimSRE is a tool to investigate how different work structures or practices for an SRE team might affect work outcomes.

The basic idea is that we model an SRE team as a state machine (via discrete event simulation). This state machine, together with a bunch of assumptions about what operational work, system onboarding, project work, etc, actually mean, is used to run a simulation of a number of teams for a fixed number of steps. At the end of that, we display graphically what kind of work mix the team(s) have. Originally, this was used to support the intuition that in the steady state of an SRE team, it's a really commmon outcome that they are generally overwhelmed with operational work and purely in-team technical work *unless* a sufficient amount of cross-team project work is done (which in this naively positive view of the world, helps all other SRE teams). 

There are a large number of improvements to be made:
 1. Should fully utilise the actual event-oriented approach of simpy, rather than the half-way house I do here
 2. Should fully simulate multiple teams; the approach here makes that tricky to do. (Particularly important to do for modelling cross-team work correctly.)
 3. In the future "policy" such as whether onboardings add one operational work or two or whatever, should be easily swappable out objects, so we can test the effects of changing more easily.

You'll need to do the equivalent of ``pip3 install mplot3d matplotlib`` to get this to work.
