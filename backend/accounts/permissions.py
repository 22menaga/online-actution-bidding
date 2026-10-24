from rest_framework.permissions import BasePermission
class RolePermission(BasePermission):
    allowed_roles=()
    def has_permission(self, request, view): return bool(request.user and request.user.is_authenticated and request.user.is_active and not request.user.is_suspended and (not self.allowed_roles or request.user.role in self.allowed_roles))
class IsAdmin(RolePermission): allowed_roles=('ADMIN',)
class IsSeller(RolePermission): allowed_roles=('SELLER',)
class IsBuyer(RolePermission): allowed_roles=('BUYER',)
class IsSellerOrAdmin(RolePermission): allowed_roles=('SELLER','ADMIN')
