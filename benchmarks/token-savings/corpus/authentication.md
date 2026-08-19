# Authentication and API tokens

Acme Notes API protects every write endpoint with a bearer token. Reads are open
by default on the loopback interface and protected once you bind to `0.0.0.0`.

## Creating a token

```
acme-notes token create --name my-laptop
```

This prints a token once. It is stored only as a hash, so a lost token cannot be
recovered — create a new one and revoke the old.

## Using a token

Send it as a header on each request:

```
Authorization: Bearer <token>
```

## Revoking a token

```
acme-notes token revoke --name my-laptop
```

Revocation is immediate. Any in-flight request using the token completes, but the
next request with it is rejected with `401 Unauthorized`.
