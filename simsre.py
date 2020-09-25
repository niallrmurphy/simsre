#!/usr/local/bin/python3

# SimSRE, a tool to investigate how different work structures for SRE
# might affect outcomes for an SRE team or teams.

# The basic idea is that we model an SRE team as a state machine (via
# discrete event simulation) which has work assigned, processes work,
# and different types of work have different effects.

# There are a large number of improvements to be made:
# 1. Should fully utilise the actual event-oriented approach of simpy,
# rather than the half-way house I do here
# 2. Should fully simulate multiple teams; the approach here makes
# that tricky to do. (Particularly important to do for cross-team work.)
# 3. In the future "policy" such as whether onboardings add one operational
# work or two or whatever, should be easily swappable out objects, so we
# we can test the effects of changing more easily.

# You'll need to do the equivalent of pip3 install mplot3d matplotlib
# to get this to work.

from mpl_toolkits.mplot3d import Axes3D

import collections
import numpy
import matplotlib.pyplot as plt
import pprint
import random
import simpy

# Enums, via stack overflow.
def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    reverse = dict((value, key) for key, value in enums.items())
    enums['reverse_mapping'] = reverse
    return type('Enum', (), enums)

# Constants
# The Treynor "hard cap" on operational work, not more than 50%.
HARD_CAP_OPEX = 0.5
# How many "clock ticks" the simulation goes for.
SIM_DURATION = 100
# How much operational growth happens, per clock tick, which is used
# as an analogue for much our existing units of operatational work should
# be multiplied by.
QUARTERLY_GROWTH = 1.15
# The different work types that an SRE team can have.
# Operational: e.g. cell moves, cluster turnups, totally operational and necessary,
# but not relevant outside of the team (and it goes up as a function of the systems
# that a team has onboarded.)
# In team project: a siloized project, basically just some work that again makes
# something within the team easier, that's it.
# Cross team project: right now, for simplifying reasons, this overloads _two_ things:
# the team itself working on cross-team work, and also receiving the benefits of someone
# else's cross-team projects.
# Onboarding: an onboarding adds some additional work to the stack, and also changes
# the base level of operational level.
SRE_WORK_TYPES = enum(OPERATIONAL=1, IN_TEAM_PROJECT=2, CROSS_TEAM_PROJECT=3, ONBOARDING=4)
# The number of work units an SRE team can process in a clock-tick.
SRE_TEAM_CAPACITY = 10
# The maximum number of onboardings an SRE team can do.
SRE_TEAM_ONBOARDINGS_LIMIT = 10
# The baseline operational work; again a simplifying constant for the multiplications re:
# onboardings.
SRE_BASELINE_OPERATIONAL = 1
# The cap on operational work available to be assigned.
SRE_TEAM_MAX_OPERATIONAL = 20
# The default distribution of work, for a team starting from scratch.
SRE_WORK_DISTRIBUTION = [SRE_WORK_TYPES.OPERATIONAL,
                         SRE_WORK_TYPES.OPERATIONAL,
                         SRE_WORK_TYPES.OPERATIONAL,
                         SRE_WORK_TYPES.OPERATIONAL,
                         SRE_WORK_TYPES.IN_TEAM_PROJECT,
                         SRE_WORK_TYPES.IN_TEAM_PROJECT,
                         SRE_WORK_TYPES.IN_TEAM_PROJECT,
                         SRE_WORK_TYPES.IN_TEAM_PROJECT,
                         SRE_WORK_TYPES.CROSS_TEAM_PROJECT,
                         SRE_WORK_TYPES.CROSS_TEAM_PROJECT]

class SRE_work_item(object):
  """A very thin wrapper around enums to represent work types."""
  def __init__(self, work_type=None):
    if work_type is None:
      self.work_type = work_type

