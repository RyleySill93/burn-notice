# Frontend Architecture

## Tech Stack Overview

### Core Technologies

#### Vite

- **Purpose**: Build tool and development server
- **Role**: Provides fast HMR (Hot Module Replacement), optimized builds, and modern ESM-based development experience
- **Configuration**: `vite.config.ts` sets up React plugin, Tailwind CSS integration, and path aliases

#### React 19

- **Purpose**: UI library for building component-based interfaces
- **Role**: Manages component state, lifecycle, and rendering
- **Integration**: Works with Vite through `@vitejs/plugin-react` for JSX transformation and React Refresh

#### TypeScript

- **Purpose**: Type-safe JavaScript superset
- **Role**: Provides static typing, better IDE support, and compile-time error checking
- **Configuration**: Three `tsconfig` files for different contexts (app, node, base)

### Styling

#### Tailwind CSS v4

- **Purpose**: Utility-first CSS framework
- **Role**: Provides atomic CSS classes for rapid styling
- **Integration**: Uses `@tailwindcss/vite` plugin for seamless Vite integration
- **Configuration**: CSS variables enabled for dynamic theming

#### shadcn/ui

- **Purpose**: Component library foundation
- **Role**: Provides accessible, customizable UI primitives
- **Components**: Located in `src/components/ui/` - includes Button, Checkbox, Input
- **Configuration**: `components.json` defines styling preferences (New York theme, Lucide icons)

### State Management & Data Fetching

#### TanStack Query (React Query)

- **Purpose**: Server state management
- **Role**: Handles data fetching, caching, synchronization, and background updates
- **Integration**: Custom hooks in `src/hooks/` wrap API calls with query functionality

### Form Management

#### React Hook Form with Super Components

- **Purpose**: Performant form state management with minimal re-renders and enhanced UX
- **Role**: Handles form validation, field state, and submission with uncontrolled components
- **Validation**: Uses Zod schemas with `@hookform/resolvers/zod`

##### Form Validation Philosophy

Our forms use a carefully designed validation strategy for optimal user experience:

**Before Form Submission:**
- Validation triggers on blur (when field loses focus) ONLY if the form is dirty (user has changed something)
- This prevents empty required fields from showing errors when users are just tabbing through
- Errors appear only when users have actually interacted with the form

**After Form Submission:**
- Validation switches to onChange mode for immediate feedback
- Errors update in real-time as users type corrections
- This helps users fix mistakes quickly after attempting to submit

**Key Benefits:**
- **No premature errors**: Users won't see errors until they've actually tried to input something
- **Submit buttons are never disabled**: Users can always attempt to submit, preventing frustration
- **Smart feedback timing**: Avoids annoying users with errors while they're initially filling out the form, but provides immediate feedback once they're correcting mistakes

##### Super Components

We've created enhanced wrapper components that eliminate boilerplate and ensure consistency:

- **SuperFormProvider**: All-in-one form solution combining form creation, context, and submission handling
- **SuperField**: Wrapper for form inputs that automatically handles labels, errors, ARIA attributes, and helper text
  - Shows required (*) or optional indicators based on the 50% rule
  - Only mark fields if they're in the minority for cleaner UI
- **SuperButton**: Enhanced button with automatic loading states for async operations and form submissions
- **useSuperForm**: Enhanced React Hook Form with smart validation and accessibility features:
  - Auto-focuses first input on mount
  - Auto-focuses first error field on validation failure
  - Announces errors to screen readers
  - Smart validation timing: onBlur only when form is dirty, onChange after submission
  - Custom register wrapper controls when validation triggers based on form state

##### API Error Handling

SuperFormProvider integrates with our `useApiError` hook for automatic error management:
- **Automatic error clearing**: Errors are cleared when form submission starts
- **Automatic error catching**: API errors are caught and displayed automatically
- **No manual try/catch needed**: Just throw errors in onSubmit handler
- **Consistent UX**: All forms handle errors the same way

##### Example Usage

