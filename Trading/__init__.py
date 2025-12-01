# type: ignore # my linter is Pyright/Pylance and it's flaggin correct otree code as errors, so I'm ignoring it

from otree.api import *
import time
import random
from operator import itemgetter

doc = """Continuous double auction market"""

class C(BaseConstants):
    NAME_IN_URL = 'sCDA'
    # TODO: TESTING - Change back to 6 after testing!
    PLAYERS_PER_GROUP = 6  # Production group size
    num_trial_rounds = 1
    NUM_ROUNDS = 7  ## incl. trial periods
    base_payment = cu(1.81)  # Base payment for all participants who complete survey
    bonus_payment = cu(1.81)  # Additional payment for highest score increase winner
    FV_MIN = 30
    FV_MAX = 85
    num_assets_MIN = 10
    num_assets_MAX = 10
    cash_MIN_heterogeneous = 5
    cash_homogeneous = 25  # Fixed cash endowment for homogeneous groups
    decimals = 2
    marketTime = 210  # needed to initialize variables but exchanged by session_config
    supply_shock_intensity = 1  # 0.8 = 20% reduction, 1.0 = no shock, 0.5 = 50% reduction
    
    # Carbon credit destruction constants
    CO2_PER_CREDIT = 1.0  # kg CO2 per carbon credit
    KM_PER_KG_CO2 = 7.0   # km driven by car per kg CO2 (approximate)
    
    # Good definitions
    # Good A (oatmilk): money price 3, carbon price 1
    # Good B (cowmilk): money price 2, carbon price 3
    GOOD_A_MONEY_PRICE = 3
    GOOD_A_CARBON_PRICE = 1
    GOOD_B_MONEY_PRICE = 2
    GOOD_B_CARBON_PRICE = 3
    
    # Satisfaction points (constant marginal utility)
    # Conventional preference: prefers cowmilk (Good B) - higher carbon, lower price
    SATISFACTION_CONVENTIONAL_GOOD_A = 6   # oatmilk satisfaction for conventional
    SATISFACTION_CONVENTIONAL_GOOD_B = 12  # cowmilk satisfaction for conventional
    # Eco preference: prefers oatmilk (Good A) - lower carbon, higher price
    SATISFACTION_ECO_GOOD_A = 12  # oatmilk satisfaction for eco
    SATISFACTION_ECO_GOOD_B = 6   # cowmilk satisfaction for eco
    
    # Treatment definitions
    TREATMENTS = [
        'baseline_homogeneous', 
        'baseline_heterogeneous', 
        'environmental_homogeneous', 
        'environmental_heterogeneous', 
        'destruction_homogeneous', 
        'destruction_heterogeneous'
    ]
    ACTIVE_TREATMENTS = [
        'baseline_homogeneous', 
    ]  # Can be modified to test specific treatments


class Subsession(BaseSubsession):
    offerID = models.IntegerField(initial=0)
    orderID = models.IntegerField(initial=0)
    transactionID = models.IntegerField(initial=0)

    def creating_session(self):
        # Groups will be created in TreatmentAssignment WaitPage when all players arrive
        pass
def vars_for_admin_report(subsession):
    # this function defines the values sent to the admin report page
    groups = subsession.get_groups()
    period = subsession.round_number
    payoffs = sorted([p.payoff for p in subsession.get_players()])
    market_times = sorted([g.marketTime for g in groups])
    highcharts_series = []
    trades = [{'x': tx.transactionTime, 'y': tx.price, 'name': 'Trades'} for tx in Transaction.filter() if tx.Period == period and tx.group in groups]
    highcharts_series.append({'name': 'Trades', 'data': trades, 'type': 'scatter', 'id': 'trades', 'marker': {'symbol': 'circle'}})
    bids = [{'x': bx.BATime, 'y': bx.bestBid, 'name': 'Bids'} for bx in BidAsks.filter() if bx.Period == period and bx.BATime and bx.bestBid]
    highcharts_series.append({'name': 'Bids', 'data': bids, 'type': 'line', 'id': 'bids', 'lineWidth': 2})
    asks = [{'x': ax.BATime, 'y': ax.bestAsk, 'name': 'Asks'} for ax in BidAsks.filter() if ax.Period == period and ax.BATime and ax.bestAsk]
    highcharts_series.append({'name': 'Asks', 'data': asks, 'type': 'line', 'id': 'bids', 'lineWidth': 2})
    return dict(
        marketTimes=market_times,
        payoffs=payoffs,
        series=highcharts_series,
    )


class Group(BaseGroup):
    marketTime = models.FloatField(initial=C.marketTime)
    marketStartTime = models.FloatField()
    marketEndTime = models.FloatField()
    randomisedTypes = models.BooleanField()
    numAssets = models.IntegerField(initial=0)
    numParticipants = models.IntegerField(initial=0)
    numActiveParticipants = models.IntegerField(initial=0)
    assetNames = models.LongStringField()
    aggAssetsValue = models.FloatField()
    assetValue = models.FloatField()
    # Treatment fields
    treatment = models.StringField(initial="")
    framing = models.StringField(initial="")  # 'baseline', 'environmental', 'destruction'
    endowment_type = models.StringField(initial="")  # 'homogeneous', 'heterogeneous'
    gini_coefficient = models.FloatField(initial=0, decimal=4)  # Gini coefficient for cash inequality (only for heterogeneous groups)
    group_size = models.IntegerField(initial=0)  # Final group size after regrouping (for data analysis)
    bestAsk = models.FloatField()
    bestBid = models.FloatField()
    transactions = models.IntegerField(initial=0, min=0)
    marketBuyOrders = models.IntegerField(initial=0, min=0)
    marketSellOrders = models.IntegerField(initial=0, min=0)
    transactedVolume = models.IntegerField(initial=0, min=0)
    marketBuyVolume = models.IntegerField(initial=0, min=0)
    marketSellVolume = models.IntegerField(initial=0, min=0)
    limitOrders = models.IntegerField(initial=0, min=0)
    limitBuyOrders = models.IntegerField(initial=0, min=0)
    limitSellOrders = models.IntegerField(initial=0, min=0)
    limitVolume = models.IntegerField(initial=0, min=0)
    limitBuyVolume = models.IntegerField(initial=0, min=0)
    limitSellVolume = models.IntegerField(initial=0, min=0)
    cancellations = models.IntegerField(initial=0, min=0)
    cancelledVolume = models.IntegerField(initial=0, min=0)


def random_types(group: Group):
    # this code is run at the first WaitToStart page when all participants arrived
    # this function returns a binary variable to the group table whether roles should be randomised between periods.
    return group.session.config['randomise_types']


def assign_types(group: Group):
    # this code is run at the first WaitToStart page, within the initiate_group() function, when all participants arrived
    # this function allocates traders' types at the beginning of the session or when randomised.
    # when observers are set to 0, all participants are traders
    players = group.get_players()
    if group.randomisedTypes or Subsession.round_number == 1:
        ii = group.numParticipants  # number of traders without type yet
        role_structure = {'observer': 0, 'trader': ii}
        for r in ['observer', 'trader']:  # for each role
            k = 0  # number of players assigned this role
            max_k = role_structure[r]  # number of players to be assigned with this role
            while k < max_k and ii > 0:  # until enough role 'r' types are assigned
                rand_num = round(random.uniform(a=0, b=1) * ii, 0)
                i = 0
                for p in players:
                    if p.isParticipating and i < rand_num and not p.field_maybe_none('roleID'):
                        i += 1
                        if rand_num == i:
                            ii -= 1
                            p.roleID = str(r)
                            p.participant.vars['roleID'] = str(r)
                            k += 1
                    if not p.isParticipating and not p.field_maybe_none('roleID'):
                        p.roleID = str('not participating')
                        p.participant.vars['roleID'] = str('not participating')
    else:
        for p in players:
            p.roleID = p.participant.vars['roleID']


def define_asset_value(group: Group):
    # this code is run at the first WaitToStart page, within the initiate_group() function, when all participants arrived
    # this function determines the BBV and shares the information to the players table.
    asset_value = round(random.uniform(a=C.FV_MIN, b=C.FV_MAX), C.decimals)
    group.assetValue = asset_value


def count_participants(group: Group):
    # this code is run at the first WaitToStart page, within the initiate_group() function, when all participants arrived
    # this function determines the number of actual participants.
    if group.round_number == 1:
        # Reset numParticipants before counting (it might have been set earlier)
        group.numParticipants = 0
        try:
            players = group.get_players()
            for p in players:
                if p.isParticipating == 1:
                    group.numParticipants += 1
        except Exception as e:
            raise
    else:  # since player.isParticipating is not newly assign with a value by a click or a timeout, I take the value from the previous round
        for p in group.get_players():
            pr = p.in_round(group.round_number - 1)
            p.isParticipating = pr.isParticipating
        group.numParticipants = group.session.vars['numParticipants']
    group.session.vars['numParticipants'] = group.numParticipants


def initiate_group(group: Group):
    # this code is run at the first WaitToStart page when all participants arrived
    # this function starts substantial calculations on group level.
    try:
        count_participants(group=group)
        define_asset_value(group=group)
        assign_types(group=group)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise


def get_max_time(group: Group):
    # this code is run at the WaitingMarket page just before the market page when all participants arrived
    # this function returns the duration time of a market.
    return group.session.config['market_time']  # currently the binary value is retrieved from the config variables


def persistent_timeout(player: 'Player', page_name: str, default_seconds: float) -> float:
    """
    Create a server-side deadline the first time the player reaches a page in a given round.
    Subsequent visits (via browser back button, refresh, etc.) use the same deadline so the
    remaining time can only decrease.
    """
    key = f'timeout_deadline_{page_name}_round_{player.round_number}'
    deadlines = player.participant.vars.setdefault('page_deadlines', {})
    now = time.time()
    deadline = deadlines.get(key)

    if deadline is None:
        deadline = now + default_seconds
        deadlines[key] = deadline

    remaining = deadline - now

    if remaining < 0:
        return 0
    return remaining


