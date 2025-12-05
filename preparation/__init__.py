# type: ignore # my linter is Pyright/Pylance and it's flaggin correct otree code as errors, so I'm ignoring it

from otree.api import *
from otree.api import widgets
import time
from os import environ

doc = """Preparation app: Welcome, Privacy, Instructions, and Comprehension Check"""

class C(BaseConstants):
    NAME_IN_URL = 'preparation'
    PLAYERS_PER_GROUP = None
    num_trial_rounds = 1
    NUM_ROUNDS = 1  # Preparation app only runs in round 1
    
    # Payment constants (must match Trading app)
    base_payment = cu(3.75)  # Base payment for all participants who complete survey
    bonus_payment = cu(1.90)  # Additional payment for highest score increase winner
    
    # Treatment definitions (must match Trading app)
    TREATMENTS = [
        'baseline_homogeneous', 
        'baseline_heterogeneous', 
        'environmental_homogeneous', 
        'environmental_heterogeneous', 
        'destruction_homogeneous', 
        'destruction_heterogeneous'
    ]
    # ACTIVE_TREATMENTS: Set via environment variable for production (one treatment per oTree Hub project)
    # For local testing, you can modify this list directly
    # For production: Set OTREE_ACTIVE_TREATMENT environment variable (single treatment, e.g., 'baseline_homogeneous')
    active_treatment_env = environ.get('OTREE_ACTIVE_TREATMENT', '')
    if active_treatment_env:
        # Production: Use environment variable (single treatment per project)
        ACTIVE_TREATMENTS = [active_treatment_env]
    else:
        # Local testing: Default to baseline_homogeneous
        ACTIVE_TREATMENTS = ['baseline_homogeneous']


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


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
    # Minimal fields needed for preparation pages
    isParticipating = models.BooleanField(choices=((True, 'active'), (False, 'inactive')), initial=0)
    consent = models.BooleanField(initial=False)
    prolific_id = models.StringField(label="Prolific ID", blank=False)
    
    # Treatment fields (stored in participant.vars, but also in player for template access)
    treatment = models.StringField(initial="")
    framing = models.StringField(initial="")
    endowment_type = models.StringField(initial="")
    
    # Comprehension check fields - using RadioSelect widget to show all options with radio buttons
    # Note: blank=False (default) means all fields are required - users cannot proceed without answering
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
        ('a', 'a. I will receive the bonus of £1.90 if I have the highest Score Change in my group in any of the trading rounds'),  # Must match C.bonus_payment
        ('b', 'b. I will receive the base payout of £3.75 even if I do not complete the survey at the end'),  # Must match C.base_payment
        ('c', 'c. All participants who complete the full study receive £3.75, and the player with highest Score Change in her group in the randomly selected round gets an additional £1.90')  # Must match C.base_payment and C.bonus_payment
    ], widget=widgets.RadioSelect, label="")
    
    comp_q6 = models.StringField(choices=[
        ('a', 'a. Correct. For each unused carbon credit in the experiment, 1 kg CO₂ will be compensated through reforestation projects in Germany, helping to reduce real-world carbon emissions.'),
        ('b', 'b. Incorrect. Unused carbon credits in the experiment have no effect on real-world emissions')
    ], widget=widgets.RadioSelect, label="")  # Only for destruction framing
    comp_attempts = models.IntegerField(initial=0)
    comp_correct_count = models.IntegerField(initial=0)
    comp_passed = models.BooleanField(initial=False)


# Form validation functions (must be at module level, not inside Page classes)
def prolific_id_error_message(player, value):
    """Validate that Prolific ID is exactly 24 alphanumeric characters."""
    if not value:
        return 'Please enter your Prolific ID to continue.'
    
    value_clean = value.strip()
    
    if len(value_clean) != 24:
        return 'Your Prolific ID must be exactly 24 characters long. You entered {0} characters. Please enter a 24-character alphanumeric string.'.format(len(value_clean))
    
    if not value_clean.isalnum():
        return 'Your Prolific ID must contain only letters and numbers (no spaces or special characters). Please enter a 24-character alphanumeric string.'
    
    return None


# PAGES
class Welcome(Page):
    @staticmethod
    def get_timeout_seconds(player: Player):
        return persistent_timeout(player, 'Welcome', 120)
    
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        # Set everyone to participating by default
        # Privacy page will handle setting isParticipating=0 if needed (timeout/no consent)
        player.isParticipating = 1
        player.participant.vars['isParticipating'] = 1
    
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1


