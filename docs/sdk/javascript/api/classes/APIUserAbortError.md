# Class: APIUserAbortError

The caller cancelled the request through an `AbortSignal`.

## Extends

* [`TypeSafeError`](TypeSafeError.md)

## Constructors

<a id="sdk-constructor" />

### Constructor

```ts theme={null}
new APIUserAbortError(message?, options?): APIUserAbortError;
```

#### Parameters

##### message?

`string` = `"Request was aborted."`

##### options?

`ErrorOptions`

#### Returns

`APIUserAbortError`

#### Overrides

[`TypeSafeError`](TypeSafeError.md).[`constructor`](TypeSafeError.md#sdk-constructor)
