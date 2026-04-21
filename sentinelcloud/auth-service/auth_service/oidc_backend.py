from __future__ import annotations

from typing import Iterable

from django.contrib.auth.models import Group
from mozilla_django_oidc.auth import OIDCAuthenticationBackend


class KeycloakOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """Synchronise les rôles Keycloak vers les groupes Django."""

    def create_user(self, claims: dict):
        user = super().create_user(claims)
        self._sync_groups_and_flags(user, claims)
        return user

    def update_user(self, user, claims: dict):
        user = super().update_user(user, claims)
        self._sync_groups_and_flags(user, claims)
        return user

    def filter_users_by_claims(self, claims):
        email = claims.get("email")
        if email:
            return self.UserModel.objects.filter(email__iexact=email)
        preferred_username = claims.get("preferred_username")
        return self.UserModel.objects.filter(username__iexact=preferred_username)

    def _extract_roles(self, claims: dict) -> set[str]:
        roles: set[str] = set()

        realm_roles = claims.get("realm_access", {}).get("roles", [])
        roles.update(self._to_iterable(realm_roles))

        resource_access = claims.get("resource_access", {})
        for _, client in resource_access.items():
            client_roles = client.get("roles", [])
            roles.update(self._to_iterable(client_roles))

        return {r.strip() for r in roles if r and isinstance(r, str)}

    def _sync_groups_and_flags(self, user, claims: dict) -> None:
        roles = self._extract_roles(claims)
        groups = [Group.objects.get_or_create(name=role)[0] for role in sorted(roles)]
        user.groups.set(groups)

        user.is_staff = bool({"admin", "realm-admin", "staff"} & roles)
        user.is_superuser = "realm-admin" in roles
        user.save(update_fields=["is_staff", "is_superuser"])

    @staticmethod
    def _to_iterable(value) -> Iterable[str]:
        if isinstance(value, list):
            return value
        return []