class SRE_team(object):
  """Class simulating an SRE team.

  env: simpy environment object."""
  def __init__(self, env):
    self.env = env
    # Our internal way of tracking the work assigned for us to potentially do.
    # Double-ended because I want to pop from one end and push onto the other.
    self.work_items = collections.deque()
    # Instantiate me as a process.
    self.action = env.process(self.run(env))
    # A guard to prevent simultaneous onboardings.
    self.onboarding_in_progress = False
    # Number of total onboardings we've done.
    self.onboardings = 0
    # Multiplication hack.
    self.operational_work = SRE_BASELINE_OPERATIONAL
    # How long the sim has gone on for (I believe you can get this from
    # the simpy env object, but I was on a plane and couldn't look it up)
    self.ticks = 0
    # The history of what assignments were made (i.e. put into the work queue).
    self.assigned_history_dict = collections.defaultdict(list)
    # The history of what work was performed
    self.performed_history_dict = collections.defaultdict(list)
    # Per-cycle tracking
    self.tracking = collections.defaultdict(int)

  def run(self, env):
    """Run the simulation with this SRE team object."""
    print("considering work")
    while True:
      self.ticks += 1
      # If I have no work items, assign a default distribution...
      if len(self.work_items) == 0:
        print("assigning work; default distribution")
        self.work_items = collections.deque(SRE_WORK_DISTRIBUTION[:])
      else:
        # Otherwise take a census of what work was done (during
        # which some useful housekeeping is tracked), and assign/process work.
        self.census(self.env)
        self.assign_work()
        self.process_work()
      # Return back to simulation.
      yield env.timeout(1)

  def add_work(self, work_type):
    """Add work of specifed type at the right end."""
    self.work_items.append(work_type)

  def assign_work(self):
    """Assign work to the SRE team.

    This should be in a policy object, but it's hard-coded for now."""
    # 10% chance of having a cross team project.
    if random.randint(1,10) > 9:
      print ("assigning cross team")
      self.add_work(SRE_WORK_TYPES.CROSS_TEAM_PROJECT)
      # This is a hacky representation of a cross-team project
      # solving other problems... need to find a better way.
      # If we have a cross team, remove two operationals and an
      # in-team. Other possibilities exist.
      self.clear_first_of_type(SRE_WORK_TYPES.OPERATIONAL)
      self.clear_first_of_type(SRE_WORK_TYPES.OPERATIONAL)
      self.clear_first_of_type(SRE_WORK_TYPES.IN_TEAM_PROJECT)
    # 20% chance of an onboarding per tick, but only do it if we're
    # not already doing one and are below our max.
    if (random.randint(1,10) > 8 and self.onboarding_in_progress is False
        and self.onboardings < SRE_TEAM_ONBOARDINGS_LIMIT):
      print ("assigning onboarding")
      self.onboarding_in_progress = True
      self.onboardings += 1
      self.add_work(SRE_WORK_TYPES.ONBOARDING)
    # Unconditionally: scale up our operational work as a proportion of
    # onboarded systems and "quarterly" growth.
    self.add_scaled_operational()
    print ("post assigned work: len", len(self.work_items))
    print ("onboardings: ", self.onboardings)

  def process_work(self):
    """Process the work we have in our local queue."""
    # State variables to allow us to implement things like a limit on
    # operational work.
    op_counter = 0
    capacity = 0
    self.tracking.clear()
    # Process what work we have up to our allowed limit, potentially
    # avoiding doing some kinds.
    while capacity < SRE_TEAM_CAPACITY:
      # Pop work items from the left, push onto the right
      try:
        work_item = self.work_items.popleft()
        if work_item is SRE_WORK_TYPES.IN_TEAM_PROJECT:
          print ("found in team project")
          self.work_items.append(work_item)
          self.tracking[SRE_WORK_TYPES.IN_TEAM_PROJECT] += 1
          capacity += 1
        elif (work_item is SRE_WORK_TYPES.OPERATIONAL) and (op_counter < 0.5 * SRE_TEAM_CAPACITY):
          print ("found operational")
          op_counter += 1
          capacity += 1
          self.tracking[SRE_WORK_TYPES.OPERATIONAL] += 1
        elif (work_item is SRE_WORK_TYPES.OPERATIONAL) and (op_counter >= 0.5 * SRE_TEAM_CAPACITY):
          print ("passing on operational work because over threshold")
          pass
        elif work_item is SRE_WORK_TYPES.CROSS_TEAM_PROJECT:
          print ("found cross team project")
          # "policy": 50% chance that cross team work will give you more cross team work,
          # e.g. that there's project run-over
          if random.randint(1,10) > 5:
            self.add_work(SRE_WORK_TYPES.CROSS_TEAM_PROJECT)
          capacity += 1
          self.tracking[SRE_WORK_TYPES.CROSS_TEAM_PROJECT] += 1
        elif work_item is SRE_WORK_TYPES.ONBOARDING:
          # "policy" -- an onboarding gives you a siloed project and
          # an operational work.
          self.add_work(SRE_WORK_TYPES.IN_TEAM_PROJECT)
          self.add_work(SRE_WORK_TYPES.OPERATIONAL)
          self.onboarding_in_progress = False
          capacity += 2
          self.tracking[SRE_WORK_TYPES.CROSS_TEAM_PROJECT] += 1
      except IndexError:
        print ("Hmm, work_items is empty.")
        break
    print ("post process work: assignable")
    print (collections.Counter(self.work_items).most_common())
    print ("post process work: performed")
    print (collections.Counter(self.tracking).most_common())

  def add_default_operational(self):
    """Default method I think no longer use."""
    for x in range(4):
      self.add_work(SRE_WORK_TYPES.OPERATIONAL)

  def add_scaled_operational(self):
    """Scale the operational work in our queue by some function of growth."""
    new_operational_work = int(round(self.operational_work * QUARTERLY_GROWTH) + self.onboardings)
    delta = new_operational_work - self.operational_work
    if self.operational_work < SRE_TEAM_MAX_OPERATIONAL:
      for x in range(delta):
        self.add_work(SRE_WORK_TYPES.OPERATIONAL)

  def census(self, env, printing=False):
    """Display the work that's been done, and record the history of it."""
    print ("census -- %s work items" % len(self.work_items))
    unused_work_types = [1, 2, 3, 4]
    if printing:
      print ("assignable work")
      print (collections.Counter(self.work_items).most_common())
    if printing:
      print ("performed work")
      print (self.tracking)
    for k, v in collections.Counter(self.work_items).most_common():
      self.assigned_history_dict[k].append(v)
      if k in unused_work_types:
        unused_work_types.remove(k)
    # We end up with a complete history of what work types were assigned,
    # including ones that were 0.
    for work_type in unused_work_types:
      self.assigned_history_dict[work_type].append(0)
    # Now do again for performed work
    unused_work_types = [1, 2, 3, 4]
    for k, v in collections.Counter(self.tracking).most_common():
      self.performed_history_dict[k].append(v)
      if k in unused_work_types:
        unused_work_types.remove(k)
    # We end up with a complete history of what work types were assigned,
    # including ones that were 0.
    for work_type in unused_work_types:
      self.performed_history_dict[work_type].append(0)


  def clear_first_of_type(self, supplied_type):
    """Look through work queue and remove the first of the specified type."""
    try:
      self.work_items.remove(supplied_type)
    except ValueError:
      return 0

  def sum_total_work(self):
    """Sum the total work done (unused right now)."""
    sums = []
    for x in range(1, self.ticks):
      sums.append(self.assigned_history_dict[1][x] +
                  self.assigned_history_dict[2][x] +
                  self.assigned_history_dict[3][x] +
                  self.assigned_history_dict[4][x])
    return sums

