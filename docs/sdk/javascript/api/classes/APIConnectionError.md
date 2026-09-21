# Class: APIConnectionError

The request or response-body delivery failed (DNS, TLS, connection closed, etc.).

## Extends

* [`TypeSafeError`](TypeSafeError.md)

## Extended by

* [`APITimeoutError`](APITimeoutError.md)

## Constructors

<a id="sdk-constructor" />

### Constructor

```ts theme={null}
new APIConnectionError(message?, options?): APIConnectionError;
```

#### Parameters

##### message?

`string` = `"Connection error."`

##### options?

`ErrorOptions`

#### Returns

`APIConnectionError`

#### Overrides

[`TypeSafeError`](TypeSafeError.md).[`constructor`](TypeSafeError.md#sdk-constructor)