```tsx
const apiError = useApiError()

return (
  <>
    {/* Error alert rendered outside form for flexible positioning */}
    {apiError.ErrorAlert}
    
    <SuperFormProvider
      config={{
        resolver: zodResolver(schema),
        defaultValues: { email: '', password: '' },
      }}
      apiError={apiError}  // Pass apiError for automatic error handling
      onSubmit={async (data) => {
        // No try/catch needed - just throw on error
        await loginMutation.mutateAsync(data)
        navigate({ to: '/dashboard' })
      }}
    >
      {(form) => (
        <>
          <SuperField name="email" errorText={form.formState.errors.email?.message}>
            <Input {...form.register('email')} />
          </SuperField>
          <SuperButton type="submit">Login</SuperButton>
        </>
      )}
    </SuperFormProvider>
  </>
)
```

#### Axios

- **Purpose**: HTTP client
- **Role**: Makes API requests to backend services
- **Integration**: Configured in `src/lib/api-config.ts` with base URL and interceptors

### Routing & Navigation

#### TanStack Router

- **Purpose**: Type-safe, file-based routing system
- **Role**: Manages client-side navigation, route state, and layouts
- **File Structure**: Routes defined in `src/routes/` directory
- **View Components**: Route logic separated into `src/views/` directory

#### Type-Safe Navigation

**Never use hardcoded links** - Always use TanStack Router's type-safe components:

```tsx
// ❌ Bad - hardcoded, not type-safe
<a href="/login">Login</a>

// ✅ Good - type-safe, refactorable
import { Link } from '@tanstack/react-router'
<Link to="/login">Login</Link>
```

**Link Component** for declarative navigation:
```tsx
// Simple navigation
<Link to="/dashboard">Dashboard</Link>

// With route parameters
<Link to="/user/$userId" params={{ userId: '123' }}>
  View Profile
</Link>

// With search parameters
<Link to="/products" search={{ category: 'electronics', page: 2 }}>
  Electronics
</Link>
```

**useNavigate Hook** for programmatic navigation:
```tsx
const navigate = useNavigate()

// Navigate after an action
const handleSubmit = async () => {
  await saveData()
  navigate({ to: '/success' })
}

// Navigate with params and search
navigate({ 
  to: '/user/$userId/settings', 
  params: { userId: user.id },
  search: { tab: 'security' }
})
```

**Benefits of Type-Safe Navigation**:
- TypeScript knows all your routes - auto-completion in IDE
- Compile-time validation of route params
- Refactoring safety - rename routes without breaking links
- No more typos in route paths

### Real-Time Communication

#### WebSocket Context

- **Purpose**: Real-time bidirectional communication with backend
- **Role**: Manages WebSocket connections, reconnection logic, and message handling
- **Location**: `src/contexts/WebSocketContext.tsx`
- **Features**:
  - Automatic reconnection with 3-second delay
  - Event subscription system for typed message handling
  - Connection status tracking (connecting/connected/disconnected)
  - React StrictMode compatible (prevents duplicate connections)
- **Configuration**: Uses `VITE_WS_BASE_URL` environment variable for WebSocket endpoint

### Custom Components

#### SuperButton

- **Purpose**: Enhanced button component with automatic loading state management
- **Location**: `src/components/SuperButton.tsx`
- **Motivation**: Eliminates boilerplate for loading states and prevents double-clicks
- **Features**:
  - Automatically detects async onClick handlers and shows loading spinner
  - Disables button during loading to prevent multiple submissions
  - Optional left/right icons with Lucide icons
  - Loading spinner replaces left icon during async operations
- **Usage**:
  ```tsx
  import { SuperButton } from '@/components/SuperButton'
  import { Save } from 'lucide-react'
  
  <SuperButton 
    leftIcon={Save}
    onClick={async () => {
      await saveData() // Spinner shows automatically
    }}
  >
    Save Changes
  </SuperButton>
  ```

#### SuperField

- **Purpose**: Comprehensive form field wrapper with consistent structure
- **Location**: `src/components/SuperField.tsx`
- **Motivation**: Ensures consistent form field layout, accessibility, and error handling
- **Features**:
  - Automatic label association with form controls
  - Required field indicators (red asterisk)
  - Helper text (inline or as tooltip with info icon)
  - Error message display with consistent styling
  - Works with any form control (Input, Select, Textarea, etc.)
