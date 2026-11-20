# Code rules in "backend/"
## Function rules
- Function names must be in English and snake_case
- Type-hint input parameters and return values
- One responsibility per function
- Keep functions to 50 lines or fewer where possible
- No magic numbers or hardcoded strings; move them to constants in `core/constants.py` (except domain enums tied to a specific model, which stay in that model's file)
- For optional types, write Optional[T] or T | None explicitly

## Function example
```python
def get_user_info(user_id: str) -> User:
    ...
```

## Class rules
- Class names in PascalCase
- One responsibility per class
- Inject dependencies through the constructor
- Prefer composition over inheritance
- Use ABC or Protocol when an abstraction is needed

## Layer structure
- Keep one-way dependencies: endpoint → service → repository
- Endpoints use services as dependencies
- Services take repositories as arguments and use them inside the class
- Services depend on abstract interfaces, not repository implementations
- Repositories only access data; no business logic in them
- No business logic in endpoints
- Every service and repository is a guaranteed singleton (@lru_cache and a get function)

## DTOs and VOs
- Use DTOs or VOs to move data between layers
- DTOs go in /schemes/dto/*.py
- VOs go in /schemes/vo/*.py
- Endpoint request and response schemes go in /schemes/requests.py and /schemes/responses.py
- Endpoints return Pydantic models
- The service layer returns dataclasses
- Repositories return dataclasses or SQLAlchemy ORM models
- Avoid passing raw dicts
- Minimize the Any type

## Database rules
- Prefer the ORM
- Check for N+1 problems
- If a soft-delete policy is used, handle it in one shared place

## Coding rules
- Avoid isinstance() and hasattr() where possible; use predefined types
- Use polymorphism instead of if-elif chains for type branching
- Follow SOLID
- Follow DRY (Don't Repeat Yourself)
- Follow YAGNI (You Aren't Gonna Need It)
- No circular dependencies
- Avoid unnecessary staticmethods
- Always put imports at the top of the file
- No wildcard imports (*)

## FastAPI rules
- Endpoint functions are async
- Services and repositories use async when they do I/O
- Always declare the response model
- Declare status_code
- API routers must set prefix and tags
- Use dependency injection
- Validate requests with Pydantic

## Exception handling
- Custom exceptions go in exceptions/*.py
- Raise in services and repositories; respond per exception at the endpoint
- Never send detailed error contents to the frontend
- Use the common error format for user responses
- Always log when an exception occurs
- Use explicit custom exceptions for expected failures

## Code quality checks
- Run "ruff check ." after writing code
- Run "ruff format ." after writing code
- Confirm all tests pass
- New features must come with test coverage

# Code rules in "frontend/"
## Tech stack
- React + TypeScript
- Function components
- React Hooks
- No any type

## Function rules
- Function names must be in English
- camelCase
- Declare input parameter and return types
- No export default

### Function example

```ts
function getUserInfo(userId: string): Promise<User> {
  ...
}
```

## Component rules
- Function components
- A Props interface is required
- Component names in PascalCase
- One component per file

### Component example
```tsx
interface UserCardProps {
  name: string;
  age: number;
}

export function UserCard({
  name,
  age,
}: UserCardProps): JSX.Element {
  return (
    <div>
      <p>{name}</p>
      <p>{age}</p>
    </div>
  );
}
```

## Directory structure
```text
frontend/
├── src/
│   ├── auth/          # AuthContext
│   ├── components/    # one folder per feature (chat/, collections/, documents/)
│   ├── hooks/         # React Query hooks, one use* module per feature
│   ├── lib/
│   │   ├── api/       # apiFetch client + one module per resource
│   │   └── types.ts   # shared types
│   ├── pages/
│   └── assets/
├── public/
├── package.json
├── tsconfig.json
└── vite.config.ts
```

## API layer separation

- No direct API calls inside components
- Manage every API call in `frontend/src/lib/api/`, through `apiFetch`
- Request and response types are required

### Example

```text
lib/api/
└── auth.ts
```

```ts
export async function login(
  request: LoginRequestDto,
): Promise<LoginResponseDto> {
  ...
}
```

## State management
- Global state lives in the stores directory
- Minimize business logic inside components
- Move state-change logic into a store or custom hook

## Custom hook rules
- Move reusable logic into the hooks directory
- Hook names must start with use

### Example
```ts
export function useUser(): UserState {
  ...
}
```

## DTOs and VOs
- Use DTOs for API requests/responses
- Use VOs for in-screen domain objects

### Location
- Request/response and domain types go in `src/lib/types.ts`

## Type definitions
- Prefer interfaces
- Use union types actively
- Minimize enums
- Shared types go in `src/lib/types.ts`

## Styling
- No inline styles
- Use CSS Modules or TailwindCSS
- Keep style files next to their component

## Error handling
- Every async API call needs error handling
- Separate user-facing error messages from internal logs

### Example
```ts
try {
  await login(request);
} catch (error) {
  console.error(error);
  throw new Error("Login failed.");
}
```

## Tests
- Write tests when adding or changing features
- Component tests
- Custom hook tests
- API layer tests

## Code quality
- ESLint
- TypeScript strict mode on

## After writing code
```bash
npm run lint
npm run build
```

## Don't
- Use any
- Use export default
- Call APIs directly inside components
- Omit Props types
- Omit return types
- Put business logic in UI components
- Scatter hardcoded strings