class Privacy(Page):
    form_model = 'player'
    form_fields = ['consent']
    
    @staticmethod
    def get_timeout_seconds(player: Player):
        return persistent_timeout(player, 'Privacy', 360)  # Increased from 180 to 360 seconds (6 minutes)
    
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1

    @staticmethod
    def vars_for_template(player: Player):
        # Get treatment from constants (same for all players in session)
        # Treatment is assigned in before_next_page, but we need it for template display
        treatment_list = C.ACTIVE_TREATMENTS
        if len(treatment_list) > 0:
            treatment = treatment_list[0]
            framing = treatment.split("_")[0] if "_" in treatment else treatment
        else:
            framing = 'baseline'  # Default fallback
        
        return dict(
            framing=framing,
        )

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        if timeout_happened or not player.consent:
            # End the experiment for non-consenting participants
            player.participant.vars['consent_given'] = False
            # Track if it was a timeout (for EarlyEnd feedback)
            if timeout_happened:
                player.participant.vars['privacy_timeout'] = True
            # Also mark them as not participating
            player.isParticipating = 0
            player.participant.vars['isParticipating'] = 0
        else:
            player.participant.vars['consent_given'] = True
            
            # Automatically assign treatment to consenting players (round 1 only)
            if player.round_number == 1:
                # ACTIVE_TREATMENTS should contain only one treatment per app for rolling groups
                treatment_list = C.ACTIVE_TREATMENTS
                if len(treatment_list) != 1:
                    raise ValueError(f"ACTIVE_TREATMENTS must contain exactly one treatment for rolling groups. Found: {treatment_list}")
                
                # Assign the single treatment to this player
                treatment = treatment_list[0]
                player.treatment = treatment
                
                # Split treatment name into components (e.g., baseline_homogeneous)
                parts = treatment.split("_")
                player.framing = parts[0]
                player.endowment_type = parts[1]
                
                # Store in participant.vars for persistence across apps
                player.participant.vars.update(
                    treatment=treatment,
                    framing=parts[0],
                    endowment_type=parts[1],
                )


class EarlyEnd(Page):
    # No timeout - players can stay here and click link to return to Prolific
    
    @staticmethod
    def is_displayed(player: Player):
        # Show EarlyEnd if:
        # 1. Round 1
        # 2. Either they didn't give consent OR they failed comprehension check 6 times (includes timeouts)
        # 3. They haven't already seen it (to avoid showing multiple times)
        return (player.round_number == 1 and 
                (not player.participant.vars.get('consent_given', True) or 
                 player.participant.vars.get('comp_failed_6_times', False)) and
                not player.participant.vars.get('early_end_seen', False))
    
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        # Mark that they've seen EarlyEnd so it doesn't show again
        player.participant.vars['early_end_seen'] = True
        # Mark that they should not see any more pages
        player.participant.vars['no_more_pages'] = True
    
    @staticmethod
    def vars_for_template(player: Player):
        failed_comprehension = player.participant.vars.get('comp_failed_6_times', False)
        privacy_timeout = player.participant.vars.get('privacy_timeout', False)
        no_consent = not player.participant.vars.get('consent_given', True) and not privacy_timeout
        # insufficient_players is only relevant for Trading app, but include it here to avoid template errors
        insufficient_players = False
        return dict(
            failed_comprehension=failed_comprehension,
            privacy_timeout=privacy_timeout,
            no_consent=no_consent,
            insufficient_players=insufficient_players,
        )


class ProlificID(Page):
    form_model = 'player'
    form_fields = ['prolific_id']
    
    @staticmethod
    def get_timeout_seconds(player: Player):
        return persistent_timeout(player, 'ProlificID', 300)
    
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1 and player.participant.vars.get('consent_given', False)
    
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        # Store trimmed, uppercase version for consistency
        if not timeout_happened and player.prolific_id:
            player.participant.vars['prolific_id'] = player.prolific_id.strip().upper()


