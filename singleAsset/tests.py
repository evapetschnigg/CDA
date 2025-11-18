from otree.api import Bot, Submission
import random
from . import (
    Welcome, Privacy, Instructions, ComprehensionCheck, ComprehensionFeedback,
    ComprehensionPassed, EndOfTrialRounds, PreMarket, Market, Results,
    SurveyDemographics, SurveyAttitudes, FinalResults, C
)


class PlayerBot(Bot):
    def play_round(self):
        # Welcome, Privacy, Instructions, and ComprehensionCheck are only shown in round 1
        if self.player.round_number == 1:
            # Welcome page - just click next
            yield Submission(Welcome, check_html=False)
            
            # Privacy page - consent
            yield Submission(Privacy, {'consent': True}, check_html=False)
            
            # Instructions page - just click next
            yield Submission(Instructions, check_html=False)
            
            # ComprehensionCheck - answer all questions correctly
            comp_answers = {
                'comp_q1': 'c',  # Total Score increases from 50 to 85
                'comp_q2': 'a',  # Total Score decreases from 40 to 30
                'comp_q3': 'c',  # They do not directly affect Total Score, but needed to buy goods
                'comp_q4': 'b',  # Incorrect (they are transferred)
                'comp_q5': 'c'   # All get base €1.81, highest in group gets bonus
            }
            
            # Add comp_q6 for destruction group
            if self.player.framing == 'destruction':
                comp_answers['comp_q6'] = 'a'  # Correct - CO2 compensation
            
            # Submit comprehension check with correct answers (should pass on first try)
            yield Submission(ComprehensionCheck, comp_answers, check_html=False)
            
            # After passing, ComprehensionPassed page is shown
            yield Submission(ComprehensionPassed, check_html=False)
        
        # EndOfTrialRounds - click next (only shown in round 2, after trial round 1 completes)
        # Note: is_displayed checks round_number == C.num_trial_rounds + 1
        if self.player.round_number == 2:  # After trial round (round 1)
            yield Submission(EndOfTrialRounds, check_html=False)
        
        # PreMarket - click next
        yield Submission(PreMarket, check_html=False)
        
        # Market page - wait for timeout (bots don't need to trade, just wait)
        # The Market page will timeout automatically, so we just submit
        yield Submission(Market, check_html=False)
        
        # Results - click next
        yield Submission(Results, check_html=False)
        
        # Survey pages - only shown in final round (round 7)
        if self.player.round_number == C.NUM_ROUNDS:
            # SurveyAttitudes - fill with random values (comes first in page sequence)
            survey_answers = {
                'pct_effectiveness': random.randint(1, 5),
                'pct_fairness': random.randint(1, 5),
                'pct_support': random.randint(1, 5),
                'climate_concern': random.randint(1, 5),
                'climate_responsibility': random.randint(1, 5)
            }
            
            # Add co2_certificate_trust for destruction group
            if self.player.framing == 'destruction':
                survey_answers['co2_certificate_trust'] = random.choice([True, False])
            
            yield Submission(SurveyAttitudes, survey_answers, check_html=False)
            
            # SurveyDemographics - fill with random reasonable values (comes after SurveyAttitudes)
            yield Submission(SurveyDemographics, {
                'age': random.randint(25, 45),
                'gender': random.choice(['male', 'female', 'other', 'prefer_not_to_say']),
                'education': random.choice(['no_degree', 'middle_school', 'high_school', 'vocational_training', 'bachelor', 'master', 'doctorate', 'other']),
                'income': random.randint(1, 10),  # Income category
                'employment': random.choice(['employed_full_time', 'employed_part_time', 'self_employed', 'student', 'unemployed', 'retired', 'stay_at_home_parent', 'other'])
            }, check_html=False)
            
            # FinalResults - click next
            yield Submission(FinalResults, check_html=False)

