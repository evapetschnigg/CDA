# type: ignore # my linter is Pyright/Pylance and it's flaggin correct otree code as errors, so I'm ignoring it

from otree.api import *
import time
import random
import json 
from operator import itemgetter

doc = """Continuous double auction market"""

class C(BaseConstants):
    NAME_IN_URL = 'sCDA'
    PLAYERS_PER_GROUP = None
    num_trial_rounds = 1
    NUM_ROUNDS = 3  ## incl. trial periods
    base_payment = cu(15)
    multiplier = 90
    min_payment_in_round = cu(0)
    min_payment = cu(4)
    FV_MIN = 30
    FV_MAX = 85
    num_assets_MIN = 10
    num_assets_MAX = 10
    cash_MIN = 80
    cash_MAX = 120
    decimals = 2
    marketTime = 210  # needed to initialize variables but exchanged by session_config
    supply_shock_intensity = 0.8  # 0.8 = 20% reduction, 1.0 = no shock, 0.5 = 50% reduction
    
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
        'baseline_heterogeneous', 
        'environmental_homogeneous', 
        'environmental_heterogeneous', 
        'destruction_homogeneous', 
        'destruction_heterogeneous'
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
        for p in group.get_players():
            if p.isParticipating == 1:
                group.numParticipants += 1
    else:  # since player.isParticipating is not newly assign with a value by a click or a timeout, I take the value from the previous round
        for p in group.get_players():
            pr = p.in_round(group.round_number - 1)
            p.isParticipating = pr.isParticipating
        group.numParticipants = group.session.vars['numParticipants']
    group.session.vars['numParticipants'] = group.numParticipants


def initiate_group(group: Group):
    # this code is run at the first WaitToStart page when all participants arrived
    # this function starts substantial calculations on group level.
    count_participants(group=group)
    define_asset_value(group=group)
    assign_types(group=group)


def get_max_time(group: Group):
    # this code is run at the WaitingMarket page just before the market page when all participants arrived
    # this function returns the duration time of a market.
    return group.session.config['market_time']  # currently the binary value is retrieved from the config variables


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
        ('a', 'a. My payout cannot drop below €15'),
        ('b', 'b. I will receive the base payout even if I do not complete the survey at the end'),
        ('c', 'c. My payout is determined by my performance in one randomly selected round')
    ], widget=widgets.RadioSelect, label="")
    
    comp_q6 = models.StringField(choices=[
        ('a', 'a. Correct. For each unused carbon credit in the experiment, a verified real-world carbon certificate (~1 kg CO₂) will be purchased and retired, reducing real-world carbon emissions'),
        ('b', 'b. Incorrect. Unused carbon credits in the experiment have no effect on real-world emissions')
    ], widget=widgets.RadioSelect, label="", blank=True)
    
    # Comprehension check performance tracking
    comp_correct_count = models.IntegerField(initial=0)  # Number of correct answers (0-5 or 0-6 for destruction group)
    comp_passed = models.BooleanField(initial=False)     # True if all questions correct
    
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


def cash_endowment(player: Player):
    # this code is run at the first WaitToStart page, within the initiate_player() function, when all participants arrived
    # this function returns a participant's initial cash endowment based on their treatment
    group = player.group
    
    # Check if this is a heterogeneous treatment
    if group.endowment_type == 'heterogeneous':
        # For heterogeneous: random amount between cash_MIN and cash_MAX
        return float(round(random.uniform(a=C.cash_MIN, b=C.cash_MAX), C.decimals))
    else:
        # For homogeneous: average of cash_MIN and cash_MAX
        average_cash = (C.cash_MIN + C.cash_MAX) / 2
        return float(round(average_cash, C.decimals))  


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
        initial_cash = cash_endowment(player=player)
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
        player.goodA_utility_table = '[26,17,13,10,9,7,6,5]'
        player.goodB_utility_table = '[37,28,23,20,17,14,12,10]'
        player.goods_utility = calculate_goods_utility(player)
        player.overall_utility = player.goods_utility + player.cashHolding

def set_player(player: Player):
    # this code is run at the first WaitToStart page when all participants arrived.
    # this function retrieves player characteristics from the participants table.
    assign_role_attr(player=player, role_id=player.field_maybe_none('roleID'))
    if player.isParticipating:
        player.isObserver = player.participant.vars['isObserver']