def twod_graphing_setup(title, op, in_team, cross_team, onboarding):
  # The x locations for the groups
  ind = numpy.arange(sre_team.ticks)
  # the width of the bars: can also be len(x) sequence
  width = 0.35
  # Plot colours
  p1 = plt.bar(ind, op, width, color='green')
  p2 = plt.bar(ind, in_team, width, bottom=op, color='blue')
  p3 = plt.bar(ind, cross_team, width, bottom=in_team, color='red')
  p4 = plt.bar(ind, onboarding, width, bottom=cross_team, color='yellow')
  # Legend, etc
  plt.ylabel('Work graphing, SRE')
  plt.title(title)
  plt.legend( (p1[0], p2[0], p3[0], p4[0]), ('Operational', 'In-team', 'Cross-team', 'Onboarding') )
  # Display
  plt.show()

env = simpy.Environment()
sre_team = SRE_team(env)
env.run(until=SIM_DURATION)
sre_team.census(env, printing=True)

twod_graphing_setup("Work available for doing",
                    sre_team.assigned_history_dict[SRE_WORK_TYPES.OPERATIONAL],
                    sre_team.assigned_history_dict[SRE_WORK_TYPES.IN_TEAM_PROJECT],
                    sre_team.assigned_history_dict[SRE_WORK_TYPES.CROSS_TEAM_PROJECT],
                    sre_team.assigned_history_dict[SRE_WORK_TYPES.ONBOARDING])


twod_graphing_setup("Work actually performed",
                    sre_team.performed_history_dict[SRE_WORK_TYPES.OPERATIONAL],
                    sre_team.performed_history_dict[SRE_WORK_TYPES.IN_TEAM_PROJECT],
                    sre_team.performed_history_dict[SRE_WORK_TYPES.CROSS_TEAM_PROJECT],
                    sre_team.performed_history_dict[SRE_WORK_TYPES.ONBOARDING])