class Instructions(Page):
    @staticmethod
    def get_timeout_seconds(player: Player):
        return persistent_timeout(player, 'Instructions', 480)
    
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1 and player.participant.vars.get('consent_given', False)

    @staticmethod
    def vars_for_template(player: Player):
        # Get endowment_type from player or participant.vars (fallback)
        endowment_type = player.endowment_type or player.participant.vars.get('endowment_type', '')
        framing = player.framing or player.participant.vars.get('framing', '')
        
        return dict(
            numTrials=C.num_trial_rounds,
            numRounds=7 - C.num_trial_rounds,  # Hardcoded to match Trading NUM_ROUNDS
            framing=framing,
            endowment_type=endowment_type,  # Needed for template to show correct instructions
        )


class ComprehensionCheck(Page):
    form_model = 'player'
    
    @staticmethod
    def get_timeout_seconds(player: Player):
        # Simple fixed timeout: participants always get 240 seconds on this page.
        # We intentionally do NOT use persistent_timeout here, so each visit
        # starts a fresh 240-second timer.
        return 240
    
    @staticmethod
    def get_form_fields(player: Player):
        fields = ['comp_q1', 'comp_q2', 'comp_q3', 'comp_q4', 'comp_q5']
        if player.framing == 'destruction':
            fields.append('comp_q6')
        return fields
    
    @staticmethod
    def is_displayed(player: Player):
        # Show comprehension check if:
        # 1. Round 1
        # 2. Consent given  
        # 3. Not yet passed (allows retries)
        # 4. Haven't exceeded max attempts (6)
        # 5. Haven't failed 6 times (includes timeouts and wrong answers)
        attempts = player.participant.vars.get('comp_attempts', 0)
        return (player.round_number == 1 and 
                player.participant.vars.get('consent_given', False) and
                not player.participant.vars.get('comp_passed', False) and
                attempts < 6 and
                not player.participant.vars.get('comp_failed_6_times', False))
    
    @staticmethod
    def vars_for_template(player: Player):
        return dict(
            framing=player.framing,
        )
    
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        # Increment attempts counter (timeout counts as an attempt)
        current_attempts = player.participant.vars.get('comp_attempts', 0)
        player.participant.vars['comp_attempts'] = current_attempts + 1
        player.comp_attempts = current_attempts + 1
        
        # Track if timeout occurred (for feedback message only)
        # Note: We still count their answers even if they timed out
        if timeout_happened:
            player.participant.vars['comp_timeout_occurred'] = True
        
        # Define correct answers
        correct_answers = {
            'comp_q1': 'c',  # Question 1: c
            'comp_q2': 'a',  # Question 2: a
            'comp_q3': 'c',  # Question 3: c
            'comp_q4': 'b',  # Question 4: b
            'comp_q5': 'c'   # Question 5: c
        }
        
        # Add comp_q6 for destruction group
        if player.framing == 'destruction':
            correct_answers['comp_q6'] = 'a'  # Question 6: a (destruction group only)
        
        # Count correct answers (same logic for timeout and non-timeout cases)
        correct_count = 0
        total_questions = len(correct_answers)
        for field_name, correct_answer in correct_answers.items():
            # Use field_maybe_none() to safely handle None values
            player_answer = player.field_maybe_none(field_name)
            if player_answer == correct_answer:
                correct_count += 1
        
        # Store results
        player.comp_correct_count = correct_count
        player.comp_passed = (correct_count == total_questions)  # Pass if all questions correct
        
        # Check if they've failed 6 times (6 attempts without passing)
        if player.comp_attempts == 6 and not player.comp_passed:
            # Mark that they've failed 6 times - they'll be directed to EarlyEnd
            player.participant.vars['comp_failed_6_times'] = True
            # Immediately mark player as not participating so wait pages exclude them
            player.isParticipating = 0
            player.participant.vars['isParticipating'] = 0
        
        # Store in participant vars for easy access across apps
        player.participant.vars['comp_correct_count'] = correct_count
        player.participant.vars['comp_passed'] = player.comp_passed
        player.participant.vars['comp_total_questions'] = total_questions