- **Usage**:
  ```tsx
  import { SuperField } from '@/components/SuperField'
  
  <SuperField 
    label="Email Address"
    isRequired
    helperText="We'll never share your email"
    errorText={errors.email?.message}
  >
    <Input {...register('email')} />
  </SuperField>
  ```

**Important**: ALWAYS use SuperButton for buttons and SuperField for form fields. Never use raw Button or form inputs directly.

### Code Generation

#### Orval (OpenAPI Client Generator)

- **Purpose**: Automated API client generation with React Query hooks
- **Role**: Generates TypeScript types and React Query hooks from OpenAPI spec
- **Output**: `src/generated/` contains type-safe hooks and models
- **Command**: `npm run generate` fetches schema from backend and regenerates client
- **Benefits**:
  - Full TypeScript type safety for all API calls
  - React Query hooks for every endpoint
  - Automatic request/response type validation
  - No manual API client code needed

## API Call Patterns

### Using Generated React Query Hooks

**NEVER make direct API calls with fetch or axios**. Always use the generated React Query hooks from Orval:

```tsx
// ❌ BAD - Direct API call
const response = await fetch('http://localhost:8000/auth/signup', {
  method: 'POST',
  body: JSON.stringify(data)
})

// ✅ GOOD - Using generated hook
import { useSignup } from '@/generated/auth/auth'

const signupMutation = useSignup()
const { data } = await signupMutation.mutateAsync({
  data: { email, password, firstName, lastName }
})
```

### Query Hooks (GET requests)

For fetching data, use the query hooks that return data, loading, and error states:

```tsx
import { useGetUser } from '@/generated/users/users'

// Automatic data fetching with caching
const { data: user, isLoading, error } = useGetUser(userId)

if (isLoading) return <Spinner />
if (error) return <ErrorMessage />
return <UserProfile user={user} />
```

### Mutation Hooks (POST/PUT/DELETE)

For modifying data, use mutation hooks:

```tsx
import { useUpdateUser, useDeleteUser } from '@/generated/users/users'

const updateMutation = useUpdateUser()
const deleteMutation = useDeleteUser()

// Update user
await updateMutation.mutateAsync({
  userId,
  data: { name: 'New Name' }
})

// Delete user  
await deleteMutation.mutateAsync({ userId })
```

### Regenerating Client After API Changes

After any backend API changes:

1. Ensure backend is running: `make backend`
2. Regenerate client: `npm run generate`
3. TypeScript will immediately show any breaking changes
4. Update component code to match new types

## Architecture Flow

```
Vite Dev Server
    ↓
React App (main.tsx)
    ↓
WebSocketProvider ← → WebSocket Connection
    ↓                        ↓
Components (App.tsx)    Backend WebSocket
    ↓
Custom Hooks (useTodos.ts)
    ↓
TanStack Query ← → Generated API Services
                        ↓
                    Axios Client
                        ↓
                    Backend API
```

## Directory Structure

- `/src/components/ui/` - shadcn/ui components
- `/src/contexts/` - React contexts (WebSocket provider)
- `/src/generated/` - Auto-generated API client code
- `/src/hooks/` - Custom React hooks for data fetching
- `/src/lib/` - Utilities and API configuration

## Development Workflow

1. **Type Safety**: TypeScript ensures type consistency from API to UI
2. **Code Generation**: API changes trigger regeneration of client code
3. **Component Library**: shadcn/ui components provide consistent UI patterns
4. **Fast Refresh**: Vite + React plugin enables instant feedback during development
5. **Query Management**: TanStack Query handles complex async states automatically

## Key Integration Points

- **Vite + React**: Plugin system enables JSX and React-specific optimizations
- **Tailwind + shadcn**: Utility classes work seamlessly with component primitives
- **TypeScript + Codegen**: Generated types ensure API contract compliance
- **React Query + Axios**: Provides robust data fetching with built-in error handling
- **WebSocket + Context**: Real-time updates integrated via React Context API
- **HTTP + WebSocket**: Chat messages sent via HTTP, responses via WebSocket