def calculate_goods_utility(player: Player):
    """
    Calculate total utility from goods based on session configuration.
    """
    total_utility = 0
    
    # Get configuration from session
    use_constant = player.session.config.get('use_constant_marginal_utility', True)
    
    if use_constant:
        # Use constant marginal utility
        goodA_marginal_utility = player.session.config.get('good_a_marginal_utility', 12)
        goodB_marginal_utility = player.session.config.get('good_b_marginal_utility', 20)
        
        total_utility += player.goodA_qty * goodA_marginal_utility
        total_utility += player.goodB_qty * goodB_marginal_utility
    else:
        # Use utility tables
        for i in range(player.goodA_qty):
            if i < len(json.loads(player.goodA_utility_table)):
                total_utility += json.loads(player.goodA_utility_table)[i]
        for i in range(player.goodB_qty):
            if i < len(json.loads(player.goodB_utility_table)):
                total_utility += json.loads(player.goodB_utility_table)[i]
    
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
            cashHolding=p.cashHolding,
            assetsHolding=p.assetsHolding,
            goodA_qty=p.goodA_qty,
            goodB_qty=p.goodB_qty,
            goods_utility=p.goods_utility,
            overall_utility=p.overall_utility,
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
    # this function assesses a participant's initial and final utility and calculates the period income.
    
    # Calculate initial utility (cash at start, no goods)
    initial_utility = player.initialCash
    
    # Calculate final utility (Total Score at end)
    final_utility = player.overall_utility
    
    # Calculate utility change percentage
    if not player.isObserver and player.isParticipating and initial_utility != 0:
        player.utilityChangePercent = ((final_utility - initial_utility) / initial_utility) * 100
    else:
        player.utilityChangePercent = 0
    
    # Calculate payoff based on utility change
    player.payoff = max(C.base_payment + C.multiplier * (player.utilityChangePercent / 100), C.min_payment_in_round)


