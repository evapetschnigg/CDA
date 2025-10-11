# Personal Carbon Trading Experiment - Testing Guide

## For Local Network Testing
1. Make sure you're on the same WiFi network as the experiment host
2. Open your browser and go to: `http://192.168.0.101:8000/`
3. Click "Create a session" or join an existing session

## What to Test
- **Treatment Assignment**: Check that participants get assigned to different treatment groups
- **Instructions**: Verify that "assets" vs "carbon credits" terminology appears correctly based on treatment
- **Market Trading**: Test the trading interface works properly
- **Carbon Impact**: For destruction groups, verify carbon impact calculations appear on results pages
- **Survey Questions**: Check that destruction groups see the extra trust question
- **Final Results**: Verify payout calculations and carbon impact summaries

## Treatment Groups
- **Baseline**: Asset market terminology, no environmental context
- **Environmental**: Carbon market terminology, environmental context
- **Destruction**: Carbon market + real-world carbon credit destruction

## Key Features to Verify
✅ Group assignment and isolation (players only trade within their group)
✅ Supply shock implementation (20% reduction after 50% of rounds)
✅ Conditional terminology throughout the experiment
✅ Carbon impact tracking for destruction groups
✅ Trust question for destruction groups only
✅ Proper payout calculations

## Reporting Issues
Please note:
- Which treatment group you were assigned to
- What page/action caused the issue
- Screenshot if possible
- Browser type and version
