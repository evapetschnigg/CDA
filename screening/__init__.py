from otree.api import *

doc = """
Screening study to identify participants available for scheduled real-time sessions.
"""


class C(BaseConstants):
    NAME_IN_URL = 'screening'
    PLAYERS_PER_GROUP = None  # No groups needed for screening
    NUM_ROUNDS = 1
    
    # Session details - UPDATE THESE FOR EACH SESSION
    SESSION_DATE = "Tuesday, December 9, 2024"  # Update: Tuesday 9.12
    SESSION_TIME = "17:00"  # 5:00 PM - Update as needed
    SESSION_TIMEZONE = "GMT"  # Update timezone as needed


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    prolific_id = models.StringField(label="Prolific ID", blank=False)
    can_attend = models.BooleanField(
        label="",
        choices=[
            (True, 'Yes, I want to participate and can attend at this time (I will be punctual)'),
            (False, 'No, I do not want to participate or cannot attend at this time')
        ],
        widget=widgets.RadioSelect
    )


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
    def is_displayed(player: Player):
        return player.round_number == 1
    
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        # If Prolific ID was automatically captured from URL parameter, store it
        if player.participant.label:
            player.participant.vars['prolific_id'] = player.participant.label.strip().upper()


class ProlificID(Page):
    form_model = 'player'
    form_fields = ['prolific_id']
    
    @staticmethod
    def is_displayed(player: Player):
        # Only show this page if Prolific ID was not automatically captured from URL
        # If participant.label exists (from ?participant_label={{%PROLIFIC_PID%}}), skip this page
        return player.round_number == 1 and not player.participant.label
    
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        # Store trimmed, uppercase version for consistency
        if not timeout_happened and player.prolific_id:
            player.participant.vars['prolific_id'] = player.prolific_id.strip().upper()


class AvailabilityConfirmation(Page):
    form_model = 'player'
    form_fields = ['can_attend']
    
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1
    
    @staticmethod
    def vars_for_template(player: Player):
        return dict(
            session_date=C.SESSION_DATE,
            session_time=C.SESSION_TIME,
            session_timezone=C.SESSION_TIMEZONE,
        )


class ThankYou(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1
    
    @staticmethod
    def vars_for_template(player: Player):
        return dict(
            can_attend=player.can_attend,
            session_date=C.SESSION_DATE,
            session_time=C.SESSION_TIME,
        )


page_sequence = [Welcome, ProlificID, AvailabilityConfirmation, ThankYou]