def calc_final_profit(player: Player):
    # this code is run at the final results page.
    # this function performs a random draw of period income and calculates a participant's payoff.
    # Only include trading rounds (exclude trial rounds)
    trading_rounds = [p for p in player.in_all_rounds() if p.round_number > C.num_trial_rounds]
    period_payoffs = [p.payoff for p in trading_rounds]
    
    # Randomly select from trading rounds only
    if period_payoffs:  # Make sure there are trading rounds
        r = random.randint(0, len(period_payoffs) - 1)
        player.selectedRound = r + 1  # Round numbers start from 1 for display
        player.finalPayoff = max(period_payoffs[r], C.min_payment)
    else:
        # Fallback if no trading rounds (shouldn't happen)
        player.selectedRound = 1
        player.finalPayoff = C.min_payment


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

    # Prices and asset costs
    if good == 'A':
        price = 5
        asset_cost = 1
    elif good == 'B':
        price = 10
        asset_cost = 3
    else:
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
class Welcome(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1

class Privacy(Page):
    form_model = 'player'
    form_fields = ['consent']
    
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1
    
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        if not player.consent:
            # End the experiment for non-consenting participants
            player.participant.vars['consent_given'] = False
        else:
            player.participant.vars['consent_given'] = True

class NoConsent(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1 and not player.participant.vars.get('consent_given', True)

class Instructions(Page):
    form_model = 'player'
    form_fields = ['isParticipating']

    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1 and player.participant.vars.get('consent_given', False)

    @staticmethod
    def vars_for_template(player: Player):
        print(f"DEBUG: Instructions page - Player {player.id} framing: '{player.framing}'")
        return dict(
            numTrials=C.num_trial_rounds,
            numRounds=C.NUM_ROUNDS - C.num_trial_rounds,
            framing=player.framing,
            endowment_type=player.endowment_type,
        )

class ComprehensionCheck(Page):
    form_model = 'player'
    
    @staticmethod
    def get_form_fields(player: Player):
        fields = ['comp_q1', 'comp_q2', 'comp_q3', 'comp_q4', 'comp_q5']
        if player.framing == 'destruction':
            fields.append('comp_q6')
        return fields
    
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1 and player.participant.vars.get('consent_given', False)
    
    @staticmethod
    def vars_for_template(player: Player):
        return dict(
            framing=player.framing,
        )
    
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        # Define correct answers
        correct_answers = {
            'comp_q1': 'c',  # Question 1: c
            'comp_q2': 'a',  # Question 2: a
            'comp_q3': 'c',  # Question 3: c (now question 4 in display order)
            'comp_q4': 'b',  # Question 4: b (now question 5 in display order)
            'comp_q5': 'c'   # Question 5: c (now question 3 in display order)
        }
        
        # Add comp_q6 for destruction group
        if player.framing == 'destruction':
            correct_answers['comp_q6'] = 'a'  # Question 6: a (destruction group only)
        
        # Count correct answers
        correct_count = 0
        total_questions = len(correct_answers)
        for field_name, correct_answer in correct_answers.items():
            if getattr(player, field_name) == correct_answer:
                correct_count += 1
        
        # Store results
        player.comp_correct_count = correct_count
        player.comp_passed = (correct_count == total_questions)  # Pass if all questions correct
        
        # Store in participant vars for easy access across rounds
        player.participant.vars['comp_correct_count'] = correct_count
        player.participant.vars['comp_passed'] = player.comp_passed
        player.participant.vars['comp_total_questions'] = total_questions


class ComprehensionFeedback(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1 and player.participant.vars.get('consent_given', False)
    
    @staticmethod
    def vars_for_template(player: Player):
        # Define correct answers and question texts
        questions_data = {
            'comp_q1': {
                'question': f"1. You have 50 mu, 6 {'carbon credits' if player.framing in ['environmental', 'destruction'] else 'assets'}, and no goods. What happens to your Total Score if you buy Good B (cost: 20 mu and 1 {'carbon credit' if player.framing in ['environmental', 'destruction'] else 'asset'}, value: 35 satisfaction points)?",
                'correct': 'c',
                'correct_text': 'c. My Total Score increases from 50 to 65',
                'options': {
                    'a': 'a. My Total Score increases from 0 to 35',
                    'b': 'b. My Total Score increases from 50 to 85',
                    'c': 'c. My Total Score increases from 50 to 65'
                }
            },
            'comp_q2': {
                'question': f"2. You have 30 mu, 5 {'carbon credits' if player.framing in ['environmental', 'destruction'] else 'assets'}, and 10 satisfaction points from goods. What happens to your Total Score if you buy {'a carbon credit' if player.framing in ['environmental', 'destruction'] else 'an asset'} for 10 mu?",
                'correct': 'a',
                'correct_text': 'a. My Total Score decreases from 40 to 30',
                'options': {
                    'a': 'a. My Total Score decreases from 40 to 30',
                    'b': 'b. My Total Score decreases from 30 to 20',
                    'c': 'c. My Total Score does not change'
                }
            },
            'comp_q5': {
                'question': '3. Which of the following correctly describes your payout for participating in this study?',
                'correct': 'c',
                'correct_text': 'c. My payout is determined by my performance in one randomly selected round',
                'options': {
                    'a': 'a. My payout cannot drop below €15',
                    'b': 'b. I will receive the base payout even if I do not complete the survey at the end',
                    'c': 'c. My payout is determined by my performance in one randomly selected round'
                }
            },
            'comp_q3': {
                'question': f"4. Which of the following correctly describes the role of {'carbon credits' if player.framing in ['environmental', 'destruction'] else 'assets'} in this experiment?",
                'correct': 'c',
                'correct_text': 'c. They do not directly affect the Total Score, but they can increase the money holdings when sold and can increase satisfaction points from goods when used to purchase goods',
                'options': {
                    'a': 'a. They directly affect the Total Score',
                    'b': 'b. They do not directly affect the Total Score, but they can increase the money holdings when they are bought',
                    'c': 'c. They do not directly affect the Total Score, but they can increase the money holdings when sold and can increase satisfaction points from goods when used to purchase goods'
                }
            },
            'comp_q4': {
                'question': f"5. {'Carbon credits' if player.framing in ['environmental', 'destruction'] else 'Assets'} not used by the end of a round will be transferred to the next round.",
                'correct': 'b',
                'correct_text': 'b. Incorrect',
                'options': {
                    'a': 'a. Correct',
                    'b': 'b. Incorrect'
                }
            }
        }
        
        # Add comp_q6 for destruction group
        if player.framing == 'destruction':
            questions_data['comp_q6'] = {
                'question': '6. Carbon credits not used by the end of a round, will reduce real-world emissions.',
                'correct': 'a',
                'correct_text': 'a. Correct. For each unused carbon credit in the experiment, a verified real-world carbon certificate (~1 kg CO₂) will be purchased and retired, reducing real-world carbon emissions',
                'options': {
                    'a': 'a. Correct. For each unused carbon credit in the experiment, a verified real-world carbon certificate (~1 kg CO₂) will be purchased and retired, reducing real-world carbon emissions',
                    'b': 'b. Incorrect. Unused carbon credits in the experiment have no effect on real-world emissions'
                }
            }
        
        # Prepare data for template
        questions = []
        for field_name, data in questions_data.items():
            user_answer = getattr(player, field_name, '')
            is_correct = user_answer == data['correct']
            
            questions.append({
                'question': data['question'],
                'user_answer': user_answer,
                'user_answer_text': data['options'].get(user_answer, 'No answer'),
                'correct_answer': data['correct'],
                'correct_text': data['correct_text'],
                'is_correct': is_correct
            })
        
        total_questions = 6 if player.framing == 'destruction' else 5
        
        return {
            'questions': questions,
            'correct_count': player.comp_correct_count,
            'total_questions': total_questions,
            'passed': player.comp_passed
        }


class WaitToStart(WaitPage):
    @staticmethod
    def after_all_players_arrive(group: Group):
        group.randomisedTypes = random_types(group=group)
        initiate_group(group=group)
        players = group.get_players()
        for p in players:
            p.assetValue = group.assetValue
            if p.isParticipating:
                set_player(player=p)
                initiate_player(player=p)


class EndOfTrialRounds(Page):
    template_name = "_templates/endOfTrialRounds.html"

    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == C.num_trial_rounds + 1 and C.num_trial_rounds > 0 and player.isParticipating == 1


class PreMarket(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.isParticipating == 1

    @staticmethod
    def vars_for_template(player: Player):
        return dict(
            round=player.round_number - C.num_trial_rounds,
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
    def after_all_players_arrive(group: Group):
        group.marketStartTime = round(float(time.time()), C.decimals)
        group.marketTime = get_max_time(group=group)


class Market(Page):
    live_method = live_method
    timeout_seconds = Group.marketTime

    @staticmethod
    def is_displayed(player: Player):
        return player.isParticipating

    @staticmethod
    def vars_for_template(player: Player):
        print(f"DEBUG: Market page - Player {player.id} framing: '{player.framing}'")
        return dict(
            framing=player.framing,
        )

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
        return dict(
            goodA_utility_table=json.loads(player.goodA_utility_table) if not player.session.config.get('use_constant_marginal_utility', True) else [],
            goodB_utility_table=json.loads(player.goodB_utility_table) if not player.session.config.get('use_constant_marginal_utility', True) else [],
        )

class ResultsWaitPage(WaitPage):
    @staticmethod
    def is_displayed(player: Player):
        return player.isParticipating == 1

    @staticmethod
    def after_all_players_arrive(group: Group):
        players = group.get_players()
        for p in players:
            calc_period_profits(player=p)
            if group.round_number == C.NUM_ROUNDS:
                calc_final_profit(player=p)


class Results(Page):
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
            
        return dict(
            payoff=cu(round(player.payoff, C.decimals)),
            initialUtility=round(initial_utility, C.decimals),
            finalUtility=round(final_utility, C.decimals),
            utilityChangePercent=round(utility_change_percent, C.decimals),
            is_last_round=player.round_number == C.NUM_ROUNDS,
        )

    @staticmethod
    def js_vars(player: Player):
        return dict(
            assetValue=round(player.assetValue, C.decimals),
        )


class SurveyDemographics(Page):
    form_model = 'player'
    form_fields = ['age', 'gender', 'education', 'income', 'employment']
    
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == C.NUM_ROUNDS and player.isParticipating == 1


class SurveyAttitudes(Page):
    form_model = 'player'
    form_fields = ['pct_effectiveness', 'pct_fairness', 'pct_support', 'climate_concern', 'climate_responsibility']
    
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == C.NUM_ROUNDS and player.isParticipating == 1


class FinalResults(Page):
    template_name = "_templates/finalResults.html"

    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS and player.isParticipating == 1

    @staticmethod
    def vars_for_template(player: Player):
        # Get the selected round's original payoff (before minimum adjustment)
        trading_rounds = [p for p in player.in_all_rounds() if p.round_number > C.num_trial_rounds]
        selected_round_index = player.selectedRound - 1  # Convert to 0-based index
        selected_round_original_payoff = trading_rounds[selected_round_index].payoff if selected_round_index < len(trading_rounds) else 0
        
        return dict(
            payoff=cu(round(player.finalPayoff, 0)),
            selectedRoundOriginalPayoff=cu(round(selected_round_original_payoff, 0)),
            periodPayoff=[[p.round_number - C.num_trial_rounds, round(p.payoff, C.decimals), round(p.utilityChangePercent, C.decimals)] for p in player.in_all_rounds() if p.round_number > C.num_trial_rounds],
        )


class TreatmentAssignment(WaitPage):
    wait_for_all_groups = True

    @staticmethod
    def is_displayed(player: Player):
        # Always show after consent (for group persistence in all rounds)
        return player.participant.vars.get('consent_given', False)

    @staticmethod
    def after_all_players_arrive(subsession: Subsession):
        print(f"DEBUG: after_all_players_arrive called for round {subsession.round_number}")

        # For rounds after round 1, copy groups from round 1
        if subsession.round_number > 1:
            print(f"DEBUG: Round {subsession.round_number} - copying groups from round 1")
            subsession.group_like_round(1)
            
            # Copy treatment info from round 1 groups to current groups
            round_1_groups = subsession.in_round(1).get_groups()
            current_groups = subsession.get_groups()
            
            for i, (round_1_group, current_group) in enumerate(zip(round_1_groups, current_groups)):
                current_group.treatment = round_1_group.treatment
                current_group.framing = round_1_group.framing
                current_group.endowment_type = round_1_group.endowment_type
                print(f"DEBUG: Round {subsession.round_number} - Group {i+1} copied treatment: {current_group.treatment}")
                
                # Also update player records with treatment info
                for p in current_group.get_players():
                    p.treatment = current_group.treatment
                    p.framing = current_group.framing
                    p.endowment_type = current_group.endowment_type
                    p.participant.vars.update(
                        treatment=current_group.treatment,
                        framing=current_group.framing,
                        endowment_type=current_group.endowment_type,
                    )
            
            # Debug: show the copied groups
            groups = subsession.get_groups()
            print(f"DEBUG: Round {subsession.round_number} - copied {len(groups)} groups")
            for i, group in enumerate(groups):
                players = group.get_players()
                print(f"DEBUG: Group {i+1} has {len(players)} players: {[p.id_in_subsession for p in players]}")
            return

        # Only create groups in round 1
        if subsession.round_number == 1:
            players = subsession.get_players()
            random.shuffle(players)

            treatment_list = C.ACTIVE_TREATMENTS
            num_players = len(players)
            n_groups = min(len(treatment_list), num_players)

            if n_groups < 1:
                raise ValueError("No players available to form groups.")

            # Distribute players into groups (round robin)
            groups_matrix = [[] for _ in range(n_groups)]
            for i, p in enumerate(players):
                groups_matrix[i % n_groups].append(p)

            subsession.set_group_matrix(groups_matrix)
            print(f"DEBUG: Created {n_groups} groups with set_group_matrix")
            print(f"DEBUG: Groups matrix: {[[p.id_in_subsession for p in grp] for grp in groups_matrix]}")

            # Assign treatments to groups
            import math
            num_treatments = len(treatment_list)
            reps = math.ceil(n_groups / num_treatments)
            treatment_pool = (treatment_list * reps)[:n_groups]
            random.shuffle(treatment_pool)

            for i, group in enumerate(subsession.get_groups()):
                group.treatment = treatment_pool[i]

                # Split treatment name into components (e.g., baseline_homogeneous)
                parts = group.treatment.split("_")
                group.framing = parts[0]
                group.endowment_type = parts[1]

                print(f"DEBUG: Group {group.id} assigned treatment {group.treatment}")

                # Store treatment info for all players
                for p in group.get_players():
                    p.treatment = group.treatment
                    p.framing = group.framing
                    p.endowment_type = group.endowment_type
                    p.participant.vars.update(
                        treatment=group.treatment,
                        framing=group.framing,
                        endowment_type=group.endowment_type,
                    )

page_sequence = [Welcome, Privacy, NoConsent, TreatmentAssignment, Instructions, ComprehensionCheck, ComprehensionFeedback, WaitToStart, EndOfTrialRounds, PreMarket, WaitingMarket, Market, ResultsWaitPage, Results, SurveyAttitudes, SurveyDemographics, FinalResults]
