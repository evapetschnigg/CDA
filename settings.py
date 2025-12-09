from os import environ

SESSION_CONFIGS = [
    dict(
        name='PCT',
        display_name='PCT',
        app_sequence=['preparation', 'Trading'],  # Preparation app runs first, then Trading
        num_demo_participants=6,
        market_time=80,
        randomise_types=True, # KeyError : 'roleID' shows up if this is set to False
        short_selling=False,
        margin_buying=False,
    ),
    dict(
        name='screening',
        display_name='Screening Study',
        app_sequence=['screening'],
        num_demo_participants=1,
    ),
]

# if you set a property in SESSION_CONFIG_DEFAULTS, it will be inherited by all configs
# in SESSION_CONFIGS, except those that explicitly override it.
# the session config can be accessed from methods in your apps as self.session.config,
# e.g. self.session.config['participation_fee']

SESSION_CONFIG_DEFAULTS = dict(
    real_world_currency_per_point=1.00, participation_fee=0.00, doc=""
)

PARTICIPANT_FIELDS = ['roleID', 'isObserver', 'isParticipating', 'treatment', 'framing', 'endowment_type', 'good_preference', 'finished']

SESSION_FIELDS = ['numParticipants']

# ISO-639 code
# for example: de, fr, ja, ko, zh-hans
LANGUAGE_CODE = 'en'

# e.g. EUR, GBP, CNY, JPY
REAL_WORLD_CURRENCY_CODE = 'GBP'
USE_POINTS = False

ADMIN_USERNAME = 'admin'
# For security, set admin password via environment variable:
# Heroku/oTree Hub: Set OTREE_ADMIN_PASSWORD in Config Vars
# Local: export OTREE_ADMIN_PASSWORD='your_secure_password_here'
# For local testing without env var, set a default password below:
ADMIN_PASSWORD = environ.get('OTREE_ADMIN_PASSWORD', 'test123')  # Default 'test123' for local testing only
# For production, ALWAYS set OTREE_ADMIN_PASSWORD environment variable!

# SECRET_KEY: Use environment variable for production, fallback for local testing
# On Heroku: heroku config:set OTREE_SECRET_KEY='your_generated_key'
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(50))"
SECRET_KEY = environ.get('OTREE_SECRET_KEY', '776841529')  # Change fallback for production!

DEMO_PAGE_INTRO_HTML = """ """

INSTALLED_APPS = ['otree']
#DEBUG = False

# AUTH_LEVEL: Required for oTree Hub free tier (public projects)
# DEMO = Anyone can access (required for free public projects on oTree Hub)
# STUDY = Requires authentication (not allowed for free public projects)
# You CAN collect real data in DEMO mode - all data is saved normally!
AUTH_LEVEL = 'DEMO'  # Required for oTree Hub free tier
