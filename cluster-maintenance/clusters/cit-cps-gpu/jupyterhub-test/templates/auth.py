# OAuth Configuration Module
# Centralized authentication settings for JupyterHub

import os

def get_oauth_config():
    """
    Return OAuth configuration for Authentik integration
    """
    return {
        'client_id': 'vUhzKqEF0UxPtZNM8aRbA1ncaehhIAIA2x9r83FI',
        'client_secret': 'EbAzlZLERPQzmF2EQByhihKuUqp36u138fYERPptymppmJbWhquI4sHu9vchqtnMRqbAVnZS6nOA6G0FescWa13MOLdlegQB3yyZSqe5V32NtYsnfDOndyZHiqiL2Bj6',
        'oauth_callback_url': 'https://jupyterhub.cps.unileoben.ac.at/hub/oauth_callback',
        'authorize_url': 'https://auth.cps.unileoben.ac.at/application/o/authorize/',
        'token_url': 'https://auth.cps.unileoben.ac.at/application/o/token/',
        'userdata_url': 'https://auth.cps.unileoben.ac.at/application/o/userinfo/',
        'login_service': 'CPS Authentik',
        'username_claim': 'preferred_username',
        'userdata_params': {
            'state': 'state'
        },
        'scope': ['openid', 'profile', 'email', 'groups'],
        'claim_groups_key': 'groups'
    }

def get_admin_config():
    """
    Return admin user configuration
    """
    return {
        'users': ['bjoern.hagen']  # Add admin users here
    }