class Player(BasePlayer):
    isParticipating = models.BooleanField(choices=((True, 'active'), (False, 'inactive')), initial=0)  ## describes whether this participant is participating in this round, i.e., whether they pressed the 'next' button.
    isObserver = models.BooleanField(choices=((True, 'active'), (False, 'inactive')), initial=0)  ## describes a participant role as active trader or observer
    roleID = models.StringField()
    allowShort = models.BooleanField(initial=True)
    allowLong = models.BooleanField(initial=True)
    assetValue = models.FloatField()
    initialCash = models.FloatField(initial=0, decimal=C.decimals)
    initialAssets = models.IntegerField(initial=0)
    initialEndowment = models.FloatField(initial=0, decimal=C.decimals)
    cashHolding = models.FloatField(initial=0, decimal=C.decimals)
    assetsHolding = models.IntegerField(initial=0)
    endEndowment = models.FloatField(initial=0, decimal=C.decimals)
    # Treatment fields
    treatment = models.StringField(initial="")
    framing = models.StringField(initial="")
    endowment_type = models.StringField(initial="")
    good_preference = models.StringField(initial="")  # 'conventional' prefers cowmilk (Good B), 'eco' prefers oatmilk (Good A)
    unused_assets_endofround = models.IntegerField(initial=0)  # Track unused assets at end of round for all treatments
    capLong = models.FloatField(initial=0, min=0, decimal=C.decimals)
    capShort = models.IntegerField(initial=0, min=0)
    transactions = models.IntegerField(initial=0, min=0)
    marketOrders = models.IntegerField(initial=0, min=0)
    marketBuyOrders = models.IntegerField(initial=0, min=0)
    marketSellOrders = models.IntegerField(initial=0, min=0)
    transactedVolume = models.IntegerField(initial=0, min=0)
    marketOrderVolume = models.IntegerField(initial=0, min=0)
    marketBuyVolume = models.IntegerField(initial=0, min=0)
    marketSellVolume = models.IntegerField(initial=0, min=0)
    limitOrders = models.IntegerField(initial=0, min=0)
    limitBuyOrders = models.IntegerField(initial=0, min=0)
    limitSellOrders = models.IntegerField(initial=0, min=0)
    limitVolume = models.IntegerField(initial=0, min=0)
    limitBuyVolume = models.IntegerField(initial=0, min=0)
    limitSellVolume = models.IntegerField(initial=0, min=0)
    limitOrderTransactions = models.IntegerField(initial=0, min=0)
    limitBuyOrderTransactions = models.IntegerField(initial=0, min=0)
    limitSellOrderTransactions = models.IntegerField(initial=0, min=0)
    limitVolumeTransacted = models.IntegerField(initial=0, min=0)
    limitBuyVolumeTransacted = models.IntegerField(initial=0, min=0)
    limitSellVolumeTransacted = models.IntegerField(initial=0, min=0)
    cancellations = models.IntegerField(initial=0, min=0)
    cancelledVolume = models.IntegerField(initial=0, min=0)
    cashOffered = models.FloatField(initial=0, min=0, decimal=C.decimals)
    assetsOffered = models.IntegerField(initial=0, min=0)
    tradingProfit = models.FloatField(initial=0) # this does not make too much sense with the utility from goods anymore --> change to abosolute utility change
    wealthChange = models.FloatField(initial=0) # change this to relative utility change 
    finalPayoff = models.CurrencyField(initial=0)
    selectedRound = models.IntegerField(initial=1)
    isWinner = models.BooleanField(initial=False)  # True if player won the bonus (highest Score Change in selected round)
    goodA_qty = models.IntegerField(initial=0)
    goodB_qty = models.IntegerField(initial=0)
    goodA_utility_table = models.StringField()
    goodB_utility_table = models.StringField()
    goods_utility = models.FloatField(initial=0)
    overall_utility = models.FloatField(initial=0)
    utilityChangePercent = models.FloatField(initial=0) # utility change as percentage
    consent = models.BooleanField(choices=((True, 'I consent'), (False, 'I do not consent')), initial=False)
    
    # Comprehension check questions
    comp_q1 = models.StringField(choices=[
        ('a', 'a. My Total Score increases from 0 to 35'),
        ('b', 'b. My Total Score increases from 50 to 85'),
        ('c', 'c. My Total Score increases from 50 to 65')
    ], widget=widgets.RadioSelect, label="")
    
    comp_q2 = models.StringField(choices=[
        ('a', 'a. My Total Score decreases from 40 to 30'),
        ('b', 'b. My Total Score decreases from 30 to 20'),
        ('c', 'c. My Total Score does not change')
    ], widget=widgets.RadioSelect, label="")
    
    comp_q3 = models.StringField(choices=[
        ('a', 'a. They directly affect the Total Score'),
        ('b', 'b. They do not directly affect the Total Score, but they can increase the money holdings when they are bought'),
        ('c', 'c. They do not directly affect the Total Score, but they can increase the money holdings when sold and can increase satisfaction points from goods when used to purchase goods')
    ], widget=widgets.RadioSelect, label="")
    
    comp_q4 = models.StringField(choices=[
        ('a', 'a. Correct'),
        ('b', 'b. Incorrect')
    ], widget=widgets.RadioSelect, label="")
    
    comp_q5 = models.StringField(choices=[
        ('a', 'a. I will receive the bonus of €1.81 if I have the highest Score Change in my group in any of the trading rounds'),
        ('b', 'b. I will receive the base payout of €1.81 even if I do not complete the survey at the end'),
        ('c', 'c. All participants who complete the full study receive €1.81, and the player with highest Score Change in her group in the randomly selected round gets an additional €1.81')
    ], widget=widgets.RadioSelect, label="")
    
    comp_q6 = models.StringField(choices=[
        ('a', 'a. Correct. For each unused carbon credit in the experiment, 1 kg of CO₂ will be compensated through reforestation projects in Germany, helping to reduce real-world carbon emissions.'),
        ('b', 'b. Incorrect. Unused carbon credits in the experiment have no effect on real-world emissions')
    ], widget=widgets.RadioSelect, label="", blank=True)
    
    # Comprehension check performance tracking
    comp_correct_count = models.IntegerField(initial=0)  # Number of correct answers (0-5 or 0-6 for destruction group)
    comp_passed = models.BooleanField(initial=False)     # True if all questions correct
    comp_attempts = models.IntegerField(initial=0)       # Number of attempts needed to pass comprehension check
    
    # Survey Demographics
    age = models.IntegerField(choices=[(i, str(i)) for i in range(18, 101)], initial=0, label="")
    gender = models.StringField(choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say')
    ], widget=widgets.RadioSelect, label="")
    education = models.StringField(choices=[
        ('no_degree', 'No degree (yet)'),
        ('middle_school', 'Middle school'),
        ('high_school', 'High school'),
        ('vocational_training', 'Vocational training or apprenticeship'),
        ('bachelor', 'Bachelor\'s degree'),
        ('master', 'Master\'s degree (e.g., Diploma, State Exam)'),
        ('doctorate', 'Doctorate (PhD) or higher'),
        ('other', 'Other degree')
    ], widget=widgets.RadioSelect, label="")
    income = models.IntegerField(choices=[
        (1, 'Under 200 €'),
        (2, '200 € to under 300 €'),
        (3, '300 € to under 400 €'),
        (4, '400 € to under 500 €'),
        (5, '500 € to under 625 €'),
        (6, '625 € to under 750 €'),
        (7, '750 € to under 875 €'),
        (8, '875 € to under 1000 €'),
        (9, '1000 € to under 1125 €'),
        (10, '1125 € to under 1250 €'),
        (11, '1250 € to under 1375 €'),
        (12, '1375 € to under 1500 €'),
        (13, '1500 € to under 1750 €'),
        (14, '1750 € to under 2000 €'),
        (15, '2000 € to under 2250 €'),
        (16, '2250 € to under 2500 €'),
        (17, '2500 € to under 2750 €'),
        (18, '2750 € to under 3000 €'),
        (19, '3000 € to under 4000 €'),
        (20, '4000 € to under 5000 €'),
        (21, '5000 € to under 7500 €'),
        (22, '7500 € and more'),
        (23, 'Prefer not to say')
    ], initial=0, label="")
    employment = models.StringField(choices=[
        ('employed_full_time', 'Employed full-time'),
        ('employed_part_time', 'Employed part-time'),
        ('self_employed', 'Self-employed / Freelance'),
        ('student', 'Student'),
        ('unemployed', 'Unemployed'),
        ('retired', 'Retired'),
        ('stay_at_home_parent', 'Stay-at-home parent'),
        ('other', 'Other')
    ], widget=widgets.RadioSelect, label="")
    # Survey Attitudes
    pct_effectiveness = models.IntegerField(choices=[
        (1, 'Strongly disagree'),
        (2, 'Disagree'),
        (3, 'Neither agree nor disagree'),
        (4, 'Agree'),
        (5, 'Strongly agree')
    ], widget=widgets.RadioSelect, initial=0, label="")
    pct_fairness = models.IntegerField(choices=[
        (1, 'Strongly disagree'),
        (2, 'Disagree'),
        (3, 'Neither agree nor disagree'),
        (4, 'Agree'),
        (5, 'Strongly agree')
    ], widget=widgets.RadioSelect, initial=0, label="")
    pct_support = models.IntegerField(choices=[
        (1, 'Strongly oppose'),
        (2, 'Oppose'),
        (3, 'Neither support nor oppose'),
        (4, 'Support'),
        (5, 'Strongly support')
    ], widget=widgets.RadioSelect, initial=0, label="")
    climate_concern = models.IntegerField(choices=[
        (1, 'Not at all concerned'),
        (2, 'Slightly concerned'),
        (3, 'Moderately concerned'),
        (4, 'Very concerned'),
        (5, 'Extremely concerned')
    ], widget=widgets.RadioSelect, initial=0, label="")
    climate_responsibility = models.IntegerField(choices=[
        (1, 'Strongly disagree'),
        (2, 'Disagree'),
        (3, 'Neither agree nor disagree'),
        (4, 'Agree'),
        (5, 'Strongly agree')
    ], widget=widgets.RadioSelect, initial=0, label="")
    
    # Trust question for destruction group only
    co2_certificate_trust = models.BooleanField(choices=[
        (True, 'Yes'),
        (False, 'No')
    ], widget=widgets.RadioSelect, initial=None, label="")


