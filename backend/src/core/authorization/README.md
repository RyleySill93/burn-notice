# Authorization System

## Overview
The authorization system implements a comprehensive Role-Based Access Control (RBAC) to manage permissions across various resources. The system features hierarchical permissions, explicit deny rules, and efficient caching mechanisms to ensure optimal performance while maintaining security.

## Core Components

### Access Roles
Access roles define reusable sets of permissions that can be assigned to users through memberships. Each role can contain multiple access policies and is scoped to a specific customer or entity.

### Access Policies
Access policies define specific permissions within a role. Each policy specifies:
- Permission type (READ, WRITE, ADMIN)
- Resource type (CLUSTER, NAMESPACE, ENTITY, DASHBOARD, FIELD, STAFF)
- Resource selector (for targeting specific resources)
- Effect (ALLOW, DENY)

### Membership Assignments
Links users to roles through their memberships, enabling the inheritance of all permissions defined in the associated access role.

## Key Authorization Principles

### Permission Hierarchy
Permissions follow a cascading hierarchy:
- ADMIN permission implies WRITE and READ permissions
- WRITE permission implies READ permission
- Explicit DENY rules always override any ALLOW rules (security-first approach)

### Resource Hierarchy
Permissions follow a resource hierarchy:
- Customer → Namespace → Entity
- Permissions granted at a higher level flow down to lower resources unless explicitly denied

### Cache Management
The system implements an efficient caching strategy:
- Permission checks are cached to improve performance
- Two distinct cache types: permission checks and permitted resource IDs
- Cache is automatically invalidated when:
  - Policies change
  - Role assignments change 
  - User assignments change

### Cache Invalidation
Cache invalidation is implemented at critical points:
- When creating or updating access policies
- When updating role-policy assignments
- When modifying user-role assignments
- When deleting membership assignments

## Performance Optimization
The authorization system uses bulk operations where possible to avoid nested queries and improve performance:
- Batch retrieval of membership assignments
- Bulk cache invalidation for affected users
- Efficient resource ID filtering

## Authorization Flow

The authorization flow follows this pattern:
1. Users are assigned to access roles through memberships
2. Access roles contain policies that define permissions
3. Policies specify what actions (permission types) can be performed on which resources (resource types)
4. The authorization service evaluates these policies, applying the permission hierarchy rules
5. Results are cached for improved performance until invalidated by relevant changes

This design allows for composable and reusable permission sets, making it easy to manage access across the application while maintaining strong security guarantees.


## Pattern for Adding a New Resource Type

When adding a new resource type (like FIELD_VALUE, FORMULA, DASHBOARD), follow this checklist:

### Backend (Authorization Service)

- [ ] Add to `ResourceTypeEnum` in `constants.py`
- [ ] Add to `_get_all_resources_for_type()` - return all resource IDs
- [ ] Add to `_get_universe_for_resource_type()` - return resources user might access
- [ ] Add to `_get_hierarchical_permissions()` - handle inheritance for `list_permitted_ids`
- [ ] Add to `list_permitted_ids()` - handle DENY filtering
- [ ] Add to `_has_hierarchical_permission()` - route to specific handler
- [ ] Add `_has_{resource}_permission()` method - implement hierarchy logic
- [ ] Add cache invalidation to create/delete operations

### Backend (Tests)

- [ ] `test_explicit_{resource}_allow`
- [ ] `test_explicit_{resource}_deny`
- [ ] `test_{resource}_inherits_from_{parent}`
- [ ] `test_list_permitted_{resource}_ids`

### Frontend

- [ ] Add to `ResourceTypeEnum.ts` (or regenerate client)
- [ ] Add label to `RESOURCE_TYPE_LABELS` in `constants.ts`
- [ ] Add label to local `RESOURCE_TYPE_LABELS` in `PoliciesManagement.tsx`
- [ ] Add query for resources (e.g., `listFormulasForCustomer`)
- [ ] Add to `ManagePolicyModal`:
  - [ ] Query with enabled condition
  - [ ] Namespace query enabled condition
  - [ ] `filteredResources` handling
  - [ ] `isLoading` condition
  - [ ] Resource type dropdown option
  - [ ] Picker `groupBy` conditions
- [ ] Add to `PoliciesManagement`:
  - [ ] Query for resources
  - [ ] `getDisplayName` helper function
  - [ ] `getResourceNamesById` handling
  - [ ] Sort condition for grouped display
- [ ] Add `NotEnforcedTag` if not yet enforced

### Enforcement (when ready)

- [ ] Update guards to use new resource type
- [ ] Add permission checks to write operations
- [ ] Add bulk filtering for import operations
- [ ] Update frontend to query/display permissions