class ComprehensionFeedback(Page):
    @staticmethod
    def get_timeout_seconds(player: Player):
        # Simple fixed timeout: participants always get 60 seconds on this page.
        # We intentionally do NOT use persistent_timeout here, so each visit
        # starts a fresh 60-second timer.
        return 60
    
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        # Reset the timeout_occurred flag after showing feedback
        # This ensures the flag only applies to the current attempt
        if 'comp_timeout_occurred' in player.participant.vars:
            player.participant.vars['comp_timeout_occurred'] = False
    
    @staticmethod
    def is_displayed(player: Player):
        # Show feedback for failures (not when passed)
        # Exception: Don't show if they've failed 6 times (they'll see EarlyEnd instead)
        return (player.round_number == 1 and 
                player.participant.vars.get('consent_given', False) and
                player.participant.vars.get('comp_correct_count') is not None and
                not player.participant.vars.get('comp_passed', False) and
                not player.participant.vars.get('comp_failed_6_times', False))
    
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
                'correct_text': 'c. All participants who complete the full study receive £3.75, and the player with highest Score Change in her group in the randomly selected round gets an additional £1.90',  # Must match C.base_payment and C.bonus_payment
                'options': {
                    'a': 'a. I will receive the bonus of £1.90 if I have the highest Score Change in my group in any of the trading rounds',  # Must match C.bonus_payment
                    'b': 'b. I will receive the base payout of £3.75 even if I do not complete the survey at the end',  # Must match C.base_payment
                    'c': 'c. All participants who complete the full study receive £3.75, and the player with highest Score Change in her group in the randomly selected round gets an additional £1.90'  # Must match C.base_payment and C.bonus_payment
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
                'question': '6. Carbon credits not used by the end of a round will reduce real-world emissions.',
                'correct': 'a',
                'correct_text': 'a. Correct. For each unused carbon credit in the experiment, 1 kg of CO₂ will be compensated through reforestation projects in Germany, helping to reduce real-world carbon emissions.',
                'options': {
                    'a': 'a. Correct. For each unused carbon credit in the experiment, 1 kg CO₂ will be compensated through reforestation projects in Germany, helping to reduce real-world carbon emissions.',
                    'b': 'b. Incorrect. Unused carbon credits in the experiment have no effect on real-world emissions'
                }
            }
        
        # Prepare data for template
        questions = []
        for field_name, data in questions_data.items():
            # Use field_maybe_none() to safely handle None values (though fields are now required)
            user_answer = player.field_maybe_none(field_name) or ''
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
        
        # Check if they timed out on this attempt
        timeout_occurred = player.participant.vars.get('comp_timeout_occurred', False)
        
        # Calculate remaining tries
        max_attempts = 6
        remaining_tries = max(0, max_attempts - player.comp_attempts)
        
        return {
            'questions': questions,
            'correct_count': player.comp_correct_count,
            'total_questions': total_questions,
            'attempts': player.comp_attempts,
            'max_attempts': max_attempts,
            'remaining_tries': remaining_tries,
            'timeout_occurred': timeout_occurred
        }


class ComprehensionPassed(Page):
    @staticmethod
    def get_timeout_seconds(player: Player):
        return persistent_timeout(player, 'ComprehensionPassed', 15)
    
    @staticmethod
    def is_displayed(player: Player):
        # Show passed message only once when they first pass
        return (player.round_number == 1 and 
                player.participant.vars.get('consent_given', False) and
                player.participant.vars.get('comp_passed', False) and
                not player.participant.vars.get('comp_passed_message_shown', False))
    
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        # Mark that they've seen the passed message
        player.participant.vars['comp_passed_message_shown'] = True
        # Mark that they're ready for group formation (for Trading app)
        player.participant.vars['waiting_for_group'] = True
    
    @staticmethod
    def vars_for_template(player: Player):
        total_questions = player.participant.vars.get('comp_total_questions', 5)
        return dict(
            total_questions=total_questions,
        )


# Page sequence for preparation app
page_sequence = [
    Welcome, Privacy, EarlyEnd, ProlificID, Instructions,
    # Comprehension check loop (up to 6 attempts)
    # EarlyEnd appears after each ComprehensionFeedback to catch 6-time failures
    ComprehensionCheck, ComprehensionFeedback, ComprehensionPassed, EarlyEnd,
    ComprehensionCheck, ComprehensionFeedback, ComprehensionPassed, EarlyEnd,
    ComprehensionCheck, ComprehensionFeedback, ComprehensionPassed, EarlyEnd,
    ComprehensionCheck, ComprehensionFeedback, ComprehensionPassed, EarlyEnd,
    ComprehensionCheck, ComprehensionFeedback, ComprehensionPassed, EarlyEnd,
    ComprehensionCheck, ComprehensionFeedback, ComprehensionPassed, EarlyEnd,
]