def asset_endowment(player: Player):
    # this code is run at the first WaitToStart page, within the initiate_player() function, when all participants arrived
    # this function returns a participant's initial asset endowment
    
    # Calculate the number of trading rounds
    num_trading_rounds = C.NUM_ROUNDS - C.num_trial_rounds
    shock_round = (num_trading_rounds // 2) + C.num_trial_rounds + 1
    
    # Apply supply shock: reduction after 50% of trading rounds
    if player.round_number >= shock_round:
        # Apply shock intensity (e.g., 0.8 = 20% reduction)
        base_endowment = int(random.uniform(a=C.num_assets_MIN, b=C.num_assets_MAX))
        return int(base_endowment * C.supply_shock_intensity)
    else:
        # 100% of original endowment (no reduction)
        return int(random.uniform(a=C.num_assets_MIN, b=C.num_assets_MAX))


def short_allowed(player: Player):
    # this code is run at the first WaitToStart page, within the initiate_player() function, when all participants arrived
    # this function returns a binary variable whether short selling is allowed
    group = player.group
    return group.session.config['short_selling']  # currently the binary value is retrieved from the config variables


def long_allowed(player: Player):
    # this code is run at the first WaitToStart page, within the initiate_player() function, when all participants arrived
    # this function returns a binary variable whether buying on margin is allowed
    group = player.group
    return group.session.config['margin_buying']  # currently the binary value is retrieved from the config variables


def asset_short_limit(player: Player):
    # this code is run at the first WaitToStart page, within the initiate_player() function, when all participants arrived
    # this function returns a participant's short selling limits if that is allowed
    if player.allowShort:
        return player.initialAssets  # currently the short selling limit is set equal to the asset endowment
    else:
        return 0


def calculate_gini_coefficient(values):
    """
    Calculate the Gini coefficient for a list of values.
    Gini coefficient measures inequality: 0 = perfect equality, 1 = maximum inequality.
    
    Uses the formula: G = (Σ Σ |x_i - x_j|) / (2 * n^2 * μ)
    Where μ is the mean of all values.
    
    Args:
        values: List of numerical values
    
    Returns:
        float: Gini coefficient (between 0 and 1)
    """
    if not values or len(values) == 0:
        return 0.0
    
    # Handle case where all values are the same (perfect equality)
    if len(set(values)) == 1:
        return 0.0
    
    n = len(values)
    total_sum = sum(values)
    
    if total_sum == 0:
        return 0.0
    
    mean = total_sum / n
    
    # Calculate sum of absolute differences between all pairs
    abs_diff_sum = 0
    for i in range(n):
        for j in range(n):
            abs_diff_sum += abs(values[i] - values[j])
    
    # Gini coefficient formula
    gini = abs_diff_sum / (2 * n * n * mean)
    
    # Ensure result is between 0 and 1 (should be, but safety check)
    return max(0.0, min(1.0, gini))


def distribute_heterogeneous_cash(group: Group):
    """
    Distributes cash across all players in a heterogeneous group such that:
    - Total cash equals cash_homogeneous * group_size exactly
    - Each player gets at least cash_MIN_heterogeneous
    - Cash is randomly distributed
    
    Returns a dictionary mapping player.id_in_group to their cash amount.
    """
    players = group.get_players()
    group_size = len(players)
    total_cash = C.cash_homogeneous * group_size
    cash_distribution = {}
    unrounded_amounts = []
    
    # Sort players by id_in_group to ensure consistent distribution
    sorted_players = sorted(players, key=lambda p: p.id_in_group)
    
    # First, calculate unrounded amounts for all players except the last
    remaining_cash_unrounded = total_cash
    for i, player in enumerate(sorted_players[:-1]):  # All except last
        remaining_players = group_size - i - 1
        # Minimum needed for remaining players (including last)
        min_for_others = C.cash_MIN_heterogeneous * remaining_players
        # Maximum available for this player
        max_for_this = remaining_cash_unrounded - min_for_others
        # Minimum for this player
        min_for_this = C.cash_MIN_heterogeneous
        
        # Ensure max >= min (safety check)
        if max_for_this < min_for_this:
            max_for_this = min_for_this
        
        # Randomly assign between min and max (unrounded)
        cash_amount_unrounded = random.uniform(a=min_for_this, b=max_for_this)
        unrounded_amounts.append((player.id_in_group, cash_amount_unrounded))
        remaining_cash_unrounded -= cash_amount_unrounded
    
    # Round all but the last player
    allocated_rounded = 0.0
    for player_id, unrounded in unrounded_amounts:
        rounded = float(round(unrounded, C.decimals))
        cash_distribution[player_id] = rounded
        allocated_rounded += rounded
    
    # Last player gets exactly the remaining cash (ensures exact total)
    last_player = sorted_players[-1]
    last_player_amount = total_cash - allocated_rounded
    
    # Ensure last player gets at least minimum (should always be true given our constraints)
    if last_player_amount < C.cash_MIN_heterogeneous:
        # This shouldn't happen, but if it does, we need to adjust
        # Take from the previous player(s) to ensure minimum
        shortage = C.cash_MIN_heterogeneous - last_player_amount
        if len(unrounded_amounts) > 0:
            # Adjust the last assigned player
            last_assigned_id = unrounded_amounts[-1][0]
            cash_distribution[last_assigned_id] = max(
                C.cash_MIN_heterogeneous,
                cash_distribution[last_assigned_id] - shortage
            )
            # Recalculate
            allocated_rounded = sum(cash_distribution.values())
            last_player_amount = total_cash - allocated_rounded
    
    cash_distribution[last_player.id_in_group] = float(round(last_player_amount, C.decimals))
    
    return cash_distribution


def cash_endowment(player: Player):
    # This function returns a participant's initial cash endowment based on their treatment
    # It is called in TreatmentAssignment (round 1) and the result is stored in participant.vars
    # Subsequent rounds copy the stored value from round 1
    group = player.group
    
    # Check if cash endowment was already calculated and stored
    if 'cash_endowment' in player.participant.vars:
        return player.participant.vars['cash_endowment']
    
    # Check if this is a heterogeneous treatment
    if group.endowment_type == 'heterogeneous':
        # For heterogeneous groups, we need to distribute cash at the group level
        # Check if distribution has already been done for this group
        players = group.get_players()
        distribution_done = any('cash_endowment' in p.participant.vars for p in players)
        
        if not distribution_done:
            # Distribute cash for the entire group
            cash_distribution = distribute_heterogeneous_cash(group=group)
            total_allocated = 0
            
            # Store the distribution results
            for p in players:
                cash_amount = cash_distribution[p.id_in_group]
                p.participant.vars['cash_endowment'] = cash_amount
                total_allocated += cash_amount
            
        
        # Return this player's cash endowment
        return player.participant.vars['cash_endowment']
    else:
        # For homogeneous: fixed amount from constant
        cash_amount = float(round(C.cash_homogeneous, C.decimals))
        player.participant.vars['cash_endowment'] = cash_amount
        return cash_amount  


def cash_long_limit(player: Player):
    # this code is run at the first WaitToStart page, within the initiate_player() function, when all participants arrived
    # this function returns a participant's buying on margin limits if that is allowed
    if player.allowLong:
        return player.initialCash  # currently the buying on margin limit is set equal to the cash endowment
    else:
        return 0


def assign_role_attr(player: Player, role_id):
    # this code is run at the first WaitToStart page, within the set_player() function, when all participants arrived
    # this function determines a participant's attributes in terms of being active or observer, and distributes information
    if role_id == 'observer':
        player.participant.vars['isObserver'] = True
    elif role_id == 'trader':
        player.participant.vars['isObserver'] = False


def initiate_player(player: Player):
    # this code is run at the first WaitToStart page when all participants arrived
    # this function starts substantial calculations on player level.
    group = player.group
    if not player.isObserver and player.isParticipating:
        # Retrieve cash endowment from participant.vars (set in TreatmentAssignment)
        initial_cash = player.participant.vars.get('cash_endowment', 0)
        player.initialCash = initial_cash
        player.cashHolding = initial_cash
        player.allowLong = long_allowed(player=player)
        player.capLong = cash_long_limit(player=player)
        initial_assets = asset_endowment(player=player)
        player.initialAssets = initial_assets
        group.numAssets += player.initialAssets
        player.assetsHolding = initial_assets
        player.allowShort = short_allowed(player=player)
        player.capShort = asset_short_limit(player=player)
        player.goodA_qty = 0
        player.goodB_qty = 0
        # Utility tables no longer used - we use constant marginal utility based on preference
        # Keep fields empty to avoid issues, but they're not used
        player.goodA_utility_table = ''
        player.goodB_utility_table = ''
        player.goods_utility = calculate_goods_utility(player)
        player.overall_utility = player.goods_utility + player.cashHolding

def set_player(player: Player):
    # this code is run at the first WaitToStart page when all participants arrived.
    # this function retrieves player characteristics from the participants table.
    assign_role_attr(player=player, role_id=player.field_maybe_none('roleID'))
    if player.isParticipating:
        player.isObserver = player.participant.vars['isObserver']

def get_good_money_price(good: str) -> int:
    """Get money price for a good from constants."""
    if good == 'A':
        return C.GOOD_A_MONEY_PRICE
    elif good == 'B':
        return C.GOOD_B_MONEY_PRICE
    else:
        raise ValueError(f"Invalid good: {good}")

def get_good_carbon_price(good: str) -> int:
    """Get carbon price for a good from constants."""
    if good == 'A':
        return C.GOOD_A_CARBON_PRICE
    elif good == 'B':
        return C.GOOD_B_CARBON_PRICE
    else:
        raise ValueError(f"Invalid good: {good}")

def get_good_satisfaction(good: str, preference: str) -> int:
    """Get satisfaction points for a good based on player preference."""
    if preference == 'conventional':
        if good == 'A':
            return C.SATISFACTION_CONVENTIONAL_GOOD_A
        elif good == 'B':
            return C.SATISFACTION_CONVENTIONAL_GOOD_B
    elif preference == 'eco':
        if good == 'A':
            return C.SATISFACTION_ECO_GOOD_A
        elif good == 'B':
            return C.SATISFACTION_ECO_GOOD_B
    else:
        raise ValueError(f"Invalid preference: {preference}")
    raise ValueError(f"Invalid good: {good}")

def calculate_goods_utility(player: Player):
    """
    Calculate total utility from goods based on player preference.
    Uses constants for satisfaction points.
    """
    total_utility = 0
    
    # Get player preference (default to 'conventional' if not set)
    # Use field_maybe_none() to safely handle None values
    preference = player.field_maybe_none('good_preference') or 'conventional'
    
    # Get satisfaction points from constants
    goodA_satisfaction = get_good_satisfaction('A', preference)
    goodB_satisfaction = get_good_satisfaction('B', preference)
    
    total_utility += player.goodA_qty * goodA_satisfaction
    total_utility += player.goodB_qty * goodB_satisfaction
    
    return total_utility

def live_method(player: Player, data):
    # this code is run at the market page whenever a participants updates the page or a new order is created.
    # this function receives orders and processes them, furthermore, it sends the new order book to participant.
    if not data or 'operationType' not in data:
        return
    key = data['operationType']
    highcharts_series = []
    group = player.group
    period = group.round_number
    players = group.get_players()
    if key == 'limit_order':
        limit_order(player, data)
    elif key == 'cancel_limit':
        cancel_limit(player, data)
    elif key == 'market_order':
        transaction(player, data)
    elif key == 'buy_good':
        result = buy_good(player, data)  # Get the result from buy_good
    offers = Limit.filter(group=group)
    transactions = Transaction.filter(group=group)
    if transactions:
        hc_data = [{'x': tx.transactionTime, 'y': tx.price, 'name': 'Trades'} for tx in Transaction.filter(group=group)]
        highcharts_series.append({'name': 'Trades', 'data': hc_data})
    else:
        highcharts_series = []
    best_bid = group.field_maybe_none('bestBid')
    best_ask = group.field_maybe_none('bestAsk')
    BidAsks.create(  # observe Bids and Asks of respective asset before the request
        group=group,
        Period=period,
        orderID=group.subsession.orderID,
        bestBid=best_bid,
        bestAsk=best_ask,
        BATime=round(float(time.time() - player.group.marketStartTime), C.decimals),
        timing='before',
        operationType=key,
    )
    bids = sorted([[offer.price, offer.remainingVolume, offer.offerID, offer.makerID] for offer in offers if offer.isActive and offer.isBid], reverse=True, key=itemgetter(0))
    asks = sorted([[offer.price, offer.remainingVolume, offer.offerID, offer.makerID] for offer in offers if offer.isActive and not offer.isBid], key=itemgetter(0))
    msgs = News.filter(group=group)
    if asks:
        best_ask = asks[0][0]
        group.bestAsk = best_ask
    else:
        best_ask = None
        group.bestAsk = None  # Clear the group field when no asks
    if bids:
        best_bid = bids[0][0]
        group.bestBid = best_bid
    else:
        best_bid = None
        group.bestBid = None  # Clear the group field when no bids
    BidAsks.create(  # observe Bids and Asks of respective asset after the request
        group=group,
        Period=period,
        orderID=group.subsession.orderID,
        bestBid=best_bid,
        bestAsk=best_ask,
        BATime=round(float(time.time() - player.group.marketStartTime), C.decimals),
        timing='after',
        operationType=key,
    )
    if key == 'market_start':
        players = [player]
    return {  # the next lines define the information send to participants
        p.id_in_group: dict(
            bids=bids,
            asks=asks,
            trades=sorted([[t.price, t.transactionVolume, t.transactionTime, t.sellerID] for t in transactions if (t.makerID == p.id_in_group or t.takerID == p.id_in_group)], reverse = True, key=itemgetter(2)),
            cashHolding=f"{p.cashHolding:.{C.decimals}f}",
            assetsHolding=p.assetsHolding,
            goodA_qty=p.goodA_qty,
            goodB_qty=p.goodB_qty,
            goods_utility=p.goods_utility,
            overall_utility=f"{p.overall_utility:.{C.decimals}f}",
            highcharts_series=highcharts_series,
            news=sorted([[m.msg, m.msgTime, m.playerID] for m in msgs if m.playerID == p.id_in_group], reverse=True, key=itemgetter(1)),
            # Add goods trade info if this player just made a purchase
            goods_trade_good=result.get('goods_trade_good') if key == 'buy_good' and p.id_in_group == player.id_in_group else None,
            goods_trade_qty=result.get('goods_trade_qty') if key == 'buy_good' and p.id_in_group == player.id_in_group else None,
            goods_trade_price=result.get('goods_trade_price') if key == 'buy_good' and p.id_in_group == player.id_in_group else None
        )
        for p in players
    }


def calc_period_profits(player: Player):
    # this code is run at the results wait page.
    # this function calculates the participant's Score Change percentage for the round.
    
    # Calculate initial utility (cash at start, no goods)
    initial_utility = player.initialCash
    
    # Calculate final utility (Total Score at end)
    final_utility = player.overall_utility
    
    # Calculate utility change percentage (Score Change %)
    if not player.isObserver and player.isParticipating and initial_utility != 0:
        player.utilityChangePercent = ((final_utility - initial_utility) / initial_utility) * 100
    else:
        player.utilityChangePercent = 0
    
    # Note: Payoff is no longer calculated here - it's determined at the end based on group comparison


def calc_final_profit(group: Group):
    # this code is run at the final results wait page after all players arrive.
    # this function randomly selects a round and determines the winner within the group.
    # All participating players get base payment (€1.81), winner gets bonus (€1.81).
    
    # Get all participating players in the group
    participating_players = [p for p in group.get_players() if p.isParticipating == 1]
    
    if not participating_players:
        return  # No participating players, skip calculation
    
    # Get trading rounds (exclude trial rounds) - use first player as reference
    first_player = participating_players[0]
    trading_rounds = [p for p in first_player.in_all_rounds() if p.round_number > C.num_trial_rounds]
    
    if not trading_rounds:
        # Fallback if no trading rounds (shouldn't happen)
        for p in participating_players:
            p.selectedRound = 1
            p.finalPayoff = C.base_payment
            p.isWinner = False
        return
    
    # Randomly select a round (same for all players in the group)
    selected_round_index = random.randint(0, len(trading_rounds) - 1)
    selected_round_number = trading_rounds[selected_round_index].round_number
    
    # Store selected round for all players
    for p in participating_players:
        # Convert to display round number (1-based, excluding trial rounds)
        p.selectedRound = selected_round_number - C.num_trial_rounds
    
    # Find Score Change % for each player in the selected round
    player_scores = []
    for p in participating_players:
        # Find the player's round data for the selected round
        selected_round_player = None
        for round_player in p.in_all_rounds():
            if round_player.round_number == selected_round_number:
                selected_round_player = round_player
                break
        
        if selected_round_player:
            score_change = selected_round_player.utilityChangePercent
            player_scores.append((p, score_change))
        else:
            # Fallback: no score found
            player_scores.append((p, 0))
    
    # Find the maximum Score Change % in the group
    max_score_change = max(score for _, score in player_scores) if player_scores else 0
    
    # Find all players with the highest Score Change %
    tied_winners = [p for p, score in player_scores if score == max_score_change and max_score_change is not None]
    
    # Randomly select one winner if there's a tie
    if tied_winners:
        winner = random.choice(tied_winners)
    else:
        winner = None
    
    # Set finalPayoff and isWinner for each player
    for p, score_change in player_scores:
        # Everyone gets base payment
        p.finalPayoff = C.base_payment
        p.isWinner = False
        
        # Only the selected winner gets bonus
        if p == winner:
            p.isWinner = True
            p.finalPayoff = C.base_payment + C.bonus_payment


def custom_export(players):
    # this function defines the variables that are downloaded in customised tables
    # Export Limits
    yield ['TableName', 'sessionID', 'offerID', 'group', 'Period', 'maker', 'price', 'limitVolume', 'isBid', 'offerID', 'orderID', 'offerTime', 'remainingVolume', 'isActive', 'bestAskBefore', 'bestBidBefore', 'bestAskAfter', 'bestBidAfter']
    limits = Limit.filter()
    for l in limits:
        yield ['Limits', l.group.session.code, l.offerID, l.group.id_in_subsession, l.group.round_number, l.makerID, l.price, l.limitVolume, l.isBid, l.orderID, l.offerTime, l.remainingVolume, l.isActive, l.bestAskBefore, l.bestBidBefore, l.bestAskAfter, l.bestBidAfter]

    # Export Transactions
    yield ['TableName', 'sessionID', 'transactionID', 'group', 'Period', 'maker', 'taker', 'price', 'transactionVolume', 'limitVolume', 'sellerID', 'buyerID', 'isBid', 'offerID', 'orderID', 'offerTime', 'transactionTime', 'remainingVolume', 'isActive', 'bestAskBefore', 'bestBidBefore', 'bestAskAfter', 'bestBidAfter']
    trades = Transaction.filter()
    for t in trades:
        yield ['Transactions', t.group.session.code, t.transactionID, t.group.id_in_subsession, t.group.round_number, t.makerID, t.takerID, t.price, t.transactionVolume, t.limitVolume, t.sellerID, t.buyerID, t.isBid, t.offerID, t.orderID, t.offerTime, t.transactionTime, t.remainingVolume, t.isActive, t.bestAskBefore, t.bestBidBefore, t.bestAskAfter, t.bestBidAfter]

    # Export Orders
    yield ['TableName', 'sessionID', 'orderID', 'orderType', 'group', 'Period', 'maker', 'taker', 'price', 'transactionVolume', 'limitVolume', 'sellerID', 'buyerID', 'isBid', 'offerID', 'transactionID', 'offerTime', 'transactionTime', 'remainingVolume', 'isActive', 'bestAskBefore', 'bestBidBefore', 'bestAskAfter', 'bestBidAfter']
    orders = Order.filter()
    for o in orders:
        yield ['Orders', o.group.session.code, o.orderID, o.orderType, o.group.id_in_subsession, o.group.round_number, o.makerID, o.takerID, o.price, o.transactionVolume, o.limitVolume, o.sellerID, o.buyerID, o.isBid, o.offerID, o.transactionID, o.offerTime, o.transactionTime, o.remainingVolume, o.isActive, o.bestAskBefore, o.bestBidBefore, o.bestAskAfter, o.bestBidAfter]

    # Export BidAsk
    yield ['TableName', 'sessionID', 'orderID', 'operationType', 'group', 'Period', 'bestAsk', 'bestBid', 'BATime', 'timing']
    bidasks = BidAsks.filter()
    for b in bidasks:
        yield ['BidAsks', b.group.session.code, b.orderID, b.operationType, b.group.id_in_subsession, b.group.round_number, b.bestAsk, b.bestBid, b.BATime, b.timing]

    # Export News
    yield ['TableName', 'sessionID', 'message', 'group', 'Period', 'playerID', 'msgTime']
    news = News.filter()
    for n in news:
        yield ['BidAsks', n.group.session.code, n.msg, n.group.id_in_subsession, n.group.round_number, n.playerID, n.msgTime]


class Limit(ExtraModel):
    offerID = models.IntegerField()
    orderID = models.IntegerField()
    makerID = models.IntegerField()
    group = models.Link(Group)
    Period = models.IntegerField()
    maker = models.Link(Player)
    limitVolume = models.IntegerField()
    price = models.FloatField(decimal=C.decimals)
    transactedVolume = models.IntegerField()
    remainingVolume = models.IntegerField()
    amount = models.FloatField(decimal=C.decimals)
    isBid = models.BooleanField(choices=((True, 'Bid'), (False, 'Ask')))
    offerTime = models.FloatField(doc="Timestamp (seconds since beginning of trading)")
    isActive = models.BooleanField(choices=((True, 'active'), (False, 'inactive')))
    bestBidBefore = models.FloatField()
    bestAskBefore = models.FloatField()
    bestAskAfter = models.FloatField()
    bestBidAfter = models.FloatField()


def limit_order(player: Player, data):
    # this code is run at the market page, within the live_method(), whenever a participants aimes to create a limit order.
    # this function processes limit orders and creates new entries in the Limit and Order tables.
    maker_id = player.id_in_group
    group = player.group
    period = group.round_number
    if player.isObserver:
        News.create(
            player=player,
            playerID=maker_id,
            group=group,
            Period=period,
            msg='Cannot proceed: you are an observer who cannot place a bid/ask.',
            msgTime=round(float(time.time() - player.group.marketStartTime), C.decimals)
        )
        return
    if not (data['isBid'] >= 0 and data['limitPrice'] and data['limitVolume']):
        News.create(
            player=player,
            playerID=maker_id,
            group=group,
            Period=period,
            msg='Cannot proceed: misspecified price, volume or asset.',
            msgTime=round(float(time.time() - player.group.marketStartTime), C.decimals)
        )
        return
    price = round(float(data['limitPrice']), C.decimals)
    is_bid = bool(data['isBid'] == 1)
    limit_volume = int(data['limitVolume'])
    if not (price > 0 and limit_volume > 0):
        News.create(
            player=player,
            playerID=maker_id,
            group=group,
            Period=period,
            msg='Cannot proceed: misspecified price or volume.',
            msgTime=round(float(time.time() - player.group.marketStartTime), C.decimals)
        )
        return
    if is_bid and player.cashHolding + player.capLong - player.cashOffered - limit_volume * price < 0:
        News.create(
            player=player,
            playerID=maker_id,
            group=group,
            Period=period,
            msg='Cannot proceed: insufficient cash available.',
            msgTime=round(float(time.time() - player.group.marketStartTime), C.decimals)
        )
        return
    best_ask_before = group.field_maybe_none('bestAsk')
    best_bid_before = group.field_maybe_none('bestBid')
    if not is_bid and player.assetsHolding + player.capShort - player.assetsOffered - limit_volume < 0:
        News.create(
            player=player,
            playerID=maker_id,
            group=group,
            Period=period,
            msg='Cannot proceed: insufficient assets available.',
            msgTime=round(float(time.time() - player.group.marketStartTime), C.decimals)
        )
        return
    elif (is_bid and best_ask_before is not None and price > best_ask_before) or (not is_bid and best_bid_before is not None and price < best_bid_before):
        News.create(
            player=player,
            playerID=maker_id,
            group=group,
            Period=period,
            msg='Cannot proceed: there is a buy/sell offer with the same or a more interesting price available.',
            msgTime=round(float(time.time() - player.group.marketStartTime), C.decimals)
        )
        return
    offer_id = player.subsession.offerID + 1
    player.subsession.offerID += 1
    while len(Limit.filter(group=group, offerID=offer_id)) > 0:  # to prevent duplicates in offerID
        offer_id += 1
    offer_time = round(float(time.time() - player.group.marketStartTime), C.decimals)
    order_id = player.subsession.orderID + 1
    player.subsession.orderID += 1
    while len(Order.filter(group=group, offerID=order_id)) > 0:  # to prevent duplicates in orderID
        order_id += 1
    if best_ask_before:
        best_ask_after = best_ask_before
    else:
        best_ask_before = -1
        best_ask_after = -1
    if best_bid_before:
        best_bid_after = best_bid_before
    else:
        best_bid_before = -1
        best_bid_after = -1
    if is_bid and (best_bid_before == -1 or price >= best_bid_before):
        best_bid_after = price
    elif not is_bid and (best_ask_before == -1 or price <= best_ask_before):
        best_ask_after = price
    Limit.create(
        offerID=offer_id,
        orderID=order_id,
        makerID=maker_id,
        group=group,
        Period=period,
        limitVolume=limit_volume,
        price=price,
        transactedVolume=0,
        remainingVolume=limit_volume,
        amount=limit_volume * price,
        isBid=is_bid,
        offerTime=offer_time,
        isActive=True,
        bestAskBefore=best_ask_before,
        bestBidBefore=best_bid_before,
        bestAskAfter=best_ask_after,
        bestBidAfter=best_bid_after,
    )
    Order.create(
        orderID=order_id,
        offerID=offer_id,
        makerID=maker_id,
        group=group,
        Period=period,
        limitVolume=limit_volume,
        price=price,
        transactedVolume=0,
        remainingVolume=limit_volume,
        amount=limit_volume * price,
        isBid=is_bid,
        orderType='limitOrder',
        offerTime=offer_time,
        orderTime=offer_time,
        isActive=True,
        bestAskBefore=best_ask_before,
        bestBidBefore=best_bid_before,
        bestAskAfter=best_ask_after,
        bestBidAfter=best_bid_after,
    )
    player.limitOrders += 1
    player.limitVolume += limit_volume
    group.limitOrders += 1
    group.limitVolume += limit_volume
    if is_bid:
        player.cashOffered += limit_volume * price
        player.limitBuyOrders += 1
        player.limitBuyVolume += limit_volume
        group.limitBuyOrders += 1
        group.limitBuyVolume += limit_volume
    else:
        player.assetsOffered += limit_volume
        player.limitSellOrders += 1
        player.limitSellVolume += limit_volume
        group.limitSellOrders += 1
        group.limitSellVolume += limit_volume


def cancel_limit(player: Player, data):
    # this code is run at the market page, within the live_method(), whenever a participants aimes to create a limit order.
    # this function processes limit order withdrawals and creates new entries in the Order table.
    if 'offerID' not in data:
        return
    maker_id = int(data['makerID'])
    group = player.group
    period = group.round_number
    if player.isObserver:
        News.create(
            player=player,
            playerID=maker_id,
            group=group,
            Period=period,
            msg='Cannot proceed: you are an observer who cannot withdraw a bid/ask.',
            msgTime=round(float(time.time() - player.group.marketStartTime), C.decimals)
        )
        return
    if maker_id != player.id_in_group:
        News.create(
            player=player,
            playerID=player.id_in_group,
            group=group,
            Period=period,
            msg='Cannot proceed: you can withdraw your own buy/sell offers only.',
            msgTime=round(float(time.time() - player.group.marketStartTime), C.decimals)
        )
        return
    offer_id = int(data['offerID'])
    # we need to update Limit table entry
    offers = [o for o in Limit.filter(group=group) if o.offerID == offer_id]
    if not offers or len(offers) != 1:
        print('Error: too few or too many buy/sell offers found while withdrawing.')
        return
    offers[0].isActive = False
    is_bid = offers[0].isBid
    limit_volume = offers[0].limitVolume
    remaining_volume = offers[0].remainingVolume
    price = offers[0].price
    transacted_volume = offers[0].transactedVolume
    offer_time = offers[0].offerTime
    if price != float(data['limitPrice']) or is_bid != bool(data['isBid'] == 1):
        print('Odd request when player', maker_id, 'cancelled an order', data)
    order_id = player.subsession.orderID + 1
    player.subsession.orderID += 1
    while len(Order.filter(group=group, offerID=order_id)) > 0:  # to prevent duplicates in orderID
        order_id += 1
    best_ask_before = group.field_maybe_none('bestAsk')
    best_bid_before = group.field_maybe_none('bestBid')
    limitoffers = Limit.filter(group=group)
    best_bid_after = max([offer.price for offer in limitoffers if offer.isActive and offer.isBid] or [-1])
    best_ask_after = min([offer.price for offer in limitoffers if offer.isActive and not offer.isBid] or [-1])
    if not best_ask_before:
        best_ask_before = -1
    if not best_bid_before:
        best_bid_before = -1
    Order.create(
        orderID=order_id,
        offerID=offer_id,
        makerID=maker_id,
        group=group,
        Period=period,
        limitVolume=limit_volume,
        price=price,
        transactedVolume=transacted_volume,
        remainingVolume=0,
        amount=limit_volume * price,
        isBid=is_bid,
        orderType='cancelLimitOrder',
        offerTime=offer_time,
        orderTime=float(time.time() - player.group.marketStartTime),
        isActive=False,
        bestAskBefore=best_ask_before,
        bestBidBefore=best_bid_before,
        bestAskAfter=best_ask_after,
        bestBidAfter=best_bid_after,
    )
    player.cancellations += 1
    player.cancelledVolume += remaining_volume
    group.cancellations += 1
    group.cancelledVolume += remaining_volume
    if is_bid:
        player.cashOffered -= remaining_volume * price
    else:
        player.assetsOffered -= remaining_volume


class Order(ExtraModel):
    orderID = models.IntegerField()
    offerID = models.IntegerField()
    transactionID = models.IntegerField()
    makerID = models.IntegerField()
    takerID = models.IntegerField()
    sellerID = models.IntegerField()
    buyerID = models.IntegerField()
    group = models.Link(Group)
    Period = models.IntegerField()
    limitVolume = models.IntegerField()
    transactionVolume = models.IntegerField()
    transactedVolume = models.IntegerField()
    remainingVolume = models.IntegerField()
    price = models.FloatField(decimal=C.decimals)
    amount = models.FloatField(decimal=C.decimals)
    isBid = models.BooleanField(choices=((True, 'Bid'), (False, 'Ask')))
    orderType = models.StringField()
    orderTime = models.FloatField(doc="Timestamp (seconds since beginning of trading)")
    offerTime = models.FloatField()
    transactionTime = models.FloatField()
    isActive = models.BooleanField(choices=((True, 'active'), (False, 'inactive')))
    bestBidBefore = models.FloatField()
    bestAskBefore = models.FloatField()
    bestAskAfter = models.FloatField()
    bestBidAfter = models.FloatField()


class Transaction(ExtraModel):
    transactionID = models.IntegerField()
    offerID = models.IntegerField()
    orderID = models.IntegerField()
    makerID = models.IntegerField()
    takerID = models.IntegerField()
    sellerID = models.IntegerField()
    buyerID = models.IntegerField()
    group = models.Link(Group)
    Period = models.IntegerField()
    transactionVolume = models.IntegerField()
    limitVolume = models.IntegerField()
    remainingVolume = models.IntegerField()
    price = models.FloatField(decimal=C.decimals)
    amount = models.FloatField(decimal=C.decimals)
    isBid = models.BooleanField(choices=((True, 'Bid'), (False, 'Ask')))
    offerTime = models.FloatField()
    transactionTime = models.FloatField(doc="Timestamp (seconds since beginning of trading)")
    isActive = models.BooleanField(choices=((True, 'active'), (False, 'inactive')))
    bestBidBefore = models.FloatField()
    bestAskBefore = models.FloatField()
    bestAskAfter = models.FloatField()
    bestBidAfter = models.FloatField()


def transaction(player: Player, data):
    # this code is run at the market page, within the live_method(), whenever a participants aimes to acccept a limit order, i.e., when a market order is made.
    # this function processes market orders and creates new entries in the Transaction and Order tables, and updates the Limit table.
    if 'offerID' not in data:
        return
    offer_id = int(data['offerID'])
    taker_id = player.id_in_group
    group = player.group
    period = group.round_number
    if player.isObserver:
        News.create(
            player=player,
            playerID=taker_id,
            group=group,
            Period=period,
            msg='Cannot proceed: you are an observer who cannot accept a bid/ask.',
            msgTime=round(float(time.time() - player.group.marketStartTime), C.decimals)
        )
        return
    limit_entry = Limit.filter(group=group, offerID=offer_id)
    if len(limit_entry) > 1:
        print('Limit entry is not well-defined: multiple entries with the same ID')
    limit_entry = limit_entry[0]
    transaction_volume = int(data['transactionVolume'])
    is_bid = limit_entry.isBid
    price = float(limit_entry.price)
    maker_id = int(limit_entry.makerID)
    remaining_volume = int(limit_entry.remainingVolume)
    limit_volume = int(limit_entry.limitVolume)
    if not (price > 0 and transaction_volume > 0): # check whether data is valid
        News.create(
            player=player,
            playerID=taker_id,
            group=group,
            Period=period,
            msg='Cannot proceed: misspecified volume.',
            msgTime=round(float(time.time() - player.group.marketStartTime), C.decimals)
        )
        return
    if price != float(data['transactionPrice']) or is_bid != bool(data['isBid'] == 1):
        print('Odd request when player', maker_id, 'accepted an order', data, 'while in the order book we find', limit_entry)
    is_active = limit_entry.isActive
    if transaction_volume >= remaining_volume:
        transaction_volume = remaining_volume
        is_active = False
    if not is_bid and player.cashHolding + player.capLong - player.cashOffered - transaction_volume * price < 0:
        News.create(
            player=player,
            playerID=taker_id,
            group=group,
            Period=period,
            msg='Cannot proceed: insufficient cash available.',
            msgTime=round(float(time.time() - player.group.marketStartTime), C.decimals)
        )
        return
    best_ask_before = group.field_maybe_none('bestAsk')
    best_bid_before = group.field_maybe_none('bestBid')
    if is_bid and player.assetsHolding + player.capShort - player.assetsOffered - transaction_volume < 0:
        News.create(
            player=player,
            playerID=taker_id,
            group=group,
            Period=period,
            msg='Cannot proceed: insufficient assets available.',
            msgTime=round(float(time.time() - player.group.marketStartTime), C.decimals)
        )
        return
    elif maker_id == taker_id:
        News.create(
            player=player,
            playerID=taker_id,
            group=group,
            Period=period,
            msg='Cannot proceed: own buy/selloffers cannot be transacted.',
            msgTime=round(float(time.time() - player.group.marketStartTime), C.decimals)
        )
        return
    if (is_bid and best_bid_before and price < best_bid_before) or (not is_bid and best_ask_before and price > best_ask_before) :
        News.create(
            player=player,
            playerID=taker_id,
            group=group,
            Period=period,
            msg='Cannot proceed: there is a better buy/sell offer available.',
            msgTime=round(float(time.time() - player.group.marketStartTime), C.decimals)
        )
        return
    offer_time = round(float(limit_entry.offerTime), C.decimals)
    players = group.get_players()
    maker = [p for p in players if p.id_in_group == maker_id][0]
    if is_bid:
        [buyer, seller] = [maker, player]
        maker.cashOffered -= transaction_volume * price
        maker.limitBuyOrderTransactions += 1
        maker.limitBuyVolumeTransacted += transaction_volume
        player.marketSellOrders += 1
        player.marketSellVolume += transaction_volume
        group.marketSellOrders += 1
        group.marketSellVolume += transaction_volume
        seller_id = player.id_in_group
        buyer_id = maker.id_in_group
    else:
        [buyer, seller] = [player, maker]
        maker.assetsOffered -= transaction_volume  # undo offer holdings
        maker.limitSellOrderTransactions += 1
        maker.limitSellVolumeTransacted += transaction_volume
        player.marketBuyOrders += 1
        player.marketBuyVolume += transaction_volume
        group.marketBuyOrders += 1
        group.marketBuyVolume += transaction_volume
        seller_id = maker.id_in_group
        buyer_id = seller.id_in_group
    transaction_id = player.subsession.transactionID + 1
    player.subsession.transactionID += 1
    while len(Transaction.filter(group=group, offerID=transaction_id)) > 0:  # to prevent duplicates in transactionID
        transaction_id += 1
    order_id = player.subsession.orderID + 1
    player.subsession.orderID += 1
    while len(Order.filter(group=group, offerID=order_id)) > 0:  # to prevent duplicates in orderID
        order_id += 1
    transaction_time = round(float(time.time() - group.marketStartTime), C.decimals)
    limit_entry.transactedVolume += transaction_volume
    limit_entry.isActive = is_active
    transacted_volume = limit_entry.transactedVolume
    limit_entry.remainingVolume -= transaction_volume
    buyer.cashHolding -= transaction_volume * price
    seller.cashHolding += transaction_volume * price
    buyer.overall_utility = calculate_goods_utility(buyer) + buyer.cashHolding
    seller.overall_utility = calculate_goods_utility(seller) + seller.cashHolding
    buyer.transactions += 1
    buyer.transactedVolume += transaction_volume
    buyer.assetsHolding += transaction_volume
    seller.transactions += 1
    seller.transactedVolume += transaction_volume
    seller.assetsHolding -= transaction_volume
    maker.limitOrderTransactions += 1
    maker.limitVolumeTransacted += transaction_volume
    player.marketOrders += 1
    player.marketOrderVolume += transaction_volume
    group.transactions += 1
    group.transactedVolume += transaction_volume
    limitOffers = Limit.filter(group=group)
    best_bid_after = max([offer.price for offer in limitOffers if offer.isActive and offer.isBid] or [-1])
    best_ask_after = min([offer.price for offer in limitOffers if offer.isActive and not offer.isBid] or [-1])
    if not best_ask_before:
        best_ask_before = -1
    if not best_bid_before:
        best_bid_before = -1
    Transaction.create(
        transactionID=transaction_id,
        offerID=offer_id,
        orderID=order_id,
        makerID=maker_id,
        takerID=taker_id,
        sellerID=seller_id,
        buyerID=buyer_id,
        group=group,
        Period=period,
        price=price,
        transactionVolume=transaction_volume,
        remainingVolume=remaining_volume - transaction_volume,
        amount=transaction_volume * price,
        isBid=is_bid,
        transactionTime=transaction_time,
        offerTime=offer_time,
        isActive=is_active,
        bestAskBefore=best_ask_before,
        bestBidBefore=best_bid_before,
        bestAskAfter=best_ask_after,
        bestBidAfter=best_bid_after,
    )
    Order.create(
        orderID=order_id,
        offerID=offer_id,
        transactionID=transaction_id,
        group=group,
        Period=period,
        makerID=maker_id,
        takerID=taker_id,
        sellerID=seller_id,
        buyerID=buyer_id,
        limitVolume=limit_volume,
        price=price,
        transactedVolume=transacted_volume,
        remainingVolume=remaining_volume - transaction_volume,
        amount=limit_volume * price,
        isBid=is_bid,
        orderType='marketOrder',
        orderTime=transaction_time,
        offerTime=offer_time,
        isActive=is_active,
        bestAskBefore=best_ask_before,
        bestBidBefore=best_bid_before,
        bestAskAfter=best_ask_after,
        bestBidAfter=best_bid_after,
    )

def buy_good(player: Player, data):
    good = data.get('good')
    qty_raw = data.get('quantity', 0)
    try:
        qty = int(qty_raw)
    except (ValueError, TypeError):
        News.create(
            player=player,
            playerID=player.id_in_group,
            group=player.group,
            Period=player.group.round_number,
            msg='Cannot proceed: invalid quantity.',
            msgTime=round(float(time.time() - player.group.marketStartTime), C.decimals)
        )
        return dict()

    # Add validation for invalid quantities
    if qty <= 0:
        News.create(
            player=player,
            playerID=player.id_in_group,
            group=player.group,
            Period=player.group.round_number,
            msg='Cannot proceed: quantity must be positive.',
            msgTime=round(float(time.time() - player.group.marketStartTime), C.decimals)
        )
        return dict()

    # Prices and asset costs from constants
    try:
        price = get_good_money_price(good)
        asset_cost = get_good_carbon_price(good)
    except ValueError:
        News.create(
            player=player,
            playerID=player.id_in_group,
            group=player.group,
            Period=player.group.round_number,
            msg='Cannot proceed: invalid good.',
            msgTime=round(float(time.time() - player.group.marketStartTime), C.decimals)
        )
        return dict()

    # Check if player can afford
    total_price = price * qty
    total_assets = asset_cost * qty
    if player.cashHolding < total_price or player.assetsHolding < total_assets:
        News.create(
            player=player,
            playerID=player.id_in_group,
            group=player.group,
            Period=player.group.round_number,
            msg='Cannot proceed: insufficient funds or assets.',
            msgTime=round(float(time.time() - player.group.marketStartTime), C.decimals)
        )
        return dict()

    # Update player holdings (only if they can afford it)
    if good == 'A':
        player.goodA_qty += qty
    else:
        player.goodB_qty += qty
    player.cashHolding -= total_price
    player.assetsHolding -= total_assets

    # Calculate utility from goods using the function
    player.goods_utility = calculate_goods_utility(player)
    player.overall_utility = player.goods_utility + player.cashHolding

    # Return success with updated values
    return dict(
        goodA_qty=player.goodA_qty,
        goodB_qty=player.goodB_qty,
        cashHolding=player.cashHolding,
        assetsHolding=player.assetsHolding,
        goods_utility=player.goods_utility,
        overall_utility=player.overall_utility,
        goods_trade_good=good,
        goods_trade_qty=qty,
        goods_trade_price=price
    )

class News(ExtraModel):
    player = models.Link(Player)
    playerID = models.IntegerField()
    group = models.Link(Group)
    Period = models.IntegerField()
    msg = models.StringField()
    msgTime = models.FloatField()


class BidAsks(ExtraModel):
    group = models.Link(Group)
    Period = models.IntegerField()
    assetValue = models.StringField()
    orderID = models.IntegerField()
    bestBid = models.FloatField()
    bestAsk = models.FloatField()
    BATime = models.FloatField()
    timing = models.StringField()
    operationType = models.StringField()


# PAGES
class EarlyEnd(Page):
    """EarlyEnd for Trading app - only shows for FormTradingGroups timeout"""
    # No timeout - players can stay here and click link to return to Prolific

    @staticmethod
    def is_displayed(player: Player):
        # Show EarlyEnd only for FormTradingGroups timeout (other cases handled by preparation app)
        return (player.round_number == 1 and 
                player.participant.vars.get('insufficient_players_timeout', False) and
                not player.participant.vars.get('early_end_seen', False))
    
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        # Mark that they've seen EarlyEnd so it doesn't show again
        player.participant.vars['early_end_seen'] = True
        # Mark that they should not see any more pages
        player.participant.vars['no_more_pages'] = True

    @staticmethod
    def vars_for_template(player: Player):
        insufficient_players = player.participant.vars.get('insufficient_players_timeout', False)
        return dict(
            failed_comprehension=False,
            timeout_inactive=False,
            privacy_timeout=False,
            no_consent=False,
            insufficient_players=insufficient_players,
        )

# All comprehension check pages are now handled by the preparation app
# Removed unused classes: Welcome, Privacy, Instructions, ComprehensionCheck, ComprehensionFeedback, ComprehensionPassed

class EndOfTrialRounds(Page):
    template_name = "_templates/endOfTrialRounds.html"

    @staticmethod
    def get_timeout_seconds(player: Player):
        return persistent_timeout(player, 'EndOfTrialRounds', 10)

    @staticmethod
    def is_displayed(player: Player):
        # Sync isParticipating if needed
        if 'isParticipating' in player.participant.vars:
            player.isParticipating = player.participant.vars['isParticipating']
        result = (player.round_number == C.num_trial_rounds + 1 and 
                 C.num_trial_rounds > 0 and 
                 player.isParticipating == 1)
        return result


class PreMarket(Page):
    @staticmethod
    def get_timeout_seconds(player: Player):
        return persistent_timeout(player, 'PreMarket', 60)
    
    @staticmethod
    def is_displayed(player: Player):
        return player.isParticipating == 1

    @staticmethod
    def vars_for_template(player: Player):
        group = player.group
        is_heterogeneous = group.endowment_type == 'heterogeneous'
        
        # Calculate marginal utilities based on preference for display
        # Use field_maybe_none() to safely handle None values
        preference = player.field_maybe_none('good_preference') or 'conventional'
        goodA_marginal_utility = get_good_satisfaction('A', preference)
        goodB_marginal_utility = get_good_satisfaction('B', preference)
        
        # Check if there are other players in the group
        other_players = [p for p in group.get_players() if p.id_in_group != player.id_in_group and p.isParticipating == 1]
        has_other_players = len(other_players) > 0
        
        if is_heterogeneous:
            # For heterogeneous groups: collect cash values of other players
            other_players_cash_values = []
            for other_player in other_players:
                cash_endowment_value = other_player.participant.vars.get('cash_endowment', 0)
                cash_endowment_rounded = round(cash_endowment_value, C.decimals)
                other_players_cash_values.append(cash_endowment_rounded)
            
            # Sort for consistent display
            other_players_cash_values.sort(reverse=True)
            
            # Format as comma-separated string for display
            if len(other_players_cash_values) == 0:
                cash_values_display = ""
            elif len(other_players_cash_values) == 1:
                cash_values_display = str(other_players_cash_values[0])
            elif len(other_players_cash_values) == 2:
                cash_values_display = f"{other_players_cash_values[0]} and {other_players_cash_values[1]}"
            else:
                # Format as "value1, value2, ..., and last_value"
                formatted_values = [str(v) for v in other_players_cash_values[:-1]]
                cash_values_display = ", ".join(formatted_values) + f", and {other_players_cash_values[-1]}"
            
            return dict(
                round=player.round_number - C.num_trial_rounds,
                is_heterogeneous=True,
                has_other_players=has_other_players,
                cash_values_display=cash_values_display,
                goodA_marginal_utility=goodA_marginal_utility,
                goodB_marginal_utility=goodB_marginal_utility,
                goodA_money_price=C.GOOD_A_MONEY_PRICE,
                goodA_carbon_price=C.GOOD_A_CARBON_PRICE,
                goodB_money_price=C.GOOD_B_MONEY_PRICE,
                goodB_carbon_price=C.GOOD_B_CARBON_PRICE,
            )
        else:
            # For homogeneous groups: all others have the same cash_homogeneous value
            return dict(
                round=player.round_number - C.num_trial_rounds,
                is_heterogeneous=False,
                has_other_players=has_other_players,
                homogeneous_cash=str(round(C.cash_homogeneous, C.decimals)),
                goodA_marginal_utility=goodA_marginal_utility,
                goodB_marginal_utility=goodB_marginal_utility,
                goodA_money_price=C.GOOD_A_MONEY_PRICE,
                goodA_carbon_price=C.GOOD_A_CARBON_PRICE,
                goodB_money_price=C.GOOD_B_MONEY_PRICE,
                goodB_carbon_price=C.GOOD_B_CARBON_PRICE,
        )

    @staticmethod
    def js_vars(player: Player):
        return dict(
            allowShort=player.allowShort,
            capShort=player.capShort,
            capLong=player.capLong,
            cashHolding=player.cashHolding,
        )


class WaitingMarket(WaitPage):
    @staticmethod
    def get_timeout_seconds(player: Player):
        # Timeout after 3 minutes - if someone closes browser, others can proceed
        return 180
    
    @staticmethod
    def is_displayed(player: Player):
        # Only participating players should see this wait page
        return player.isParticipating == 1

    @staticmethod
    def get_players_for_group(group: Group):
        # Wait only for participating players
        return [p for p in group.get_players() if p.isParticipating == 1]

    @staticmethod
    def after_all_players_arrive(group: Group):
        # Only called when all participating players (group 1) have arrived
        group.marketStartTime = round(float(time.time()), C.decimals)
        group.marketTime = get_max_time(group=group)


class Market(Page):
    live_method = live_method
    timeout_seconds = Group.marketTime

    @staticmethod
    def is_displayed(player: Player):
        return player.isParticipating


    @staticmethod
    def js_vars(player: Player):
        group = player.group
        return dict(
            id_in_group=player.id_in_group,
            allowShort=player.allowShort,
            capShort=player.capShort,
            capLong=player.capLong,  # round(player.capLong, 2)
            cashHolding=player.cashHolding,
            assetsHolding=player.assetsHolding,
            marketTime=group.marketTime,
        )

    @staticmethod
    def get_timeout_seconds(player: Player):
        group = player.group
        if player.isParticipating == 0:
            return 1
        else:
            return group.marketStartTime + group.marketTime - time.time()

    @staticmethod
    def vars_for_template(player: Player):
        # Calculate marginal utilities based on preference for display
        # Use field_maybe_none() to safely handle None values
        preference = player.field_maybe_none('good_preference') or 'conventional'
        goodA_marginal_utility = get_good_satisfaction('A', preference)
        goodB_marginal_utility = get_good_satisfaction('B', preference)
        
        return dict(
            goodA_marginal_utility=goodA_marginal_utility,
            goodB_marginal_utility=goodB_marginal_utility,
            goodA_money_price=C.GOOD_A_MONEY_PRICE,
            goodA_carbon_price=C.GOOD_A_CARBON_PRICE,
            goodB_money_price=C.GOOD_B_MONEY_PRICE,
            goodB_carbon_price=C.GOOD_B_CARBON_PRICE,
        )

class ResultsWaitPage(WaitPage):
    @staticmethod
    def get_timeout_seconds(player: Player):
        # Timeout after 2 minutes - results calculation should be quick
        return 120
    
    @staticmethod
    def is_displayed(player: Player):
        # Only participating players should see this wait page
        return player.isParticipating == 1

    @staticmethod
    def after_all_players_arrive(group: Group):
        # Only process participating players
        players = [p for p in group.get_players() if p.isParticipating == 1]
        for p in players:
            # Capture unused assets at end of round for all treatments
            p.unused_assets_endofround = p.assetsHolding
            
            calc_period_profits(player=p)
        
        # Calculate final profit and determine winners at group level (only in final round)
        if group.round_number == C.NUM_ROUNDS:
            calc_final_profit(group=group)


class Results(Page):
    @staticmethod
    def get_timeout_seconds(player: Player):
        return persistent_timeout(player, 'Results', 45)
    
    @staticmethod
    def is_displayed(player: Player):
        return player.isParticipating == 1

    @staticmethod
    def vars_for_template(player: Player):
        # Calculate initial utility for this round (cash at start, no goods)
        initial_utility = player.initialCash
        
        # Calculate final utility (current overall_utility)
        final_utility = player.overall_utility
        
        # Use the utility change from the existing system
        utility_change_percent = player.utilityChangePercent
        
        # Calculate carbon credit impact for destruction group
        carbon_impact = None
        if player.framing == 'destruction':
            co2_retired = player.unused_assets_endofround * C.CO2_PER_CREDIT
            km_saved = co2_retired * C.KM_PER_KG_CO2
            carbon_impact = {
                'unused_credits': player.unused_assets_endofround,
                'co2_retired': round(co2_retired, 1),
                'km_saved': round(km_saved, 1)
            }
            
        return dict(
            initialUtility=round(initial_utility, C.decimals),
            finalUtility=round(final_utility, C.decimals),
            utilityChangePercent=round(utility_change_percent, C.decimals),
            carbon_impact=carbon_impact,
            is_last_round=player.round_number == C.NUM_ROUNDS,
        )

    @staticmethod
    def js_vars(player: Player):
        # assetValue is not used in the experiment - removed to prevent errors
        return dict()


class SurveyDemographics(Page):
    form_model = 'player'
    form_fields = ['age', 'gender', 'education', 'income', 'employment']
    # No timeout - surveys don't block others, and we want complete data
    
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == C.NUM_ROUNDS and player.isParticipating == 1


class SurveyAttitudes(Page):
    form_model = 'player'
    form_fields = ['pct_effectiveness', 'pct_fairness', 'pct_support', 'climate_concern', 'climate_responsibility']
    # No timeout - surveys don't block others, and we want complete data
    
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == C.NUM_ROUNDS and player.isParticipating == 1
    
    @staticmethod
    def get_form_fields(player: Player):
        fields = ['pct_effectiveness', 'pct_fairness', 'pct_support', 'climate_concern', 'climate_responsibility']
        if player.framing == 'destruction':
            fields.append('co2_certificate_trust')
        return fields
    
    @staticmethod
    def vars_for_template(player: Player):
        return dict(
            framing=player.framing
        )


class FinalResults(Page):
    template_name = "_templates/finalResults.html"
    # No timeout - players can stay here and read their results

    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS and player.isParticipating == 1

    @staticmethod
    def vars_for_template(player: Player):
        # Get trading rounds for selected round lookup
        trading_rounds = [p for p in player.in_all_rounds() if p.round_number > C.num_trial_rounds]
        selected_round_index = player.selectedRound - 1  # Convert to 0-based index
        
        # Calculate carbon impact for selected round (destruction group only)
        selected_round_carbon_impact = None
        if player.framing == 'destruction' and selected_round_index < len(trading_rounds):
            selected_round_player = trading_rounds[selected_round_index]
            if hasattr(selected_round_player, 'unused_assets_endofround'):
                unused_credits = selected_round_player.unused_assets_endofround
                co2_retired = unused_credits * C.CO2_PER_CREDIT
                km_saved = co2_retired * C.KM_PER_KG_CO2
                selected_round_carbon_impact = {
                    'unused_credits': unused_credits,
                    'co2_retired': round(co2_retired, 1),
                    'km_saved': round(km_saved, 1)
                }
        
        # Get all players in the same group (for comparing Score Changes)
        group_players = [p for p in player.group.get_players() if p.isParticipating == 1]
        
        # Check if player was tied for highest but not randomly selected as winner
        was_tied_but_not_selected = False
        if selected_round_index < len(trading_rounds):
            selected_round_player = trading_rounds[selected_round_index]
            player_score = selected_round_player.utilityChangePercent
            
            # Get all group members' scores for the selected round
            all_scores = []
            for group_player in group_players:
                for rp in group_player.in_all_rounds():
                    if rp.round_number == selected_round_player.round_number:
                        all_scores.append(rp.utilityChangePercent)
                        break
            
            if all_scores:
                max_score = max(all_scores)
                # Player had max score but wasn't selected as winner (tied and lost random draw)
                if player_score == max_score and not player.isWinner:
                    was_tied_but_not_selected = True
        
        # Generate period data with Score Change % and carbon credit info for destruction group
        periodPayoff = []
        
        for p in player.in_all_rounds():
            if p.round_number > C.num_trial_rounds:
                # Round data: [Round number, Score Change %]
                round_data = [p.round_number - C.num_trial_rounds, round(p.utilityChangePercent, C.decimals)]
                
                # Collect Score Changes of other group members for this round
                other_players_scores = []
                for other_player in group_players:
                    if other_player.id != player.id:  # Exclude current player
                        # Find the other player's round data for this round number
                        other_round_player = None
                        for rp in other_player.in_all_rounds():
                            if rp.round_number == p.round_number:
                                other_round_player = rp
                                break
                        
                        if other_round_player:
                            other_score = round(other_round_player.utilityChangePercent, C.decimals)
                            other_players_scores.append(f"{other_score}")
                
                # Format as comma-separated list
                other_scores_str = ", ".join(other_players_scores) if other_players_scores else "-"
                round_data.append(other_scores_str)
                
                # Add carbon credit info for destruction group
                if player.framing == 'destruction' and hasattr(p, 'unused_assets_endofround'):
                    unused_credits = p.unused_assets_endofround
                    co2_retired = unused_credits * C.CO2_PER_CREDIT
                    km_saved = co2_retired * C.KM_PER_KG_CO2
                    
                    round_data.extend([unused_credits, round(co2_retired, 1), round(km_saved, 1)])
                
                periodPayoff.append(round_data)
        
        return dict(
            payoff=cu(round(player.finalPayoff, 2)),
            isWinner=player.isWinner,
            was_tied_but_not_selected=was_tied_but_not_selected,
            periodPayoff=periodPayoff,
            is_destruction_group=player.framing == 'destruction',
            selected_round_carbon_impact=selected_round_carbon_impact,
        )


def group_by_arrival_time_method(subsession: Subsession, waiting_players):
    """
    Called by oTree when group_by_arrival_time = True on FormTradingGroups.
    Returns a list of players to group together (of size PLAYERS_PER_GROUP), or None to keep waiting.
    This function must be at module level (not inside a class).
    
    Note: Players who reach this page should all be eligible (failed players are on EarlyEnd).
    Also handles timeout: if a player has been waiting > 15 minutes and can't form a group, mark them for EarlyEnd.
    """
    if subsession.round_number != 1:
        return None  # Use default grouping for other rounds
    
    # Get ALL players in the subsession (not just waiting_players) because we're using 2-app approach
    all_players = subsession.get_players()
    
    
    # Check for timeout: if any player has been waiting > 15 minutes and can't form a group, mark them for EarlyEnd
    session = subsession.session
    timeout_key = 'form_trading_groups_first_arrival_time'
    timeout_duration = 900  # 15 minutes
    
    if timeout_key in session.vars:
        elapsed = time.time() - session.vars[timeout_key]
        if elapsed >= timeout_duration:
            # Timeout reached - check if there are enough players to form a group
            eligible_before_timeout = [p for p in all_players 
                                     if not p.participant.vars.get('no_more_pages', False) and
                                        p.participant.vars.get('comp_passed', False) and
                                        p.participant.vars.get('waiting_for_group', False) and
                                        'cash_endowment' not in p.participant.vars]
            
            if len(eligible_before_timeout) < C.PLAYERS_PER_GROUP:
                # Not enough players - mark all waiting players for EarlyEnd
                for p in eligible_before_timeout:
                    p.isParticipating = 0
                    p.participant.vars['isParticipating'] = 0
                    p.participant.vars['insufficient_players_timeout'] = True
                    p.participant.vars['waiting_for_group'] = False
                    p.participant.vars['no_more_pages'] = True
                # Clear timeout key
                if timeout_key in session.vars:
                    del session.vars[timeout_key]
                # Return None to prevent grouping (players will go to EarlyEnd)
                return None
    
    # Debug: Check each player's status
    for p in all_players:
        waiting_flag = p.participant.vars.get('waiting_for_group', False)
        comp_passed = p.participant.vars.get('comp_passed', False)
        is_participating = p.isParticipating == 1
        has_cash = 'cash_endowment' in p.participant.vars
        no_more_pages = p.participant.vars.get('no_more_pages', False)
    
    # Filter to only eligible players who have passed comprehension and are waiting
    # Players who reach this page should have comp_passed=True, but double-check
    eligible = [p for p in all_players 
              if not p.participant.vars.get('no_more_pages', False) and  # Not on EarlyEnd
                 p.participant.vars.get('comp_passed', False) and  # Must have passed comprehension
                 p.participant.vars.get('waiting_for_group', False) and  # Must be waiting for group
                 'cash_endowment' not in p.participant.vars]  # Not already grouped
    
    # Get the required group size from constants
    required_size = C.PLAYERS_PER_GROUP
    
    
    # If we have enough players, return the first group of required_size
    if len(eligible) >= required_size:
        # Use a flag to prevent forming the same group multiple times
        # Sort by id to ensure consistent grouping
        eligible_sorted = sorted(eligible, key=lambda p: p.id_in_subsession)
        new_group = eligible_sorted[:required_size]
        
        # Create a unique key for this group
        group_key = tuple(sorted([p.id_in_subsession for p in new_group]))
        formation_key = f'_group_formed_{group_key}'
        
        if not subsession.session.vars.get(formation_key, False):
            # Mark that we're forming this group
            subsession.session.vars[formation_key] = True
            return new_group
        else:
            return None
    
    # Not enough players yet, return None to keep waiting
    return None


class FormTradingGroups(WaitPage):
    """
    Wait page that forms groups as players arrive using oTree's built-in group_by_arrival_time.
    Players who reach this page should all be eligible (failed players are on EarlyEnd).
    """
    template_name = 'Trading/FormTradingGroups.html'
    group_by_arrival_time = True  # Works after a filtering app (preparation app filters out failures)
    
    @staticmethod
    def after_all_players_arrive(group: Group):
        """
        Called when a full group arrives. Initialize the group.
        Note: The group is already formed by group_by_arrival_time_method, so we just initialize it.
        """
        if group.round_number != 1:
            return
        
        # Get players from the group (this should work since oTree just formed it)
        # If we get a detached instance error, we'll re-fetch from subsession
        try:
            players = group.get_players()
        except Exception:
            # If group is detached, re-fetch from subsession
            subsession = group.subsession
            # Find the group by matching player count and eligibility
            for g in subsession.get_groups():
                try:
                    g_players = g.get_players()
                    if len(g_players) == C.PLAYERS_PER_GROUP:
                        # Check if this looks like our group (all eligible, not initialized)
                        all_eligible = all(
                            p.participant.vars.get('waiting_for_group', False) and
                            p.participant.vars.get('comp_passed', False) and
                            p.isParticipating == 1 and
                            'cash_endowment' not in p.participant.vars
                            for p in g_players
                        )
                        if all_eligible:
                            group = g
                            players = g_players
                            break
                except Exception:
                    continue
        
        # If we still don't have players, something went wrong
        if 'players' not in locals() or not players:
            return
        required_size = C.PLAYERS_PER_GROUP
        
        # Sync isParticipating from participant.vars for all players (set by preparation app)
        for p in players:
            if 'isParticipating' in p.participant.vars:
                p.isParticipating = p.participant.vars['isParticipating']
        
        # Only initialize if this is a full group of eligible players
        eligible_players = [p for p in players 
                          if p.participant.vars.get('waiting_for_group', False) and
                             p.participant.vars.get('comp_passed', False) and
                             p.isParticipating == 1 and
                             'cash_endowment' not in p.participant.vars]
        
        
        if len(players) == required_size and len(eligible_players) == required_size:
            # Get treatment from first player (all should have same treatment from preparation app)
            first_player = players[0]
            treatment = first_player.participant.vars.get('treatment')
            framing = first_player.participant.vars.get('framing')
            endowment_type = first_player.participant.vars.get('endowment_type')
            
            
            if treatment:
                # Assign treatment to group
                group.treatment = treatment
                group.framing = framing
                group.endowment_type = endowment_type
                group.group_size = len(players)
                
                # Update all players with group treatment info
                for p in players:
                    p.treatment = treatment
                    p.framing = framing
                    p.endowment_type = endowment_type
                    p.participant.vars.update(
                        treatment=treatment,
                        framing=framing,
                        endowment_type=endowment_type,
                    )
                
                # Calculate and assign cash endowments
                for p in players:
                    cash_val = cash_endowment(player=p)
                
                # Assign good_preference (50% conventional, 50% eco)
                shuffled = players.copy()
                random.shuffle(shuffled)
                num_players = len(players)
                num_eco = num_players // 2
                num_conventional = num_players - num_eco
                preferences = (['conventional'] * num_conventional + ['eco'] * num_eco)
                random.shuffle(preferences)
                for p, pref in zip(shuffled, preferences):
                    p.good_preference = pref
                    p.participant.vars['good_preference'] = pref
                
                # Calculate Gini coefficient for heterogeneous groups
                if endowment_type == 'heterogeneous':
                    cash_endowments = [p.participant.vars.get('cash_endowment', 0) for p in players]
                    group.gini_coefficient = round(calculate_gini_coefficient(cash_endowments), 4)
                else:
                    group.gini_coefficient = 0.0
                
                # Initialize group and players for trading
                group.randomisedTypes = random_types(group=group)
                # Don't set numParticipants here - let count_participants() do it
                # participating_count = sum(1 for p in players if p.isParticipating == 1)
                # group.numParticipants = participating_count
                
                initiate_group(group=group)
                # count_participants() already sets group.numParticipants, so we don't need to set it again
                # group.numParticipants = participating_count
                
                # Reset timeout timer for the next group - give them a fresh 15 minutes
                timeout_key = 'form_trading_groups_first_arrival_time'
                session = group.subsession.session
                if timeout_key in session.vars:
                    del session.vars[timeout_key]
                
                for p in players:
                    if p.isParticipating == 1:
                        # assetValue is not used but set to prevent None errors
                        if group.field_maybe_none('assetValue') is not None:
                            p.assetValue = group.assetValue
                        set_player(player=p)
                        initiate_player(player=p)
                
                # Mark players as no longer waiting
                for p in players:
                    p.participant.vars['waiting_for_group'] = False
            else:
                # No treatment found for first player - this shouldn't happen
                pass
        else:
            # Group size mismatch - this shouldn't happen if group_by_arrival_time works correctly
            pass
    
    @staticmethod
    def get_timeout_seconds(player: Player):
        # Timeout after 15 minutes (900 seconds) - send to EarlyEnd
        return 900
    
    @staticmethod
    def is_displayed(player: Player):
        # Only show in round 1 after comprehension check is passed
        if player.round_number != 1:
            return False
        
        # Sync isParticipating from participant.vars (set by preparation app)
        # This ensures the player field matches participant.vars
        if 'isParticipating' in player.participant.vars:
            player.isParticipating = player.participant.vars['isParticipating']
        
        # Don't show if already in a group (has cash_endowment)
        if 'cash_endowment' in player.participant.vars:
            return False
        
        # Don't show if marked for EarlyEnd (including insufficient_players_timeout)
        if player.participant.vars.get('no_more_pages', False) or player.participant.vars.get('insufficient_players_timeout', False):
            return False
        
        # Only show if passed comprehension check
        comp_passed = player.participant.vars.get('comp_passed', False)
        if not comp_passed:
            return False
        
        # Mark that this player is available for grouping
        # (This is set in preparation app's ComprehensionPassed, but set it here too as backup)
        player.participant.vars['waiting_for_group'] = True
        
        return True
    
    @staticmethod
    def vars_for_template(player: Player):
        """
        Return display values only. DO NOT form groups here to avoid infinite loops.
        Group formation happens in get_players_for_group.
        """
        if player.round_number != 1:
            return {}
        
        subsession = player.subsession
        session = subsession.session
        
        # Use PLAYERS_PER_GROUP from constants (not hardcoded)
        required_group_size = C.PLAYERS_PER_GROUP
        timeout_key = 'form_trading_groups_first_arrival_time'  # Tracks when first eligible player arrived for timeout calculation
        timeout_duration = 900  # 15 minutes
        
        # Get all eligible players who are waiting (simplified - players who reach this page should be eligible)
        # Include the current player in the count
        # Only count players who are actually waiting (have waiting_for_group=True and no cash_endowment)
        waiting = [p for p in subsession.get_players() 
                  if not p.participant.vars.get('no_more_pages', False) and
                     p.participant.vars.get('waiting_for_group', False) and
                     'cash_endowment' not in p.participant.vars]
        
        
        # Set first arrival time if this is the first eligible player
        if waiting and timeout_key not in session.vars:
            session.vars[timeout_key] = time.time()
        
        # Check if timeout has been reached
        timeout_reached = False
        if timeout_key in session.vars:
            elapsed = time.time() - session.vars[timeout_key]
            if elapsed >= timeout_duration:
                timeout_reached = True
        
        # Handle timeout: mark all waiting players for EarlyEnd if they can't form a group
        if timeout_reached and len(waiting) < required_group_size:
            for p in waiting:
                p.isParticipating = 0
                p.participant.vars['isParticipating'] = 0
                p.participant.vars['insufficient_players_timeout'] = True
                p.participant.vars['waiting_for_group'] = False
                p.participant.vars['no_more_pages'] = True
            if timeout_key in session.vars:
                del session.vars[timeout_key]
            return {
                'eligible_count': 0,
                'players_needed': 0,
                'group_size': required_group_size,
                'player_has_cash_endowment': False,
                'timeout_reached': True,
                'insufficient_players': True,
                'time_remaining': None,
            }
        
        # Calculate display values
        # Show how many players are needed to complete the NEXT group that will form
        # This is based on how many players are currently waiting (not yet in a group)
        # The current player is included in 'waiting'
        if len(waiting) == 0:
            # Shouldn't happen, but fallback
            needed = required_group_size
        else:
            # Calculate how many players are needed for the next group
            # If there are N waiting players, they will form groups of size required_group_size
            # The remainder tells us how many are in the "incomplete" next group
            remaining_in_next_group = len(waiting) % required_group_size
            if remaining_in_next_group == 0:
                # All waiting players can form complete groups, so the next group needs required_group_size players
                needed = required_group_size
            else:
                # There's an incomplete group forming - show how many more it needs
                # Example: if 1 person is waiting and group_size=2, remaining=1, needed=2-1=1
                needed = required_group_size - remaining_in_next_group
        
        # Check if timeout is approaching (for display purposes)
        time_remaining = None
        if timeout_key in session.vars:
            elapsed = time.time() - session.vars[timeout_key]
            time_remaining = max(0, timeout_duration - elapsed)
            time_remaining = int(time_remaining)
        
        # Check if this player was just assigned to a group
        player_has_cash = 'cash_endowment' in player.participant.vars
        if player_has_cash:
            # Mark as no longer waiting
            player.participant.vars['waiting_for_group'] = False
        
        return {
            'eligible_count': len(waiting), 
            'players_needed': needed, 
            'group_size': required_group_size,
            'player_has_cash_endowment': player_has_cash,
            'time_remaining': time_remaining,
            'timeout_reached': timeout_reached,
            'insufficient_players': False
        }
    
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        """Handle timeout - mark player for EarlyEnd"""
        if timeout_happened:
            # Check if player couldn't form a group (still waiting)
            if 'cash_endowment' not in player.participant.vars:
                player.isParticipating = 0
                player.participant.vars['isParticipating'] = 0
                player.participant.vars['insufficient_players_timeout'] = True
                player.participant.vars['waiting_for_group'] = False
                player.participant.vars['no_more_pages'] = True  # Critical: prevent showing FormTradingGroups again


class TreatmentAssignment(Page):
    """
    For rounds > 1, preserves groups from round 1.
    Same players, same cash endowment, same treatment, same preferences.
    """
    
    @staticmethod
    def is_displayed(player: Player):
        # Only show in rounds > 1 to preserve groups
        # Skip if player has seen EarlyEnd
        if player.round_number == 1:
            return False
        
        # Sync isParticipating from participant.vars or round 1 (in case it's not set yet)
        if 'isParticipating' in player.participant.vars:
            player.isParticipating = player.participant.vars['isParticipating']
        elif player.round_number > 1:
            # Try to get from round 1
            round_1_player = player.in_round(1)
            if round_1_player:
                player.isParticipating = round_1_player.isParticipating
                player.participant.vars['isParticipating'] = round_1_player.isParticipating
        
        # For rounds > 1, if player successfully participated in round 1, they should continue
        # Clear no_more_pages if they have cash_endowment (successfully formed group in round 1)
        if player.round_number > 1:
            round_1_player = player.in_round(1)
            if round_1_player and 'cash_endowment' in round_1_player.participant.vars:
                # Player successfully formed a group in round 1, so clear no_more_pages
                player.participant.vars['no_more_pages'] = False
        
        # Players who reach this point should already have consent and be participating
        # (filtered by preparation app and FormTradingGroups)
        # Only check isParticipating (for potential future use with bots)
        no_more_pages = player.participant.vars.get('no_more_pages', False)
        is_participating = player.isParticipating == 1
        
        result = (not no_more_pages and is_participating)
        
        return result
    
    @staticmethod
    def get_timeout_seconds(player: Player):
        # Auto-advance immediately - page should be invisible
        return 0.01  # Even shorter for minimal flash
    
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        """Preserve groups from round 1 for rounds > 1"""
        if player.round_number > 1:
            subsession = player.subsession
            round_1_player = player.in_round(1)
            
            # Copy group structure from round 1 (only do this once per subsession)
            init_key = f'_round_{subsession.round_number}_initialized'
            if not subsession.session.vars.get(init_key, False):
                subsession.group_like_round(1)
                subsession.session.vars[init_key] = True
            
            # Get player's current group
            current_group = player.group
            if not current_group:
                return
            
            # Copy isParticipating from round 1
            if round_1_player:
                player.isParticipating = round_1_player.isParticipating
                player.participant.vars['isParticipating'] = round_1_player.isParticipating
            
            # Find corresponding group from round 1 by matching players
            round_1_group = None
            current_group_participant_ids = {p.participant.id for p in current_group.get_players()}
            for r1_group in subsession.in_round(1).get_groups():
                r1_group_participant_ids = {p.participant.id for p in r1_group.get_players()}
                if current_group_participant_ids == r1_group_participant_ids:
                    round_1_group = r1_group
                    break
            
            # Copy treatment/framing/endowment_type from round 1
            if round_1_player:
                treatment_val = round_1_player.participant.vars.get('treatment')
                framing_val = round_1_player.participant.vars.get('framing')
                endowment_type_val = round_1_player.participant.vars.get('endowment_type')
                
                if treatment_val:
                    player.treatment = treatment_val
                    current_group.treatment = treatment_val
                if framing_val:
                    player.framing = framing_val
                    current_group.framing = framing_val
                if endowment_type_val:
                    player.endowment_type = endowment_type_val
                    current_group.endowment_type = endowment_type_val
            
            # Copy group-level fields from round 1
            if round_1_group:
                if round_1_group.treatment:
                    current_group.treatment = round_1_group.treatment
                if round_1_group.framing:
                    current_group.framing = round_1_group.framing
                if round_1_group.endowment_type:
                    current_group.endowment_type = round_1_group.endowment_type
                if round_1_group.gini_coefficient is not None:
                    current_group.gini_coefficient = round_1_group.gini_coefficient
                if round_1_group.group_size:
                    current_group.group_size = round_1_group.group_size
                else:
                    # Fallback to PLAYERS_PER_GROUP if group_size not set in round 1
                    current_group.group_size = C.PLAYERS_PER_GROUP
                if round_1_group.numParticipants:
                    current_group.numParticipants = round_1_group.numParticipants
            
            # Copy cash endowment, good_preference, and all player values from round 1
            if round_1_player:
                # Copy cash_endowment from participant.vars
                if 'cash_endowment' in round_1_player.participant.vars:
                    player.participant.vars['cash_endowment'] = round_1_player.participant.vars['cash_endowment']
                
                # Copy good_preference
                if round_1_player.field_maybe_none('good_preference'):
                    good_pref = round_1_player.field_maybe_none('good_preference')
                    player.good_preference = good_pref
                    player.participant.vars['good_preference'] = good_pref
                
                # Initialize group for this round (only once per group)
                if round_1_group and player.isParticipating == 1:
                    group_init_key = f'_group_{current_group.id}_round_{subsession.round_number}_initialized'
                    if not subsession.session.vars.get(group_init_key, False):
                        # Initialize group-level settings once
                        if not current_group.field_maybe_none('randomisedTypes'):
                            current_group.randomisedTypes = random_types(group=current_group)
                            initiate_group(group=current_group)
                        subsession.session.vars[group_init_key] = True
                
                # Initialize EACH participating player (runs for every player, not just once per group)
                if round_1_player and player.isParticipating == 1:
                    # Copy all financial values directly from Round 1
                    player.initialCash = round_1_player.initialCash
                    player.initialAssets = round_1_player.initialAssets
                    player.cashHolding = round_1_player.initialCash  # Reset to initial cash
                    player.assetsHolding = round_1_player.initialAssets  # Reset to initial assets
                    player.allowShort = round_1_player.allowShort
                    player.allowLong = round_1_player.allowLong
                    player.capShort = round_1_player.capShort
                    player.capLong = round_1_player.capLong
                    
                    # assetValue is not used but set to prevent None errors
                    if player.field_maybe_none('assetValue') is None and current_group.field_maybe_none('assetValue') is not None:
                        player.assetValue = current_group.assetValue
                    
                    # Reset goods quantities and utility
                    player.goodA_qty = 0
                    player.goodB_qty = 0
                    player.goods_utility = calculate_goods_utility(player)
                    player.overall_utility = player.goods_utility + player.cashHolding
                    
                    # Re-initialize player state (this will recalculate limits based on copied values)
                    # Note: set_player reads from participant.vars['cash_endowment'], which we already copied
                    set_player(player=player)
                    initiate_player(player=player)

# Page sequence - preparation pages (Welcome, Privacy, Instructions, Comprehension) are now in preparation app
# FormTradingGroups is the first page in Trading app (after preparation app completes)
page_sequence = [
    # Form groups of 6 after comprehension check is passed (round 1 only)
    # Note: Players arrive here from preparation app with comp_passed=True and waiting_for_group=True
    FormTradingGroups, EarlyEnd,  # EarlyEnd for players who timeout or can't form groups
    # TreatmentAssignment handles round > 1 group copying (right before trading starts)
    TreatmentAssignment,
    # Continue with rest of experiment (only if passed and in a group)
    EndOfTrialRounds, PreMarket, WaitingMarket, Market, 
    ResultsWaitPage, Results, SurveyAttitudes, SurveyDemographics, FinalResults
]
