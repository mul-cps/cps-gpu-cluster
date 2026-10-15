import inspect as _native_inspect
from traitlets import observe as _native_observe
from jupyterhub.app import JupyterHub as _native_hub_class
_native_owners = frozenset(OWNERS)
_native_auth_base = _native_hub_class.class_traits()['authenticator_class'].validate(None, c.JupyterHub.authenticator_class)
class CPSNativeLoginGuard(_native_auth_base):
    @_native_observe('allowed_groups', 'admin_groups', 'auth_state_groups_key')
    def _requires_manage_groups(self, change):
        if self.manage_groups:
            return super()._requires_manage_groups(change)
    @_native_observe('claim_groups_key')
    def _claim_groups_key_changed(self, change):
        if callable(change.new):
            self.auth_state_groups_key = lambda state: self.claim_groups_key(state[self.user_auth_state_key])
        else:
            self.auth_state_groups_key = f'{self.user_auth_state_key}.{self.claim_groups_key}'
    async def update_auth_model(self, model):
        model = await super().update_auth_model(model)
        if not self.manage_groups and self.admin_groups and not model['admin']:
            groups = await self.get_user_groups(model['auth_state'])
            model['admin'] = bool(groups & self.admin_groups)
        return model
    async def check_allowed(self, username, model=None):
        if await super().check_allowed(username, model):
            return True
        if not self.manage_groups and self.allowed_groups and model is not None:
            return bool((await self.get_user_groups(model['auth_state'])) & self.allowed_groups)
        return False
    async def check_blocked_users(self, username, authentication=None):
        if username in _native_owners:
            return False
        result = super().check_blocked_users(username, authentication)
        return await result if _native_inspect.isawaitable(result) else result
    async def refresh_user(self, user, handler=None, **kwargs):
        machine_roles = getattr(getattr(user, 'orm_user', None), 'roles', ()) or ()
        if user.name in _native_owners:
            return (not getattr(user, 'admin', False)
                    and any(role.name == 'cps-workspace-kernel' for role in machine_roles))
        result = super().refresh_user(user, handler=handler, **kwargs)
        return await result if _native_inspect.isawaitable(result) else result
c.JupyterHub.authenticator_class = CPSNativeLoginGuard
c.Authenticator.manage_groups = False
c.GenericOAuthenticator.manage_groups = False
